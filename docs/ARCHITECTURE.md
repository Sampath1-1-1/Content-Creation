# Architecture (approved 16 Oct 2026)

## Goal
`python studio.py --topic "numbers 1 to 10"` → an upload-ready MP4 with original recurring characters,
an original song + narration, accurate content, frame-accurate sync and an HTML quality report —
with three human approval gates. 100% free, CPU-only laptop, commercial-use licences only.

## Decisions
- **Language:** English only (YouTube auto-dubbing can add other languages to the *speech* later;
  music-only parts are not dubbed, so videos include real spoken teaching).
- **Audience:** ages 2–4. **Goal:** monetisation (so every video has a distinct story).
- **Format and voice:** decided from Stage 1 research; voice chosen by ear from 3–4 Kokoro samples at Gate 1.
- **Cast:** one teacher + **5 children** (different silhouettes, colours, a pair of glasses; mixed genders and
  skin tones). Each video features the teacher + 1–2 rotating "star" children; whole class only in intro/outro.
  Animals and guests change per video (separate guest library).
- **Characters are hand-designed layered SVGs** (not LLM-drawn), rasterised once to PNG sprites and animated by code.
- **Song:** Kaggle ACE-Step (Apache-2.0) primary, original YuE v1 (Apache-2.0) backup;
  CPU fallback = original MIDI melody + FluidSynth + rhythmic Kokoro chant. SongGeneration and YuE2 excluded (non-commercial).
- **Timing:** for our own TTS / MIDI the word timings are known exactly; Whisper verifies, and aligns Kaggle songs.

## Stages and build order
Build order: 1 Research → 2 Script → 5 Timeline + 6 counting engine (placeholders) → 4 Audio (CPU fallback, then Kaggle)
→ 3 Characters → 6 full animation → 7 Assembly → 8 QA → 9 Publishing.

| # | Stage | Runs on | Output folder |
|---|---|---|---|
| 1 | Research (YouTube metadata stats only) | laptop + API | `01_research/` |
| 2 | Creative plan → **Gate 1** | laptop + Gemini | `02_creative/` |
| 3 | Character bible → **Gate 2** | laptop | `character_library/v1/` |
| 4 | Audio: song, narration, mix | Kaggle GPU (song) / laptop | `04_audio/` |
| 5 | Master timeline (audio = clock) | laptop | `05_timeline/` |
| 6 | Visuals: puppet animation + counting engine | laptop | `06_visuals/` |
| 7 | Assembly: H.264/AAC, SRT, intro/outro | laptop | `07_render/` |
| 8 | Quality checks + HTML report → **Gate 3** | laptop | `08_qa/` |
| 9 | Publishing package (no auto-upload) | laptop + Gemini | `09_publish/` |

## Shared machinery (`studio/core/`)
- `config.py` — one `config.yaml`; `--preview` merges `preview_overrides`.
- `manifest.py` — resume: a stage is skipped if done with the same inputs and its outputs exist.
- `cache.py` — every API response / generated asset cached on disk (YouTube data ≤ 30 days).
- `quota.py` — counts free quota per day (Pacific time, like Google) and stops *before* running out.
- `retry.py` — exponential backoff for rate limits and temporary server errors.
- `llm.py` — Gemini: cached, quota-tracked, model fallback, saves every prompt; blocks prompts containing brand names.
- `gates.py` — approval pages + terminal y/n/later; approvals tied to the exact content approved.
- `doctor.py` — setup checker with fix instructions.

## Folder layout
```
studio.py  config.yaml  .env(.example)  requirements.txt
studio/core/  studio/stages/  studio/research/  (later: audio/ visual/ kaggle/ optional/ai_video/)
character_library/v1/{teacher, kids/kid_01..kid_05, guests}/
assets/{fonts, soundfonts, objects, backgrounds}/
tests/  docs/
projects/<topic>/  cache/      ← local only, git-ignored
```

## Estimated laptop times (i5-1035G1, 12 GB, 3-minute video, final mode)
Research 1–3 min · Script 1–2 min · Audio (CPU) 3–6 min · Timeline 3–6 min · Frames + encode 12–25 min ·
QA 6–10 min → **~30–50 min** plus review. Preview mode ~8–12 min. Kaggle song adds queue time but not laptop time.
