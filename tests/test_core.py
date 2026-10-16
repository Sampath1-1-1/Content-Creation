"""Core machinery: cache, quota, retries, manifest/resume, gates, config."""

import tempfile
from datetime import datetime
from pathlib import Path

from studio.core.cache import DiskCache
from studio.core.config import deep_merge, load_config
from studio.core.errors import GatePending, GateRejected, QuotaExceededError
from studio.core.gates import approval_gate
from studio.core.llm import extract_json
from studio.core.manifest import Manifest
from studio.core.paths import slugify
from studio.core.quota import PACIFIC, QuotaLedger
from studio.core.retry import with_retries


def test_cache_roundtrip_and_ttl():
    with tempfile.TemporaryDirectory() as d:
        clock = [1000.0]
        c = DiskCache(Path(d), "ns", ttl_days=1, clock=lambda: clock[0])
        assert c.get({"q": 1}) is None
        c.set({"q": 1}, {"answer": 42})
        assert c.get({"q": 1}) == {"answer": 42}
        assert c.get({"q": 2}) is None
        clock[0] += 2 * 86400  # two days later → expired
        assert c.get({"q": 1}) is None


def test_quota_check_spend_and_daily_reset():
    with tempfile.TemporaryDirectory() as d:
        now = [datetime(2026, 10, 16, 10, 0, tzinfo=PACIFIC)]
        q = QuotaLedger(Path(d) / "q.json", {"youtube": 1000}, {"youtube": 100}, now_fn=lambda: now[0])
        assert q.remaining("youtube") == 900
        q.spend("youtube", 800)
        assert q.remaining("youtube") == 100
        try:
            q.check("youtube", 200)
            raise AssertionError("should have raised")
        except QuotaExceededError:
            pass
        # persisted across instances
        q2 = QuotaLedger(Path(d) / "q.json", {"youtube": 1000}, {"youtube": 100}, now_fn=lambda: now[0])
        assert q2.used("youtube") == 800
        now[0] = datetime(2026, 10, 17, 0, 1, tzinfo=PACIFIC)  # after midnight Pacific
        assert q2.used("youtube") == 0


def test_retry_succeeds_after_transient_errors():
    calls = {"n": 0}
    waits = []

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("503")
        return "ok"

    out = with_retries(flaky, attempts=5, base_delay=1, max_delay=10,
                       is_retryable=lambda e: "503" in str(e), sleep=waits.append)
    assert out == "ok" and calls["n"] == 3 and len(waits) == 2


def test_retry_does_not_retry_permanent_errors():
    calls = {"n": 0}

    def bad():
        calls["n"] += 1
        raise ValueError("bad key")

    try:
        with_retries(bad, attempts=5, base_delay=1, max_delay=10, is_retryable=lambda e: False,
                     sleep=lambda s: None)
    except ValueError:
        pass
    assert calls["n"] == 1


def test_manifest_resume_logic():
    with tempfile.TemporaryDirectory() as d:
        m = Manifest(Path(d))
        out = Path(d) / "out.json"
        assert not m.is_complete("s1", "h1", [out])
        out.write_text("{}")
        m.mark_started("s1", "h1")
        assert not m.is_complete("s1", "h1", [out])  # running ≠ done
        m.mark_done("s1", "h1", [out])
        assert Manifest(Path(d)).is_complete("s1", "h1", [out])       # survives reload
        assert not Manifest(Path(d)).is_complete("s1", "h2", [out])   # inputs changed
        out.unlink()
        assert not Manifest(Path(d)).is_complete("s1", "h1", [out])   # output deleted


def test_gate_flow():
    with tempfile.TemporaryDirectory() as d:
        m = Manifest(Path(d))
        f = Path(d) / "review.html"
        f.write_text("<p>hi</p>")
        answers = iter(["n", "make it slower"])
        try:
            approval_gate(m, "g1", "Script", f, "hashA", open_browser=False,
                          input_fn=lambda _: next(answers), interactive=True)
            raise AssertionError("should have raised")
        except GateRejected:
            assert m.gate("g1")["notes"] == "make it slower"
        answers = iter(["y", ""])
        approval_gate(m, "g1", "Script", f, "hashA", open_browser=False,
                      input_fn=lambda _: next(answers), interactive=True)
        # already approved for the same content → no question asked
        approval_gate(m, "g1", "Script", f, "hashA", open_browser=False,
                      input_fn=lambda _: (_ for _ in ()).throw(AssertionError("asked again")), interactive=True)
        # content changed + no terminal → pending
        try:
            approval_gate(m, "g1", "Script", f, "hashB", open_browser=False, interactive=False)
            raise AssertionError("should have raised")
        except GatePending:
            pass


def test_config_preview_overrides():
    final = load_config(mode="final")
    preview = load_config(mode="preview")
    assert final.get_path("video.width") == 1920
    assert preview.get_path("video.width") == 960
    assert preview.get_path("video.fps") == final.get_path("video.fps") == 30
    assert deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"b": 3}}) == {"a": {"b": 3, "c": 2}}


def test_slugify_and_json_extract():
    assert slugify("Numbers 1 to 10!") == "numbers-1-to-10"
    assert slugify("   ") == "untitled"
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": [1,2]}') == {"a": [1, 2]}
