"""Stable hashes for caching and resume decisions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def hash_obj(obj: Any) -> str:
    return hashlib.sha256(stable_json(obj).encode("utf-8")).hexdigest()


def hash_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def hash_files(paths: Iterable[Path]) -> str:
    return hash_obj({str(p.name): hash_file(p) for p in sorted(paths) if p.exists()})
