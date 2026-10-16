"""Per-project manifest: which stages finished, with which inputs.

This is what makes the pipeline RESUMABLE. A stage is skipped when:
  • it finished before, AND
  • its inputs (topic + relevant settings + upstream outputs) are unchanged, AND
  • all its output files still exist.
Change a setting or delete an output → only the affected stages re-run.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Manifest:
    def __init__(self, project_dir: Path):
        self.path = Path(project_dir) / "manifest.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, Any] = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                backup = self.path.with_suffix(".corrupt.json")
                os.replace(self.path, backup)
        return {"stages": {}, "gates": {}, "created_at": _now()}

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    # ── stages ──
    def stage(self, key: str) -> dict:
        return self.data.setdefault("stages", {}).get(key, {})

    def is_complete(self, key: str, input_hash: str, outputs: list[Path]) -> bool:
        st = self.stage(key)
        return (
            st.get("status") == "done"
            and st.get("input_hash") == input_hash
            and all(Path(p).exists() for p in outputs)
        )

    def mark_started(self, key: str, input_hash: str) -> None:
        self.data.setdefault("stages", {})[key] = {
            "status": "running", "input_hash": input_hash, "started_at": _now(),
        }
        self.save()

    def mark_done(self, key: str, input_hash: str, outputs: list[Path], meta: dict | None = None) -> None:
        st = self.data.setdefault("stages", {}).setdefault(key, {})
        st.update({
            "status": "done", "input_hash": input_hash, "finished_at": _now(),
            "outputs": [str(p) for p in outputs], "meta": meta or {},
        })
        self.save()

    def mark_failed(self, key: str, error: str) -> None:
        st = self.data.setdefault("stages", {}).setdefault(key, {})
        st.update({"status": "failed", "error": error, "failed_at": _now()})
        self.save()

    # ── approval gates ──
    def gate(self, gate_id: str) -> dict:
        return self.data.setdefault("gates", {}).get(gate_id, {})

    def set_gate(self, gate_id: str, decision: str, content_hash: str, notes: str = "") -> None:
        self.data.setdefault("gates", {})[gate_id] = {
            "decision": decision, "content_hash": content_hash, "notes": notes, "at": _now(),
        }
        self.save()
