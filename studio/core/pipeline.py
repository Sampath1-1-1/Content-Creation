"""Runs the stages in order, skipping any that are already done (resume)."""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .context import RunContext
from .hashing import hash_obj
from .log import get_logger

log = get_logger("pipeline")


@dataclass
class Stage:
    number: int
    key: str
    title: str
    run: Callable[[RunContext], dict] | None = None          # None → not built yet
    fingerprint: Callable[[RunContext], dict] | None = None  # inputs that affect the output
    outputs: Callable[[RunContext], list[Path]] | None = None

    @property
    def built(self) -> bool:
        return self.run is not None


def stage_registry() -> list[Stage]:
    from ..stages import s1_research

    return [
        s1_research.STAGE,
        Stage(2, "s2_creative", "Creative plan (script, lyrics, shot list)"),
        Stage(3, "s3_characters", "Character bible"),
        Stage(4, "s4_audio", "Audio (song, narration, mix)"),
        Stage(5, "s5_timeline", "Timeline"),
        Stage(6, "s6_visuals", "Visuals"),
        Stage(7, "s7_assembly", "Assembly"),
        Stage(8, "s8_qa", "Quality checks"),
        Stage(9, "s9_publish", "Publishing package"),
    ]


def run_pipeline(ctx: RunContext, from_stage: int = 1, only_stage: int | None = None,
                 force: bool = False) -> bool:
    """Returns True if every requested stage finished."""
    stages = stage_registry()
    selected = [s for s in stages if (s.number == only_stage if only_stage else s.number >= from_stage)]

    for stage in selected:
        label = f"Stage {stage.number} – {stage.title}"
        if not stage.built:
            log.info(f"\n⏭  {label}: not built yet. The pipeline stops here for now.")
            return False

        fingerprint = stage.fingerprint(ctx) if stage.fingerprint else {}
        input_hash = hash_obj({"stage": stage.key, "topic": ctx.topic, "mode": ctx.mode, **fingerprint})
        outputs = stage.outputs(ctx) if stage.outputs else []

        if not force and ctx.manifest.is_complete(stage.key, input_hash, outputs):
            log.info(f"✔  {label}: already done — reusing saved results.")
            continue

        log.info(f"\n▶  {label}")
        ctx.manifest.mark_started(stage.key, input_hash)
        t0 = time.time()
        try:
            meta = stage.run(ctx) or {}
        except BaseException as exc:
            ctx.manifest.mark_failed(stage.key, f"{type(exc).__name__}: {exc}")
            log.debug(traceback.format_exc())
            raise
        meta["seconds"] = round(time.time() - t0, 1)
        ctx.manifest.mark_done(stage.key, input_hash, outputs, meta)
        log.info(f"✅ {label} finished in {meta['seconds']}s")
    return True
