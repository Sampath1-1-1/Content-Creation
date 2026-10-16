"""Project folder layout: projects/<topic-slug>/<NN_stage>/..."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

STAGE_DIRS = {
    1: "01_research",
    2: "02_creative",
    3: "03_characters",
    4: "04_audio",
    5: "05_timeline",
    6: "06_visuals",
    7: "07_render",
    8: "08_qa",
    9: "09_publish",
}


def slugify(text: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return (text[:max_len].rstrip("-")) or "untitled"


def stage_dir(project_dir: Path, stage_number: int) -> Path:
    d = project_dir / STAGE_DIRS[stage_number]
    d.mkdir(parents=True, exist_ok=True)
    return d
