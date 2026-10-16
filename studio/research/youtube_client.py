"""YouTube Data API client for RESEARCH ONLY — metadata and statistics.

Rules enforced here:
  • Never downloads video, audio or thumbnails (no such calls exist in this file).
  • Every API response is cached for at most 30 days (YouTube API policies),
    so re-running the same research costs zero quota.
  • Comment text is NEVER stored: it is analysed in memory into keyword
    counts and then discarded.
  • Every call is counted against the daily quota before it is made.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ..core.cache import DiskCache
from ..core.errors import QuotaExceededError, StudioError
from ..core.log import get_logger
from ..core.quota import QuotaLedger
from ..core.retry import with_retries

log = get_logger("youtube")

# Official quota cost per call (YouTube Data API v3).
UNIT_COST = {"search": 100, "videos": 1, "channels": 1, "commentThreads": 1}


def _http_reason(exc: BaseException) -> tuple[int | None, str]:
    status = getattr(getattr(exc, "resp", None), "status", None)
    reason = ""
    content = getattr(exc, "content", b"") or b""
    try:
        err = json.loads(content.decode("utf-8") if isinstance(content, bytes) else content)["error"]
        reason = (err.get("errors") or [{}])[0].get("reason", "") or err.get("status", "")
    except Exception:  # noqa: BLE001
        reason = str(exc)
    return (int(status) if status else None), reason


def chunks(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


class YouTubeResearchClient:
    def __init__(self, api_key: str, cache_root: Path, quota: QuotaLedger, retry_cfg: dict,
                 ttl_days: float = 30):
        try:
            from googleapiclient.discovery import build
        except ModuleNotFoundError as exc:
            raise StudioError("google-api-python-client is not installed.",
                              fix="pip install -r requirements.txt") from exc
        self._yt = build("youtube", "v3", developerKey=api_key, cache_discovery=False)
        self.cache = DiskCache(cache_root, "youtube", ttl_days=ttl_days)
        self.cache.purge_expired()
        self.quota = quota
        self.retry_cfg = retry_cfg

    # ── one guarded call ──
    def _call(self, kind: str, params: dict, cache: bool = True) -> dict:
        key = {"kind": kind, "params": params}
        if cache:
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        cost = UNIT_COST[kind]
        self.quota.check("youtube", cost)

        def request():
            res = getattr(self._yt, kind)()
            return res.list(**params).execute()

        def retryable(exc: BaseException) -> bool:
            status, reason = _http_reason(exc)
            if reason in ("quotaExceeded", "dailyLimitExceeded"):
                return False
            return status in (500, 502, 503, 504) or reason in ("rateLimitExceeded", "userRateLimitExceeded",
                                                                 "backendError")

        try:
            data = with_retries(
                request,
                attempts=int(self.retry_cfg.get("attempts", 5)),
                base_delay=float(self.retry_cfg.get("base_delay_s", 2.0)),
                max_delay=float(self.retry_cfg.get("max_delay_s", 60.0)),
                is_retryable=retryable,
                on_retry=lambda n, w, e: log.info("  YouTube busy — waiting %.0fs (try %d)…", w, n + 1),
            )
        except Exception as exc:  # noqa: BLE001
            status, reason = _http_reason(exc)
            if reason in ("quotaExceeded", "dailyLimitExceeded"):
                self.quota.mark_exhausted("youtube")
                raise QuotaExceededError(
                    "YouTube says today's free API quota is used up.",
                    fix="Wait for the reset (midnight Pacific ≈ 12:30 PM India time) and re-run. "
                    "Everything fetched so far is cached and won't cost quota again.") from exc
            if reason == "commentsDisabled":
                self.quota.spend("youtube", cost)
                return {"items": [], "commentsDisabled": True}
            if status in (400, 403) and reason in ("keyInvalid", "API_KEY_INVALID", "badRequest", "forbidden",
                                                   "accessNotConfigured"):
                raise StudioError(f"YouTube API rejected the key ({reason}).",
                                  fix="Check YOUTUBE_API_KEY in .env and that 'YouTube Data API v3' "
                                  "is enabled in your Google Cloud project.") from exc
            raise StudioError(f"YouTube API error ({status} {reason}).",
                              fix="Check your internet connection and re-run.") from exc
        self.quota.spend("youtube", cost)
        if cache:
            self.cache.set(key, data)
        return data

    # ── public methods ──
    def search_ids(self, query: str, order: str, max_results: int, region: str, language: str) -> list[str]:
        data = self._call("search", {
            "part": "id", "q": query, "type": "video", "order": order,
            "maxResults": min(50, max_results), "regionCode": region,
            "relevanceLanguage": language, "safeSearch": "strict",
        })
        return [it["id"]["videoId"] for it in data.get("items", []) if it.get("id", {}).get("videoId")]

    def videos(self, ids: list[str]) -> list[dict]:
        out: list[dict] = []
        for batch in chunks(ids, 50):
            # (maxResults is not allowed together with id — max 50 ids per call instead)
            data = self._call("videos", {"part": "snippet,statistics,contentDetails,status",
                                         "id": ",".join(batch)})
            out.extend(data.get("items", []))
        return out

    def channels(self, ids: list[str]) -> list[dict]:
        out: list[dict] = []
        for batch in chunks(sorted(set(ids)), 50):
            data = self._call("channels", {"part": "snippet,statistics", "id": ",".join(batch)})
            out.extend(data.get("items", []))
        return out

    def comment_texts(self, video_id: str, n: int) -> list[str]:
        """Top comments as plain text — returned for in-memory analysis only, never cached."""
        data = self._call("commentThreads", {"part": "snippet", "videoId": video_id, "order": "relevance",
                                             "maxResults": min(100, n), "textFormat": "plainText"},
                          cache=False)
        texts = []
        for it in data.get("items", []):
            snip = it.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            if snip.get("textDisplay"):
                texts.append(snip["textDisplay"])
        return texts


class FixtureYouTubeClient:
    """Offline stand-in with the same methods, reading a sample JSON file.

    Used for demos and tests — the sample data is synthetic (made up), not real videos.
    """

    def __init__(self, fixture_path: Path):
        self.data: dict[str, Any] = json.loads(Path(fixture_path).read_text(encoding="utf-8"))

    def search_ids(self, query: str, order: str, max_results: int, region: str, language: str) -> list[str]:
        ids = self.data["searches"].get(query.lower(), self.data["searches"].get("_default", []))
        if order == "viewCount":
            views = {v["id"]: int(v["statistics"].get("viewCount", 0)) for v in self.data["videos"]}
            ids = sorted(ids, key=lambda i: -views.get(i, 0))
        return ids[:max_results]

    def videos(self, ids: list[str]) -> list[dict]:
        wanted = set(ids)
        return [v for v in self.data["videos"] if v["id"] in wanted]

    def channels(self, ids: list[str]) -> list[dict]:
        wanted = set(ids)
        return [c for c in self.data["channels"] if c["id"] in wanted]

    def comment_texts(self, video_id: str, n: int) -> list[str]:
        return self.data.get("comments", {}).get(video_id, [])[:n]
