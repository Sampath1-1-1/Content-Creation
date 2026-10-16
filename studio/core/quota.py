"""Free-quota tracker.

Counts how much of each free daily allowance has been used, so the pipeline
can stop BEFORE hitting a limit and show what's left. Google resets YouTube
and Gemini daily quotas at midnight Pacific time, so days are counted in
that time zone.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .errors import QuotaExceededError

PACIFIC = ZoneInfo("America/Los_Angeles")


def quota_day(now: datetime | None = None) -> str:
    now = now or datetime.now(tz=PACIFIC)
    return now.astimezone(PACIFIC).strftime("%Y-%m-%d")


class QuotaLedger:
    def __init__(self, path: Path, limits: dict[str, int], reserves: dict[str, int] | None = None,
                 now_fn=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.limits = dict(limits)
        self.reserves = dict(reserves or {})
        self._now_fn = now_fn
        self._data = self._load()

    # ── storage ──
    def _today(self) -> str:
        return quota_day(self._now_fn() if self._now_fn else None)

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def _bucket(self) -> dict:
        today = self._today()
        if self._data.get("day") != today:
            self._data = {"day": today, "used": {}}
        return self._data.setdefault("used", {})

    # ── API ──
    def used(self, service: str) -> int:
        return int(self._bucket().get(service, 0))

    def limit(self, service: str) -> int | None:
        return self.limits.get(service)

    def remaining(self, service: str) -> int | None:
        lim = self.limit(service)
        if lim is None:
            return None
        return max(0, lim - self.reserves.get(service, 0) - self.used(service))

    def check(self, service: str, units: int) -> None:
        left = self.remaining(service)
        if left is not None and units > left:
            raise QuotaExceededError(
                f"Not enough free {service} quota today: need {units}, have {left} left "
                f"(limit {self.limit(service)}, safety reserve {self.reserves.get(service, 0)}).",
                fix="Wait until the quota resets (midnight Pacific time = 12:30 or 1:30 PM in India), "
                "then run the same command again — finished work is kept. "
                "Or reduce query_templates / search_orders in config.yaml.",
            )

    def spend(self, service: str, units: int) -> None:
        bucket = self._bucket()
        bucket[service] = int(bucket.get(service, 0)) + int(units)
        self._save()

    def mark_exhausted(self, service: str) -> None:
        """The server said we're out — trust it over our own count."""
        lim = self.limit(service)
        if lim is not None:
            self._bucket()[service] = lim
            self._save()

    def summary(self) -> str:
        lines = [f"Free quota used today ({self._today()}, Pacific time):"]
        services = sorted(set(self.limits) | set(self._bucket()))
        for s in services:
            lim = self.limit(s)
            used = self.used(s)
            lines.append(f"  • {s}: {used}" + (f" / {lim}" if lim else ""))
        return "\n".join(lines)
