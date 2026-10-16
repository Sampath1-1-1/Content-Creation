# Licence ledger

Every model, library, font, soundfont and asset used by the studio, with its licence.
Rule: only commercial-use licences (Apache-2.0, MIT, BSD, ISC, OpenRAIL, CC0, OFL; LGPL/GPL only for
separate tools/libraries whose licence does not cover the videos we make). Nothing non-commercial.

Status: **in use** = installed by `requirements.txt` today · **planned** = added when its stage is built
(licence re-checked at that moment, from the project's own LICENSE file).

## Python packages

| Component | Licence | Used for | Status |
|---|---|---|---|
| PyYAML | MIT | reading config.yaml | in use |
| python-dotenv | BSD-3-Clause | reading .env keys | in use |
| tzdata | Apache-2.0 | time zones on Windows (quota resets) | in use |
| google-api-python-client | Apache-2.0 | YouTube Data API (metadata only) | in use |
| google-genai | Apache-2.0 | Gemini API SDK | in use |
| pytest | MIT | tests (development only) | in use |
| kokoro (Kokoro-82M weights + code) | Apache-2.0 | narration / chant TTS | planned (Stage 4) |
| espeak-ng | GPL-3.0 | phonemes for Kokoro, run as a separate tool; does not affect audio output | planned (Stage 4) |
| faster-whisper | MIT | lyric verification, word timestamps | planned (Stages 4–5, 8) |
| Whisper model weights | MIT | (as above) | planned |
| librosa | ISC | beat detection | planned (Stage 5) |
| pyloudnorm | MIT | loudness (LUFS) | planned (Stage 4) |
| pretty_midi / mido | MIT | composing the fallback melody | planned (Stage 4) |
| numpy | BSD-3-Clause | numbers / image arrays | planned |
| Pillow | MIT-CMU (HPND) | drawing frames | planned (Stage 6) |
| opencv-python | Apache-2.0 | quality checks | planned (Stage 8) |
| pytesseract | Apache-2.0 | OCR wrapper | planned (Stage 8) |
| SVG rasteriser (resvg or skia-python) | to verify | turning character SVGs into PNG sprites once | planned (Stage 3) |
| kaggle (official API client) | Apache-2.0 | pushing notebooks / fetching results | planned (Stage 4) |

## External programs

| Component | Licence | Used for | Status |
|---|---|---|---|
| FFmpeg (gyan.dev build) | GPL-3.0 build of an LGPL/GPL project; used as a tool, output not covered | encoding, captions, loudness checks | planned |
| Tesseract OCR | Apache-2.0 | reading numerals off frames (QA) | planned |
| FluidSynth | LGPL-2.1 | rendering the MIDI melody | planned |

## AI models

| Model | Licence | Used for | Status |
|---|---|---|---|
| ACE-Step (v1 / 1.5) | Apache-2.0 | sung song on Kaggle (primary) | planned (Stage 4) |
| YuE — original v1 models (`m-a-p/YuE-s1-*`) | Apache-2.0 | sung song on Kaggle (backup) | planned |
| ~~YuE2~~ | CC BY-NC 4.0 reported — **non-commercial** | — | **excluded** |
| ~~SongGeneration / SongGeneration 2 (Tencent)~~ | academic/research only, no commercial use | — | **excluded** |
| Gemini (API, free tier) | Google API terms (service, not a downloaded model) | scripts, lyrics, analysis | in use — terms to be re-confirmed |

## Fonts, soundfonts, art

| Asset | Licence | Used for | Status |
|---|---|---|---|
| Andika or Fredoka | SIL OFL 1.1 | numerals and on-screen text | planned (Stage 6) |
| FluidR3_GM soundfont | MIT (to verify at download) | instrument sounds for fallback song | planned (Stage 4) |
| Character art (teacher + 5 children) | original, created in this project | characters | planned (Stage 3) |

## Data

| Data | Rule |
|---|---|
| YouTube API metadata | Statistics only; cached ≤ 30 days; never download video/audio/thumbnails; comment text never stored. |
| Synthetic sample (`tests/fixtures/youtube_sample.json`) | Invented by this project — no real videos. |
