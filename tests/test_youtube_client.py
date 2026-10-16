"""YouTube client behaviour with a FAKE API object (no network, no key)."""

import json
import tempfile
from pathlib import Path

from studio.core.errors import QuotaExceededError
from studio.core.quota import QuotaLedger
from studio.research.youtube_client import YouTubeResearchClient


class FakeHttpError(Exception):
    def __init__(self, status, reason):
        super().__init__(f"{status} {reason}")
        self.resp = type("R", (), {"status": status})()
        self.content = json.dumps({"error": {"errors": [{"reason": reason}]}}).encode()


class FakeResource:
    def __init__(self, api, kind):
        self.api, self.kind = api, kind

    def list(self, **params):
        api, kind = self.api, self.kind

        class Req:
            def execute(self_inner):
                api.calls.append((kind, params))
                behaviour = api.behaviour.get(kind)
                if isinstance(behaviour, list) and behaviour:
                    nxt = behaviour.pop(0)
                    if isinstance(nxt, Exception):
                        raise nxt
                    return nxt
                if isinstance(behaviour, Exception):
                    raise behaviour
                return {"items": [{"id": {"videoId": "v1"}}, {"id": {"videoId": "v2"}}]}
        return Req()


class FakeYT:
    def __init__(self, behaviour=None):
        self.calls, self.behaviour = [], behaviour or {}

    def __getattr__(self, kind):
        return lambda: FakeResource(self, kind)


def _client(d: Path, fake: FakeYT, limit=10000) -> YouTubeResearchClient:
    from studio.core.cache import DiskCache
    c = object.__new__(YouTubeResearchClient)  # skip __init__ (needs the real library)
    c._yt = fake
    c.cache = DiskCache(d, "youtube", ttl_days=30)
    c.quota = QuotaLedger(d / "q.json", {"youtube": limit})
    c.retry_cfg = {"attempts": 3, "base_delay_s": 0.0, "max_delay_s": 0.0}
    return c


def test_search_spends_quota_once_then_uses_cache():
    with tempfile.TemporaryDirectory() as d:
        fake = FakeYT()
        c = _client(Path(d), fake)
        assert c.search_ids("numbers", "relevance", 50, "US", "en") == ["v1", "v2"]
        assert c.quota.used("youtube") == 100
        c.search_ids("numbers", "relevance", 50, "US", "en")
        assert len(fake.calls) == 1 and c.quota.used("youtube") == 100  # cached: free


def test_stops_before_call_when_quota_would_run_out():
    with tempfile.TemporaryDirectory() as d:
        fake = FakeYT()
        c = _client(Path(d), fake, limit=50)
        try:
            c.search_ids("numbers", "relevance", 50, "US", "en")
            raise AssertionError("should have raised")
        except QuotaExceededError:
            pass
        assert fake.calls == []  # never called the API


def test_server_quota_error_is_friendly_and_not_retried():
    with tempfile.TemporaryDirectory() as d:
        fake = FakeYT({"search": FakeHttpError(403, "quotaExceeded")})
        c = _client(Path(d), fake)
        try:
            c.search_ids("numbers", "relevance", 50, "US", "en")
            raise AssertionError("should have raised")
        except QuotaExceededError:
            pass
        assert len(fake.calls) == 1
        assert c.quota.remaining("youtube") == 0


def test_transient_error_is_retried():
    with tempfile.TemporaryDirectory() as d:
        fake = FakeYT({"videos": [FakeHttpError(503, "backendError"), {"items": [{"id": "v1"}]}]})
        c = _client(Path(d), fake)
        assert c.videos(["v1"]) == [{"id": "v1"}]
        assert len(fake.calls) == 2
        assert "maxResults" not in fake.calls[-1][1]  # not allowed with id


def test_comments_disabled_and_never_cached():
    with tempfile.TemporaryDirectory() as d:
        fake = FakeYT({"commentThreads": [
            FakeHttpError(403, "commentsDisabled"),
            {"items": [{"snippet": {"topLevelComment": {"snippet": {"textDisplay": "love it"}}}}]},
        ]})
        c = _client(Path(d), fake)
        assert c.comment_texts("v1", 20) == []
        assert c.comment_texts("v2", 20) == ["love it"]
        cached = list((Path(d) / "youtube").glob("*.json"))
        assert all("love it" not in p.read_text() for p in cached)
