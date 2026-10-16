"""Pure statistics over video METADATA. No network, no content — easy to unit-test.

Performance measure: views per day since upload ("vpd"). Raw view counts
favour very old videos; vpd tells us what is working *now*. The "top" group
is the top 25% of videos by vpd.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any

# ── parsing ───────────────────────────────────────────────────────────────

_DUR = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$")


def parse_iso_duration(text: str | None) -> float:
    """'PT3M21S' → 201.0 seconds. Unknown/empty → 0."""
    if not text:
        return 0.0
    m = _DUR.match(text.strip())
    if not m:
        return 0.0
    d, h, mi, s = m.groups()
    return int(d or 0) * 86400 + int(h or 0) * 3600 + int(mi or 0) * 60 + float(s or 0)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ── title features (patterns, not content) ────────────────────────────────

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⭐⭕]")
KEYWORD_FEATURES = {
    "kw_song": r"\bsongs?\b",
    "kw_learn": r"\blearn(ing)?\b|\beducational\b",
    "kw_count": r"\bcount(ing)?\b",
    "kw_kids": r"\bkids?\b|\bchildren\b",
    "kw_toddler_baby": r"\btoddlers?\b|\bbab(y|ies)\b|\bpreschool\b|\bkindergarten\b",
    "kw_nursery_rhyme": r"\bnursery\b|\brhymes?\b",
    "kw_compilation": r"\bcompilation\b|\bmore\b|\bmix\b|\bnon[- ]?stop\b",
    "kw_story": r"\bstor(y|ies)\b|\badventure\b",
    "kw_dance": r"\bdance\b|\bdancing\b|\bmove\b",
    "kw_animals": r"\banimals?\b|\bfarm\b|\bzoo\b",
    "kw_minutes_in_title": r"\b\d+\s*(min|mins|minutes|hour|hours|hr)\b",
    "kw_range_1_10": r"\b1\s*(-|to|–)\s*(10|20|100)\b",
}


def title_features(title: str) -> dict[str, Any]:
    words = re.findall(r"[A-Za-z0-9']+", title)
    lower = title.lower()
    feats: dict[str, Any] = {
        "len_chars": len(title),
        "len_words": len(words),
        "has_pipe_or_dash": ("|" in title) or (" - " in title),
        "has_emoji": bool(_EMOJI.search(title)),
        "has_digits": bool(re.search(r"\d", title)),
        "has_hashtag": "#" in title,
        "has_exclaim": "!" in title,
        "has_question": "?" in title,
        "caps_words_ratio": round(
            sum(1 for w in words if len(w) >= 2 and w.isupper() and not w.isdigit()) / max(1, len(words)), 3),
    }
    feats["has_caps_words"] = feats["caps_words_ratio"] >= 0.15
    for name, pattern in KEYWORD_FEATURES.items():
        feats[name] = bool(re.search(pattern, lower))
    return feats


BOOL_FEATURES = ["has_pipe_or_dash", "has_emoji", "has_digits", "has_hashtag", "has_exclaim",
                 "has_question", "has_caps_words", *KEYWORD_FEATURES.keys()]

# ── records ───────────────────────────────────────────────────────────────


def record_from_api(video: dict, channels_by_id: dict[str, dict], now: datetime) -> dict | None:
    sn = video.get("snippet", {})
    st = video.get("statistics", {})
    if sn.get("liveBroadcastContent", "none") != "none":
        return None
    duration = parse_iso_duration(video.get("contentDetails", {}).get("duration"))
    if duration <= 0 or not sn.get("publishedAt"):
        return None
    published = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
    age_days = max((now - published).total_seconds() / 86400, 0.01)
    views = _int_or_none(st.get("viewCount")) or 0
    likes = _int_or_none(st.get("likeCount"))
    comments = _int_or_none(st.get("commentCount"))
    ch = channels_by_id.get(sn.get("channelId", ""), {})
    ch_stats = ch.get("statistics", {})
    subs = None if ch_stats.get("hiddenSubscriberCount") else _int_or_none(ch_stats.get("subscriberCount"))
    return {
        "id": video.get("id"),
        "title": sn.get("title", ""),
        "channel_id": sn.get("channelId", ""),
        "channel_title": sn.get("channelTitle", "") or ch.get("snippet", {}).get("title", ""),
        "duration_s": duration,
        "age_days": round(age_days, 2),
        "published": sn["publishedAt"],
        "views": views,
        "likes": likes,
        "comments": comments,
        "views_per_day": views / age_days,
        "like_rate": (likes / views) if (likes is not None and views) else None,
        "comment_rate": (comments / views) if (comments is not None and views) else None,
        "made_for_kids": video.get("status", {}).get("madeForKids"),
        "language": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "unknown",
        "tags_count": len(sn.get("tags", []) or []),
        "channel_subs": subs,
        "views_per_sub": (views / subs) if subs else None,
        "comments_enabled": comments is not None,
        **title_features(sn.get("title", "")),
    }


# ── statistics helpers ────────────────────────────────────────────────────


def percentile(values: list[float], q: float) -> float | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 5:
        return None
    rx, ry = _ranks(x), _ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if vx == 0 or vy == 0:
        return None
    return round(cov / (vx * vy), 3)


def _med(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return median(vals) if vals else None


def _round_to(x: float | None, step: int) -> int | None:
    return None if x is None else int(round(x / step) * step)


DURATION_BUCKETS = [
    ("≤1 min (Shorts)", 0, 60), ("1–3 min", 60, 180), ("3–5 min", 180, 300), ("5–10 min", 300, 600),
    ("10–20 min", 600, 1200), ("20–40 min", 1200, 2400), ("40+ min", 2400, 10 ** 9),
]

STOPWORDS = set("""a an and are as at be by for from has have in is it its of on or the to with
your you our we us this that these those how what learn learning kids kid song songs video videos
children child toddlers toddler baby babies fun easy best new more full episode part official""".split())

# Words that are generic in this niche, so not treated as brand names.
GENERIC_VOCAB = STOPWORDS | set("""tv channel learning school academy music songs rhymes nursery
cartoon cartoons animation education educational studio studios family world fun club time play
english numbers number counting count one two three four five six seven eight nine ten twenty
hundred abc alphabet colors colours shapes animals preschool kindergarten super little big happy""".split())


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z']{2,}", text.lower())]


def detect_brand_terms(records: list[dict]) -> list[str]:
    """Words that look like channel/character/show names → must NEVER be used.

    1. Distinctive words from channel names.
    2. Words used in ≥3 titles where ≥80% of those titles come from ONE channel
       (typical for a recurring character's name).
    """
    brands: set[str] = set()
    for r in records:
        for t in _tokens(r.get("channel_title", "")):
            if t not in GENERIC_VOCAB:
                brands.add(t)
    by_token: dict[str, Counter] = defaultdict(Counter)
    for r in records:
        for t in set(_tokens(r["title"])):
            by_token[t][r["channel_id"]] += 1
    for t, chans in by_token.items():
        total = sum(chans.values())
        if t in GENERIC_VOCAB or total < 3:
            continue
        if chans.most_common(1)[0][1] / total >= 0.8 and len(chans) <= 2:
            brands.add(t)
    return sorted(brands)


# ── comment analysis (aggregate counts only) ──────────────────────────────

COMMENT_LEXICON = {
    "praise": r"\b(love|loves|loved|favou?rite|thank|thanks|best|great|amazing|beautiful|cute|helpful|enjoy|enjoys|happy|wonderful|awesome)\b",
    "learning_signal": r"\b(learn|learned|learnt|learning|now (he|she) can|counts?|counting|knows?)\b",
    "parent_signal": r"\b(my (son|daughter|kid|kids|toddler|baby|grandson|granddaughter|child)|year old|month old)\b",
    "too_fast": r"\b(too fast|so fast|slow (it )?down|faster than)\b",
    "too_loud_noisy": r"\b(too loud|loud|noisy|noise|screaming)\b",
    "annoying_repetitive": r"\b(annoying|repetitive|same thing|boring)\b",
    "scary_creepy": r"\b(scary|creepy|scared|weird|disturbing)\b",
    "ads_complaint": r"\b(ads?|advert|advertisements?|commercials?)\b",
    "error_complaint": r"\b(wrong|mistake|incorrect|error|misspell)\w*",
    "voice_music": r"\b(voice|sing|singing|singer|music|tune|melody|beat)\b",
    "visual": r"\b(animation|colou?rs?|graphics|characters?|drawing)\b",
}


def analyse_comments(texts_by_video: dict[str, list[str]]) -> dict[str, Any]:
    counts: Counter = Counter()
    total = 0
    for texts in texts_by_video.values():
        for t in texts:
            total += 1
            low = t.lower()
            for label, pattern in COMMENT_LEXICON.items():
                if re.search(pattern, low):
                    counts[label] += 1
    return {
        "videos_sampled": len(texts_by_video),
        "comments_analysed": total,
        "share_mentioning": {k: round(counts[k] / total, 3) if total else 0.0 for k in COMMENT_LEXICON},
        "note": "Keyword counts only — no comment text is stored.",
    }


# ── the main summary ──────────────────────────────────────────────────────


def summarize(records: list[dict], min_age_days: float = 7) -> dict[str, Any]:
    usable = [r for r in records if r["age_days"] >= min_age_days]
    if len(usable) < 8:
        return {"enough_data": False, "usable_videos": len(usable),
                "message": "Too few videos to analyse — add more query_templates in config.yaml."}

    vpd = [r["views_per_day"] for r in usable]
    top_cut = percentile(vpd, 0.75)
    top = [r for r in usable if r["views_per_day"] >= top_cut]
    rest = [r for r in usable if r["views_per_day"] < top_cut]
    long_form = [r for r in usable if r["duration_s"] > 60]
    top_long = [r for r in top if r["duration_s"] > 60]

    def dur_stats(rows: list[dict]) -> dict:
        ds = [r["duration_s"] for r in rows]
        return {"n": len(rows), "p25_s": _round_to(percentile(ds, .25), 5),
                "median_s": _round_to(percentile(ds, .5), 5), "p75_s": _round_to(percentile(ds, .75), 5)}

    # Duration buckets: how crowded vs how well they perform
    buckets = []
    overall_med_vpd = _med(vpd)
    for label, lo, hi in DURATION_BUCKETS:
        rows = [r for r in usable if lo < r["duration_s"] <= hi or (lo == 0 and r["duration_s"] <= hi)]
        if not rows:
            buckets.append({"bucket": label, "count": 0, "share": 0.0, "median_vpd": None, "vpd_vs_overall": None})
            continue
        mv = _med([r["views_per_day"] for r in rows])
        buckets.append({
            "bucket": label, "count": len(rows), "share": round(len(rows) / len(usable), 3),
            "median_vpd": round(mv, 1),
            "vpd_vs_overall": round(mv / overall_med_vpd, 2) if overall_med_vpd else None,
        })

    # Title feature lift: how much more common a pattern is among top videos
    def share(rows, f):
        return sum(1 for r in rows if r.get(f)) / len(rows) if rows else 0.0

    features = []
    for f in BOOL_FEATURES:
        s_top, s_rest, s_all = share(top, f), share(rest, f), share(usable, f)
        lift = (s_top + 0.02) / (s_rest + 0.02)
        features.append({"feature": f, "share_all": round(s_all, 3), "share_top": round(s_top, 3),
                         "share_rest": round(s_rest, 3), "lift_top_vs_rest": round(lift, 2)})
    features.sort(key=lambda x: -x["lift_top_vs_rest"])

    brand_terms = detect_brand_terms(records)
    banned = set(brand_terms) | STOPWORDS
    top_words = Counter(t for r in top for t in set(_tokens(r["title"])) if t not in banned)
    all_words = Counter(t for r in usable for t in set(_tokens(r["title"])) if t not in banned)
    words = [{"word": w, "in_top_titles": c, "in_all_titles": all_words[w],
              "top_concentration": round(c / all_words[w], 2)}
             for w, c in top_words.most_common(40) if c >= 2][:25]

    # Market structure
    ch_views: Counter = Counter()
    for r in usable:
        ch_views[r["channel_id"]] += r["views"]
    total_views = sum(ch_views.values()) or 1
    top5_share = sum(v for _, v in ch_views.most_common(5)) / total_views

    recent_top = [r for r in top if r["age_days"] <= 365]
    mfk_known = [r for r in usable if r["made_for_kids"] is not None]

    return {
        "enough_data": True,
        "usable_videos": len(usable),
        "distinct_channels": len(ch_views),
        "top_group_threshold_vpd": round(top_cut, 1),
        "views_per_day": {"median_all": round(overall_med_vpd, 1), "median_top": round(_med([r["views_per_day"] for r in top]), 1)},
        "duration": {
            "all": dur_stats(usable), "top": dur_stats(top),
            "long_form_all": dur_stats(long_form), "long_form_top": dur_stats(top_long),
            "shorts_share": round(sum(1 for r in usable if r["duration_s"] <= 60) / len(usable), 3),
            "spearman_duration_vs_vpd_long_form": spearman(
                [r["duration_s"] for r in long_form], [r["views_per_day"] for r in long_form]),
        },
        "duration_buckets": buckets,
        "engagement": {
            "median_like_rate_all": _med([r["like_rate"] for r in usable]),
            "median_like_rate_top": _med([r["like_rate"] for r in top]),
            "median_comment_rate_all": _med([r["comment_rate"] for r in usable]),
            "share_with_comments_enabled": round(sum(1 for r in usable if r["comments_enabled"]) / len(usable), 3),
        },
        "made_for_kids_share": round(sum(1 for r in mfk_known if r["made_for_kids"]) / len(mfk_known), 3) if mfk_known else None,
        "languages": dict(Counter(r["language"] for r in usable).most_common(6)),
        "freshness": {
            "median_age_days_top": round(_med([r["age_days"] for r in top]), 0),
            "share_of_top_uploaded_last_year": round(len(recent_top) / len(top), 3),
        },
        "market": {"top5_channels_share_of_views": round(top5_share, 3)},
        "title": {
            "median_len_chars_top": _med([r["len_chars"] for r in top]),
            "median_len_words_top": _med([r["len_words"] for r in top]),
            "feature_lift": features,
            "common_words_in_top_titles": words,
        },
        "brand_terms": brand_terms,
    }


def find_gaps(summary: dict) -> list[str]:
    """Rule-based opportunities. Each gap says WHY it was flagged."""
    if not summary.get("enough_data"):
        return []
    gaps: list[str] = []
    for b in summary["duration_buckets"]:
        if b["count"] >= 3 and (b["vpd_vs_overall"] or 0) >= 1.3 and b["share"] <= 0.15:
            gaps.append(f"Length {b['bucket']}: only {b['share']:.0%} of videos, but they earn "
                        f"{b['vpd_vs_overall']}× the typical views/day — under-served.")
    for f in summary["title"]["feature_lift"]:
        if f["lift_top_vs_rest"] >= 1.4 and f["share_all"] <= 0.25:
            gaps.append(f"Title pattern '{f['feature']}' is used by only {f['share_all']:.0%} of videos "
                        f"but is {f['lift_top_vs_rest']}× more common among top performers.")
    story = next((f for f in summary["title"]["feature_lift"] if f["feature"] == "kw_story"), None)
    if story and story["share_all"] < 0.15:
        gaps.append(f"Few videos frame the lesson as a story ({story['share_all']:.0%}) — "
                    "a story-led video is a clear way to stand out.")
    fresh = summary["freshness"]["share_of_top_uploaded_last_year"]
    if fresh < 0.25:
        gaps.append(f"Only {fresh:.0%} of top videos are from the last year — the niche is dominated "
                    "by older, established videos; expect slow growth and focus on a distinct angle.")
    elif fresh > 0.5:
        gaps.append(f"{fresh:.0%} of top videos are less than a year old — new videos CAN break through here.")
    if summary["market"]["top5_channels_share_of_views"] > 0.7:
        gaps.append("A few big channels take most of the views — compete on originality, not imitation.")
    return gaps
