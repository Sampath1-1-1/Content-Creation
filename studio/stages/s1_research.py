"""Stage 1 – Research (statistics and patterns only).

Flow:
  1. Build search queries from the topic (config.research.query_templates).
  2. Estimate quota cost and stop early if today's free quota isn't enough.
  3. Search → collect unique video IDs → fetch their metadata + channel stats.
  4. Sample top comments (where enabled), turn them into keyword counts, discard text.
  5. Compute statistics, find gaps, (optionally) ask Gemini to interpret the numbers.
  6. Save research.json (for Stage 2) + research_report.md/.html (for you).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..core.config import get_secret
from ..core.context import RunContext
from ..core.llm import GeminiClient
from ..core.log import get_logger
from ..core.paths import stage_dir
from ..core.pipeline import Stage
from ..research import analysis, report
from ..research.guidance import INFERRED_GUIDANCE_2_TO_4
from ..research.youtube_client import UNIT_COST, FixtureYouTubeClient, YouTubeResearchClient

log = get_logger("s1")


def build_queries(topic: str, templates: list[str]) -> list[str]:
    seen, out = set(), []
    for t in templates:
        q = " ".join(t.replace("{topic}", topic.strip()).split())
        if q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


def region_list(rc: dict) -> list[str]:
    """Markets to study. 'GLOBAL' means no country filter. Old configs used region_code."""
    regions = rc.get("regions") or [rc.get("region_code", "GLOBAL")]
    out = []
    for r in regions:
        r = str(r).strip().upper()
        if r and r not in out:
            out.append(r)
    return out or ["GLOBAL"]


def estimate_units(n_queries: int, n_orders: int, max_videos: int, comment_videos: int,
                   n_regions: int = 1) -> int:
    searches = n_queries * n_orders * n_regions * UNIT_COST["search"]
    video_batches = -(-max_videos // 50)
    channel_batches = video_batches  # at most one channel per video
    return searches + video_batches + channel_batches + comment_videos


def _outputs(ctx: RunContext) -> list[Path]:
    d = ctx.project_dir / "01_research"
    return [d / "research.json", d / "research_report.md", d / "research_report.html"]


def _fingerprint(ctx: RunContext) -> dict:
    return {"research": ctx.cfg.get("research", {}), "fixture": ctx.options.get("fixture"),
            "gemini_models": ctx.cfg.get_path("gemini.models")}


def _make_client(ctx: RunContext):
    fixture = ctx.options.get("fixture")
    if fixture:
        log.info(f"  Using OFFLINE DEMO data from {fixture} (synthetic, no API calls).")
        return FixtureYouTubeClient(Path(fixture)), "synthetic_fixture"
    rc = ctx.cfg.get("research", {})
    client = YouTubeResearchClient(
        api_key=get_secret("YOUTUBE_API_KEY"), cache_root=ctx.cache_root, quota=ctx.quota,
        retry_cfg=ctx.cfg.get("retries", {}), ttl_days=float(rc.get("cache_ttl_days", 30)))
    return client, "youtube_api"


def _llm_interpretation(ctx: RunContext, summary: dict, gaps: list[str], comments: dict | None,
                        out_dir: Path, by_region: dict | None = None) -> dict | None:
    if not ctx.cfg.get_path("research.llm_summary", True) or ctx.options.get("fixture"):
        return None
    if not get_secret("GEMINI_API_KEY", required=False):
        log.warning("  GEMINI_API_KEY not set — skipping Gemini interpretation (numbers are still complete).")
        return None
    # Only aggregate numbers go to Gemini: no titles, no channel names.
    payload = {k: summary[k] for k in ("duration", "duration_buckets", "engagement", "made_for_kids_share",
                                       "freshness", "market", "views_per_day")}
    payload["title_patterns"] = summary["title"]["feature_lift"][:12]
    payload["frequent_title_words"] = [w["word"] for w in summary["title"]["common_words_in_top_titles"]]
    payload["gaps_found"] = gaps
    payload["comment_signals"] = (comments or {}).get("share_mentioning")
    if by_region:
        payload["by_market"] = by_region  # GLOBAL = no country filter; US; IN = India
    prompt = f"""You are a children's media researcher helping plan an ORIGINAL educational video
for ages {ctx.cfg.get_path('project.audience_age', '2-4')} about: "{ctx.topic}".

Below are AGGREGATE statistics about existing YouTube videos on this topic (no titles,
no channel names). Interpret them. Do NOT name any existing channel, show, character,
studio, artist or song. Be specific and practical. Where the numbers don't support a
claim, say it is a guess.

STATISTICS (JSON):
{json.dumps(payload, ensure_ascii=False)}

Reply with JSON only, using exactly these keys:
{{
  "recommended_length_seconds": [min, max],
  "length_reasoning": "...",
  "recommended_structure": ["segment 1 ...", "segment 2 ...", "..."],
  "hook_ideas": ["...", "...", "..."],
  "title_style_advice": "... (patterns only — never copy titles)",
  "differentiation_opportunities": ["...", "...", "..."],
  "market_differences": "how the markets in by_market differ, and one plan that works for all of them",
  "things_to_avoid": ["...", "..."],
  "confidence_notes": "what is measured vs guessed"
}}"""
    client = GeminiClient(ctx.cfg, ctx.cache_root, ctx.quota, prompts_dir=out_dir / "prompts")
    log.info("  Asking Gemini to interpret the statistics…")
    return client.generate(prompt, purpose="research_interpretation",
                           banned_terms=set(summary.get("brand_terms", [])))


def run(ctx: RunContext) -> dict:
    rc = ctx.cfg.get("research", {})
    out_dir = stage_dir(ctx.project_dir, 1)
    queries = build_queries(ctx.topic, rc.get("query_templates", ["{topic}"]))
    orders = rc.get("search_orders", ["relevance"])
    max_videos = int(rc.get("max_videos", 250))
    comment_videos = int(rc.get("comment_videos", 15))

    regions = region_list(rc)
    client, source = _make_client(ctx)
    used_before = ctx.quota.used("youtube")
    if source == "youtube_api":
        est = estimate_units(len(queries), len(orders), max_videos, comment_videos, n_regions=len(regions))
        log.info(f"  {len(queries)} queries × {len(orders)} orders × {len(regions)} markets "
                 f"({', '.join(regions)}) · estimated cost ≤ {est} units (cached results cost 0). "
                 f"Remaining today: {ctx.quota.remaining('youtube')}")

    # 1) search each market; every market gets a fair share of the video cap
    per_region_cap = max(1, max_videos // len(regions))
    region_ids: dict[str, list[str]] = {}
    for region in regions:
        found_ids: list[str] = []
        for q in queries:
            for order in orders:
                found = client.search_ids(q, order, int(rc.get("results_per_search", 50)),
                                          region, rc.get("relevance_language", "en"))
                found_ids.extend(i for i in found if i not in found_ids)
        region_ids[region] = found_ids[:per_region_cap]
        log.info(f"  market {region}: {len(found_ids)} unique videos found, using {len(region_ids[region])}")
    ids: list[str] = []
    for region in regions:
        ids.extend(i for i in region_ids[region] if i not in ids)

    # 2) metadata
    videos = client.videos(ids)
    channels = client.channels([v["snippet"]["channelId"] for v in videos if "snippet" in v])
    channels_by_id = {c["id"]: c for c in channels}
    now = datetime.now(timezone.utc)
    records = [r for v in videos if (r := analysis.record_from_api(v, channels_by_id, now))]
    log.info(f"  Fetched metadata for {len(records)} videos from {len(channels_by_id)} channels.")

    # 3) statistics: overall (all markets combined) + each market separately
    min_age = float(rc.get("min_age_days", 7))
    summary = analysis.summarize(records, min_age_days=min_age)
    gaps = analysis.find_gaps(summary)
    by_region = {}
    if len(regions) > 1:
        for region in regions:
            wanted = set(region_ids[region])
            by_region[region] = report.region_snapshot(
                analysis.summarize([r for r in records if r["id"] in wanted], min_age_days=min_age))
    # brand terms from every market go on the never-use list
    summary["brand_terms"] = analysis.detect_brand_terms(records)

    # 4) comments (keyword counts only)
    comments = None
    if summary.get("enough_data") and comment_videos > 0:
        candidates = sorted((r for r in records if r["comments_enabled"] and (r["comments"] or 0) > 0),
                            key=lambda r: -r["views_per_day"])[:comment_videos]
        texts = {}
        for r in candidates:
            texts[r["id"]] = client.comment_texts(r["id"], int(rc.get("comments_per_video", 20)))
        comments = analysis.analyse_comments(texts)
        del texts  # comment text is never written anywhere

    # 5) Gemini interpretation (optional)
    llm = (_llm_interpretation(ctx, summary, gaps, comments, out_dir, by_region)
           if summary.get("enough_data") else None)

    # 6) report
    reference = [{"title": r["title"], "duration_s": r["duration_s"], "views_per_day": r["views_per_day"],
                  "age_days": r["age_days"]}
                 for r in sorted(records, key=lambda r: -r["views_per_day"])[:15]]
    rep = report.build_report(
        topic=ctx.topic, generated_at=now.isoformat(timespec="seconds"), data_source=source,
        queries=queries, quota_used=ctx.quota.used("youtube") - used_before, summary=summary, gaps=gaps,
        comments=comments, inferred=INFERRED_GUIDANCE_2_TO_4, llm=llm, reference_top=reference,
        regions=regions, by_region=by_region)
    json_p, md_p, html_p = _outputs(ctx)
    report.write_json(rep, json_p)
    report.write_markdown(rep, md_p)
    report.write_html(rep, html_p)

    log.info("\n  📊 Headline findings:")
    for line in rep["headline_findings"]:
        log.info(f"   • {line}")
    log.info(f"\n  Report: {html_p}")
    return {"videos": len(records), "source": source, "quota_used": rep["quota_used_units"]}


STAGE = Stage(1, "s1_research", "Research (patterns only)", run=run, fingerprint=_fingerprint, outputs=_outputs)
