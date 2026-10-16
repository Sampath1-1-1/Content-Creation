"""Stage 1 analysis: parsing, statistics, brand-term detection, gaps."""

import json
from datetime import datetime, timezone
from pathlib import Path

from studio.research import analysis
from studio.stages.s1_research import build_queries, estimate_units

FIXTURE = Path(__file__).parent / "fixtures" / "youtube_sample.json"
NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _records():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    chans = {c["id"]: c for c in data["channels"]}
    return [r for v in data["videos"] if (r := analysis.record_from_api(v, chans, NOW))]


def test_parse_iso_duration():
    assert analysis.parse_iso_duration("PT3M21S") == 201
    assert analysis.parse_iso_duration("PT1H2M3S") == 3723
    assert analysis.parse_iso_duration("PT45S") == 45
    assert analysis.parse_iso_duration("P1DT1S") == 86401
    assert analysis.parse_iso_duration("") == 0
    assert analysis.parse_iso_duration("garbage") == 0


def test_title_features():
    f = analysis.title_features("Counting 1-10 Song | Fun NUMBERS for Toddlers 🍎")
    assert f["kw_song"] and f["kw_count"] and f["kw_toddler_baby"] and f["kw_range_1_10"]
    assert f["has_pipe_or_dash"] and f["has_emoji"] and f["has_digits"]
    assert not f["kw_story"]


def test_record_skips_live_and_zero_duration():
    base = {"id": "x", "snippet": {"title": "t", "channelId": "c", "publishedAt": "2026-01-01T00:00:00Z",
                                   "liveBroadcastContent": "live"},
            "statistics": {"viewCount": "10"}, "contentDetails": {"duration": "PT1M"}}
    assert analysis.record_from_api(base, {}, NOW) is None
    base["snippet"]["liveBroadcastContent"] = "none"
    base["contentDetails"]["duration"] = "P0D"
    assert analysis.record_from_api(base, {}, NOW) is None


def test_hidden_likes_and_comments_are_none_not_zero():
    v = {"id": "x", "snippet": {"title": "t", "channelId": "c", "publishedAt": "2026-01-01T00:00:00Z"},
         "statistics": {"viewCount": "1000"}, "contentDetails": {"duration": "PT2M"}}
    r = analysis.record_from_api(v, {}, NOW)
    assert r["likes"] is None and r["like_rate"] is None
    assert r["comments_enabled"] is False


def test_percentile_and_spearman():
    assert analysis.percentile([1, 2, 3, 4, 5], 0.5) == 3
    assert analysis.percentile([], 0.5) is None
    assert analysis.spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == 1.0
    assert analysis.spearman([1, 2, 3, 4, 5], [50, 40, 30, 20, 10]) == -1.0
    assert analysis.spearman([1, 2], [1, 2]) is None  # too few points


def test_summary_on_fixture_is_sane():
    recs = _records()
    s = analysis.summarize(recs, min_age_days=7)
    assert s["enough_data"]
    assert s["usable_videos"] > 100
    d = s["duration"]["long_form_top"]
    assert 60 < d["p25_s"] <= d["median_s"] <= d["p75_s"]
    assert 0 <= s["made_for_kids_share"] <= 1
    shares = sum(b["share"] for b in s["duration_buckets"])
    assert abs(shares - 1.0) < 0.01  # every video lands in exactly one bucket


def test_brand_terms_detected_and_excluded_from_words():
    s = analysis.summarize(_records())
    # the synthetic recurring 'character' name used by one channel must be flagged
    assert "zibbo" in s["brand_terms"]
    assert "maple" in s["brand_terms"]
    words = {w["word"] for w in s["title"]["common_words_in_top_titles"]}
    assert "zibbo" not in words
    # generic teaching words are NOT treated as brands
    assert "counting" not in s["brand_terms"] and "numbers" not in s["brand_terms"]


def test_too_little_data():
    s = analysis.summarize(_records()[:3])
    assert s["enough_data"] is False
    assert analysis.find_gaps(s) == []


def test_gaps_are_explained():
    gaps = analysis.find_gaps(analysis.summarize(_records()))
    assert all(isinstance(g, str) and len(g) > 20 for g in gaps)


def test_comment_analysis_keeps_counts_only():
    out = analysis.analyse_comments({"a": ["My son loves this", "too loud"], "b": ["so many ads"]})
    assert out["comments_analysed"] == 3
    assert out["share_mentioning"]["parent_signal"] > 0
    assert "My son loves this" not in json.dumps(out)


def test_queries_and_cost_estimate():
    qs = build_queries("numbers 1 to 10", ["{topic}", "{topic}  song", "{topic}"])
    assert qs == ["numbers 1 to 10", "numbers 1 to 10 song"]
    assert estimate_units(6, 2, 250, 15) == 6 * 2 * 100 + 5 + 5 + 15
    assert estimate_units(6, 2, 400, 15, n_regions=3) == 6 * 2 * 3 * 100 + 8 + 8 + 15


def test_region_list():
    from studio.stages.s1_research import region_list
    assert region_list({"regions": ["global", "US", "in", "US"]}) == ["GLOBAL", "US", "IN"]
    assert region_list({"region_code": "IN"}) == ["IN"]   # old config style still works
    assert region_list({}) == ["GLOBAL"]
