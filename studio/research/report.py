"""Write the research report as JSON (for Stage 2), Markdown and HTML (for you)."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _mmss(seconds: float | None) -> str:
    if seconds is None:
        return "–"
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0%}"


def _num(x: float | None, digits: int = 0) -> str:
    if x is None:
        return "–"
    return f"{x:,.{digits}f}"


def headline_findings(report: dict) -> list[str]:
    s = report["measured"]
    if not s.get("enough_data"):
        return [s.get("message", "Not enough data.")]
    d = s["duration"]
    out = [
        f"Analysed {s['usable_videos']} videos from {s['distinct_channels']} channels.",
        f"Top performers (long-form) are typically {_mmss(d['long_form_top']['p25_s'])}–"
        f"{_mmss(d['long_form_top']['p75_s'])} long (median {_mmss(d['long_form_top']['median_s'])}).",
        f"Shorts make up {_pct(d['shorts_share'])} of results.",
    ]
    rho = d.get("spearman_duration_vs_vpd_long_form")
    if rho is not None:
        trend = "longer videos tend to do better" if rho > 0.2 else (
            "shorter videos tend to do better" if rho < -0.2 else "length barely matters on its own")
        out.append(f"Length vs views/day correlation: {rho:+.2f} — {trend}.")
    regions = report.get("regions") or []
    if len(regions) > 1:
        out[0] = (f"Analysed {s['usable_videos']} videos from {s['distinct_channels']} channels "
                  f"across markets: {', '.join('Overall' if r == 'GLOBAL' else r for r in regions)}.")
    if s.get("made_for_kids_share") is not None:
        out.append(f"{_pct(s['made_for_kids_share'])} are marked Made for Kids "
                   f"(comments enabled on {_pct(s['engagement']['share_with_comments_enabled'])}).")
    out.append(f"{_pct(s['freshness']['share_of_top_uploaded_last_year'])} of top videos were uploaded "
               f"in the last year; top 5 channels hold {_pct(s['market']['top5_channels_share_of_views'])} of views.")
    return out


def write_json(report: dict, path: Path) -> None:
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def write_markdown(report: dict, path: Path) -> None:
    s = report["measured"]
    lines = [f"# Research report — {report['topic']}", "",
             f"*Generated {report['generated_at']} · data source: **{report['data_source']}** · "
             f"YouTube quota used: {report['quota_used_units']} units*", ""]
    if report["data_source"] != "youtube_api":
        lines += ["> ⚠️ DEMO DATA — synthetic sample, not real YouTube videos.", ""]
    lines += ["## Headline findings (measured)", ""] + [f"- {x}" for x in report["headline_findings"]] + [""]
    rrows = _region_rows(report)
    if rrows:
        lines += ["## Markets compared (measured)", "", "| " + " | ".join(_REGION_HEAD) + " |",
                  "|" + "---|" * len(_REGION_HEAD)] + ["| " + " | ".join(r) + " |" for r in rrows] + [""]
    if s.get("enough_data"):
        lines += ["## Recommended length (measured)", "",
                  f"**{_mmss(report['recommendations']['length_s'][0])} – {_mmss(report['recommendations']['length_s'][1])}**", "",
                  "## Duration buckets (measured)", "", "| Length | Videos | Share | Median views/day | vs typical |",
                  "|---|---|---|---|---|"]
        for b in s["duration_buckets"]:
            lines.append(f"| {b['bucket']} | {b['count']} | {_pct(b['share'])} | {_num(b['median_vpd'])} | "
                         f"{'–' if b['vpd_vs_overall'] is None else str(b['vpd_vs_overall']) + '×'} |")
        lines += ["", "## Title patterns: top vs rest (measured)", "", "| Pattern | All | Top 25% | Rest | Lift |",
                  "|---|---|---|---|---|"]
        for f in s["title"]["feature_lift"][:12]:
            lines.append(f"| {f['feature']} | {_pct(f['share_all'])} | {_pct(f['share_top'])} | "
                         f"{_pct(f['share_rest'])} | {f['lift_top_vs_rest']}× |")
        lines += ["", "## Gaps & opportunities", ""] + [f"- {g}" for g in report["gaps"]] + [""]
    c = report.get("comments") or {}
    if c.get("comments_analysed"):
        lines += ["## What comments mention (share of comments, measured)", ""]
        lines += [f"- {k}: {_pct(v)}" for k, v in c["share_mentioning"].items()]
        lines += [""]
    else:
        lines += ["## Comments", "", "No comments available (Made for Kids videos have comments switched off).", ""]
    if report.get("llm_recommendations"):
        lines += ["## Gemini's interpretation (inferred from the numbers above)", "",
                  "```json", json.dumps(report["llm_recommendations"], indent=2, ensure_ascii=False), "```", ""]
    lines += ["## Starting defaults (INFERRED — not measurable from metadata)", "", "```json",
              json.dumps(report["inferred_guidance"], indent=2, ensure_ascii=False), "```", "",
              "## Never use these words (brand / character / channel names detected)", "",
              ", ".join(report["brand_terms_never_use"]) or "(none detected)", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


_CSS = """
:root{--bg:#fffdf7;--fg:#1f2430;--muted:#6b7280;--card:#ffffff;--line:#e8e2d4;--accent:#2f6fde;--warn:#b45309}
@media (prefers-color-scheme:dark){:root{--bg:#15171c;--fg:#e8eaf0;--muted:#9aa3b2;--card:#1d2027;--line:#2c313b;--accent:#7aa7ff;--warn:#f59e0b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 10px}
.meta{color:var(--muted);font-size:13px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}
.big{font-size:30px;font-weight:700;color:var(--accent)}.warn{color:var(--warn);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600}.wrap{overflow-x:auto}.tag{display:inline-block;font-size:12px;padding:1px 8px;border-radius:99px;border:1px solid var(--line);color:var(--muted)}
ul{padding-left:20px}pre{white-space:pre-wrap;font-size:13px}
"""


def write_html(report: dict, path: Path) -> None:
    e = html.escape
    s = report["measured"]
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
             f"content='width=device-width,initial-scale=1'><title>Research — {e(report['topic'])}</title>"
             f"<style>{_CSS}</style></head><body><main>",
             f"<h1>Research report — {e(report['topic'])}</h1>",
             f"<div class='meta'>Generated {e(report['generated_at'])} · source: {e(report['data_source'])} · "
             f"YouTube quota used: {report['quota_used_units']} units</div>"]
    if report["data_source"] != "youtube_api":
        parts.append("<p class='warn'>⚠️ DEMO DATA — synthetic sample, not real YouTube videos.</p>")
    parts.append("<h2>Headline findings <span class='tag'>measured</span></h2><div class='card'><ul>"
                 + "".join(f"<li>{e(x)}</li>" for x in report["headline_findings"]) + "</ul></div>")
    rrows = _region_rows(report)
    if rrows:
        parts.append("<h2>Markets compared <span class='tag'>measured</span></h2><div class='card wrap'><table><tr>"
                     + "".join(f"<th>{e(h)}</th>" for h in _REGION_HEAD) + "</tr>"
                     + "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rrows)
                     + "</table><div class='meta'>Everything below combines all markets.</div></div>")
    if s.get("enough_data"):
        lo, hi = report["recommendations"]["length_s"]
        parts.append(f"<h2>Recommended length <span class='tag'>measured</span></h2><div class='card'>"
                     f"<div class='big'>{_mmss(lo)} – {_mmss(hi)}</div>"
                     f"<div class='meta'>Middle half of top-performing long-form videos (views/day).</div></div>")
        rows = "".join(
            f"<tr><td>{e(b['bucket'])}</td><td>{b['count']}</td><td>{_pct(b['share'])}</td>"
            f"<td>{_num(b['median_vpd'])}</td><td>{'–' if b['vpd_vs_overall'] is None else str(b['vpd_vs_overall']) + '×'}</td></tr>"
            for b in s["duration_buckets"])
        parts.append("<h2>Duration buckets <span class='tag'>measured</span></h2><div class='card wrap'><table>"
                     "<tr><th>Length</th><th>Videos</th><th>Share</th><th>Median views/day</th><th>vs typical</th></tr>"
                     f"{rows}</table></div>")
        rows = "".join(
            f"<tr><td>{e(f['feature'])}</td><td>{_pct(f['share_all'])}</td><td>{_pct(f['share_top'])}</td>"
            f"<td>{_pct(f['share_rest'])}</td><td>{f['lift_top_vs_rest']}×</td></tr>"
            for f in s["title"]["feature_lift"][:12])
        parts.append("<h2>Title patterns: top 25% vs rest <span class='tag'>measured</span></h2>"
                     "<div class='card wrap'><table><tr><th>Pattern</th><th>All</th><th>Top 25%</th><th>Rest</th>"
                     f"<th>Lift</th></tr>{rows}</table></div>")
        parts.append("<h2>Gaps &amp; opportunities</h2><div class='card'><ul>"
                     + ("".join(f"<li>{e(g)}</li>" for g in report["gaps"]) or "<li>No clear gaps detected.</li>")
                     + "</ul></div>")
    c = report.get("comments") or {}
    if c.get("comments_analysed"):
        rows = "".join(f"<tr><td>{e(k)}</td><td>{_pct(v)}</td></tr>" for k, v in c["share_mentioning"].items())
        parts.append(f"<h2>What comments mention <span class='tag'>measured</span></h2><div class='card wrap'>"
                     f"<div class='meta'>{c['comments_analysed']} comments from {c['videos_sampled']} videos · "
                     f"keyword counts only, no text stored</div><table>{rows}</table></div>")
    else:
        parts.append("<h2>Comments</h2><div class='card'>No comments available — Made for Kids videos have "
                     "comments switched off.</div>")
    if report.get("llm_recommendations"):
        parts.append("<h2>Gemini's interpretation <span class='tag'>inferred</span></h2><div class='card'><pre>"
                     + e(json.dumps(report["llm_recommendations"], indent=2, ensure_ascii=False)) + "</pre></div>")
    parts.append("<h2>Starting defaults <span class='tag'>inferred — not measurable</span></h2><div class='card'><pre>"
                 + e(json.dumps(report["inferred_guidance"], indent=2, ensure_ascii=False)) + "</pre></div>")
    parts.append("<h2>Never use these words</h2><div class='card'><div class='meta'>Detected channel / character / "
                 "brand names. Stage 2 blocks them from every prompt and script.</div><p>"
                 + e(", ".join(report["brand_terms_never_use"]) or "(none detected)") + "</p></div>")
    ref = report.get("reference_top_videos") or []
    if ref:
        rows = "".join(
            f"<tr><td>{e(r['title'])}</td><td>{_mmss(r['duration_s'])}</td><td>{_num(r['views_per_day'])}</td>"
            f"<td>{_num(r['age_days'])}</td></tr>" for r in ref)
        parts.append("<h2>Top videos by views/day <span class='tag'>reference only — never copy</span></h2>"
                     "<div class='card wrap'><table><tr><th>Title</th><th>Length</th><th>Views/day</th>"
                     f"<th>Age (days)</th></tr>{rows}</table></div>")
    parts.append("</main></body></html>")
    path.write_text("".join(parts), encoding="utf-8")


def region_snapshot(summary: dict) -> dict[str, Any]:
    """The few numbers worth comparing between markets."""
    if not summary.get("enough_data"):
        return {"enough_data": False, "usable_videos": summary.get("usable_videos", 0)}
    lt = summary["duration"]["long_form_top"]
    return {
        "enough_data": True,
        "usable_videos": summary["usable_videos"],
        "recommended_length_s": [lt["p25_s"], lt["p75_s"]],
        "median_top_length_s": lt["median_s"],
        "shorts_share": summary["duration"]["shorts_share"],
        "made_for_kids_share": summary.get("made_for_kids_share"),
        "median_vpd_top": summary["views_per_day"]["median_top"],
        "top_uploaded_last_year": summary["freshness"]["share_of_top_uploaded_last_year"],
        "top5_channels_share": summary["market"]["top5_channels_share_of_views"],
        "best_title_patterns": [f["feature"] for f in summary["title"]["feature_lift"][:3]],
    }


def _region_rows(report: dict) -> list[list[str]]:
    rows = []
    for name, s in (report.get("by_region") or {}).items():
        label = "Overall (no country filter)" if name == "GLOBAL" else name
        if not s.get("enough_data"):
            rows.append([label, str(s.get("usable_videos", 0)), "not enough data", "–", "–", "–", "–"])
            continue
        lo, hi = s["recommended_length_s"]
        rows.append([label, str(s["usable_videos"]), f"{_mmss(lo)}–{_mmss(hi)}", _num(s["median_vpd_top"]),
                     _pct(s["shorts_share"]), _pct(s["top_uploaded_last_year"]), _pct(s["top5_channels_share"])])
    return rows


_REGION_HEAD = ["Market", "Videos", "Best length (top 25%)", "Top views/day", "Shorts",
                "Top from last year", "Top-5 channel share"]


def build_report(*, topic: str, generated_at: str, data_source: str, queries: list[str], quota_used: int,
                 summary: dict, gaps: list[str], comments: dict | None, inferred: dict,
                 llm: dict | None, reference_top: list[dict], regions: list[str] | None = None,
                 by_region: dict | None = None) -> dict[str, Any]:
    rec_len = None
    if summary.get("enough_data"):
        lt = summary["duration"]["long_form_top"]
        rec_len = [lt["p25_s"], lt["p75_s"]]
    report = {
        "topic": topic,
        "generated_at": generated_at,
        "data_source": data_source,
        "queries": queries,
        "regions": regions or [],
        "by_region": by_region or {},
        "quota_used_units": quota_used,
        "measured": summary,
        "gaps": gaps,
        "comments": comments,
        "inferred_guidance": inferred,
        "llm_recommendations": llm,
        "recommendations": {"length_s": rec_len},
        "brand_terms_never_use": summary.get("brand_terms", []),
        "reference_top_videos": reference_top,
    }
    report["headline_findings"] = headline_findings(report)
    return report
