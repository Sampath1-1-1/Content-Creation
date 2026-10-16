"""The run context passed to every stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config
from .manifest import Manifest
from .quota import QuotaLedger


@dataclass
class RunContext:
    cfg: Config
    topic: str
    slug: str
    project_dir: Path
    cache_root: Path
    manifest: Manifest
    quota: QuotaLedger
    options: dict[str, Any] = field(default_factory=dict)  # CLI flags (fixture, force, ...)

    @property
    def mode(self) -> str:
        return self.cfg.get("mode", "final")


def build_quota(cfg: Config, cache_root: Path) -> QuotaLedger:
    limits = {"youtube": int(cfg.get_path("quotas.youtube_units_per_day", 10000))}
    reserves = {"youtube": int(cfg.get_path("quotas.youtube_reserve_units", 0))}
    return QuotaLedger(cache_root / "quota.json", limits, reserves)
