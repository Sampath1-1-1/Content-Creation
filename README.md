# Kids Video Studio

Free, copyright-safe pipeline that turns a topic (e.g. "numbers 1 to 10") into an original,
upload-ready kids' educational video — on a laptop with no GPU.

- **Setup (Windows):** [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md)
- **Design:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · **Licences:** [docs/LICENCES.md](docs/LICENCES.md)
- **Problems?** [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## Status

| Stage | Status |
|---|---|
| 1 Research (patterns only) | ✅ built — waiting for your test with real API keys |
| 2 Creative plan + Gate 1 | next |
| 3–9 | not built yet |

## Commands

```bat
python studio.py doctor --online                       :: check setup + keys
python studio.py --topic "numbers 1 to 10"            :: run / resume the pipeline
python studio.py --topic "numbers 1 to 10" --only-stage 1
python studio.py --topic "numbers 1 to 10" --preview  :: fast low-res test mode
python studio.py --topic "numbers 1 to 10" --from-stage 4 --force
python studio.py status --topic "numbers 1 to 10"     :: what's finished
python studio.py quota                                :: free quota used today
python studio.py --topic "numbers 1 to 10" --fixture tests/fixtures/youtube_sample.json  :: offline demo
python -m pytest                                      :: run tests
```

**Resume:** if a run stops (error, Ctrl+C, quota), run the same command again — finished stages are skipped.

## Stage 1 – Research

Uses the YouTube Data API to collect **statistics only** (views, likes, duration, age, title patterns,
Made-for-Kids share, comment keyword counts). Never downloads videos, audio or thumbnails; never stores
comment text; API data is cached at most 30 days. Output in `projects/<topic>/01_research/`:

- `research_report.html` — read this (recommended length, buckets, title patterns, gaps)
- `research.json` — used by Stage 2
- `prompts/` — every Gemini prompt + answer (proof of originality)

Detected channel/character names go on a "never use" list that later stages enforce.

## Safety rules built in
100% free tools · commercial licences only · no copying of other creators' content · no voice cloning ·
prompts never name existing characters/shows · quota tracked and cached · keys only in `.env` (repo is public).
