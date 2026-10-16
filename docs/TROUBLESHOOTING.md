# Troubleshooting

Run `python studio.py doctor --online` first — it checks most things and says how to fix them.
Full details of any run are in `projects/<topic>/logs/run.log`.

| Problem | Fix |
|---|---|
| `'python' is not recognized` | Install Python 3.11 with "Add to PATH", reopen Command Prompt. Or use `py -3.11`. |
| `No module named ...` | Activate the venv (`.venv\Scripts\activate`), then `pip install -r requirements.txt`. |
| PowerShell: "running scripts is disabled" | Use Command Prompt instead, or run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `YOUTUBE_API_KEY is missing` / `GEMINI_API_KEY is missing` | Create `.env` from `.env.example` and paste the keys (docs/SETUP_WINDOWS.md steps 6–8). |
| YouTube "keyInvalid" / "accessNotConfigured" | Enable **YouTube Data API v3** in the same Google Cloud project as the key; check the key's API restriction. |
| "Not enough free youtube quota today" | Wait for the reset at midnight Pacific (≈12:30 PM India time in summer, 1:30 PM in winter). Cached results cost nothing on re-run. |
| Gemini "not available for your key" (404) | `python studio.py doctor --online` lists your models; put free "flash" ones in `gemini.models` in config.yaml. |
| Gemini daily limit reached | Wait for the reset, or add another free model to `gemini.models`. |
| `ffmpeg` not found | `winget install Gyan.FFmpeg`, then reopen Command Prompt. |
| `tesseract` not found | Add `C:\Program Files\Tesseract-OCR` to PATH (SETUP_WINDOWS.md). |
| Out of memory | Close browsers/other apps, use `--preview`. |
| Want to redo a stage | Add `--force` (e.g. `--only-stage 1 --force`). Delete `cache\` only if you really want to re-download everything. |
| Strange symbols instead of emoji | Harmless (old console font). Windows Terminal shows them properly. |
