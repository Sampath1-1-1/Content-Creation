"""End-to-end Stage 1 run on synthetic data (no network, no API keys)."""

import json
import tempfile
from pathlib import Path

from studio.core.config import load_config
from studio.core.context import RunContext, build_quota
from studio.core.manifest import Manifest
from studio.core.pipeline import run_pipeline

FIXTURE = Path(__file__).parent / "fixtures" / "youtube_sample.json"


def _ctx(d: Path) -> RunContext:
    cfg = load_config(mode="final")
    cache = d / "cache"
    return RunContext(cfg=cfg, topic="numbers 1 to 10", slug="demo", project_dir=d / "proj",
                      cache_root=cache, manifest=Manifest(d / "proj"), quota=build_quota(cfg, cache),
                      options={"fixture": str(FIXTURE)})


def test_stage1_runs_offline_and_resumes():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        ctx = _ctx(d)
        finished = run_pipeline(ctx, only_stage=1)
        assert finished
        out = d / "proj" / "01_research"
        rep = json.loads((out / "research.json").read_text(encoding="utf-8"))
        assert rep["data_source"] == "synthetic_fixture"
        assert rep["measured"]["enough_data"]
        assert rep["recommendations"]["length_s"][0] < rep["recommendations"]["length_s"][1]
        assert "zibbo" in rep["brand_terms_never_use"]
        html = (out / "research_report.html").read_text(encoding="utf-8")
        assert "DEMO DATA" in html
        assert ctx.quota.used("youtube") == 0  # fixture mode never touches the API

        # second run: stage is skipped (resume), files untouched
        mtime = (out / "research.json").stat().st_mtime
        run_pipeline(_ctx(d), only_stage=1)
        assert (out / "research.json").stat().st_mtime == mtime


def test_pipeline_stops_cleanly_at_unbuilt_stage():
    with tempfile.TemporaryDirectory() as d:
        assert run_pipeline(_ctx(Path(d)), from_stage=1) is False  # stage 2 not built yet
