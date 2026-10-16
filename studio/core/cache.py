"""Disk cache: identical requests are answered from disk, never re-fetched.

Each entry is a JSON file  cache/<namespace>/<sha256>.json  holding the value
and the time it was saved, so entries can expire (e.g. YouTube data must not
be kept more than 30 days under the YouTube API policies).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .hashing import hash_obj


class DiskCache:
    def __init__(self, root: Path, namespace: str, ttl_days: float | None = None,
                 clock=time.time):
        self.dir = Path(root) / namespace
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ttl_s = ttl_days * 86400 if ttl_days else None
        self._clock = clock

    def _path(self, payload: Any) -> Path:
        return self.dir / f"{hash_obj(payload)}.json"

    def get(self, payload: Any) -> Any | None:
        path = self._path(payload)
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            path.unlink(missing_ok=True)  # corrupted entry: drop it
            return None
        if self.ttl_s is not None and self._clock() - entry.get("saved_at", 0) > self.ttl_s:
            path.unlink(missing_ok=True)
            return None
        return entry.get("value")

    def set(self, payload: Any, value: Any) -> None:
        path = self._path(payload)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"saved_at": self._clock(), "value": value}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)  # atomic: a crash never leaves a half-written entry

    def purge_expired(self) -> int:
        if self.ttl_s is None:
            return 0
        removed = 0
        now = self._clock()
        for path in self.dir.glob("*.json"):
            try:
                saved = json.loads(path.read_text(encoding="utf-8")).get("saved_at", 0)
            except (json.JSONDecodeError, OSError):
                saved = 0
            if now - saved > self.ttl_s:
                path.unlink(missing_ok=True)
                removed += 1
        return removed
