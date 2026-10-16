"""`python studio.py doctor` — checks your setup and explains what's missing."""

from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from .config import ROOT, Config, get_secret

OK, WARN, BAD = "✅", "⚠️ ", "❌"


def _tool_version(exe: str) -> str | None:
    path = shutil.which(exe)
    if not path:
        return None
    try:
        out = subprocess.run([path, "-version" if "ff" in exe else "--version"],
                             capture_output=True, text=True, timeout=15)
        first = (out.stdout or out.stderr).strip().splitlines()
        return first[0][:80] if first else path
    except Exception:  # noqa: BLE001
        return path


def run_doctor(cfg: Config, online: bool = False) -> int:
    problems = 0
    print("\n🩺  Kids Video Studio — setup check\n")

    v = sys.version_info
    py_ok = (3, 10) <= (v.major, v.minor) <= (3, 12)
    print(f"{OK if py_ok else BAD} Python {v.major}.{v.minor}.{v.micro} on {platform.system()}"
          + ("" if py_ok else "  → install Python 3.11 (see docs/SETUP_WINDOWS.md)"))
    problems += not py_ok

    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    print(f"{OK if in_venv else WARN} Virtual environment "
          + ("active" if in_venv else "NOT active  → run .venv\\Scripts\\activate"))

    print("\nPython packages:")
    for mod, pip_name in [("yaml", "PyYAML"), ("dotenv", "python-dotenv"),
                          ("googleapiclient", "google-api-python-client"),
                          ("google.genai", "google-genai"), ("tzdata", "tzdata")]:
        try:
            importlib.import_module(mod)
            print(f"  {OK} {pip_name}")
        except ModuleNotFoundError:
            print(f"  {BAD} {pip_name} missing → pip install -r requirements.txt")
            problems += 1

    print("\nTools (needed from Stage 4 on — fine to install later):")
    for exe, hint in [("ffmpeg", "winget install Gyan.FFmpeg"),
                      ("ffprobe", "comes with FFmpeg"),
                      ("tesseract", "winget install UB-Mannheim.TesseractOCR")]:
        ver = _tool_version(exe)
        print(f"  {OK if ver else WARN} {exe}: {ver or 'not found → ' + hint}")

    print("\nAPI keys (.env file):")
    env_file = ROOT / ".env"
    print(f"  {OK if env_file.exists() else BAD} .env file "
          + ("found" if env_file.exists() else "missing → copy .env.example to .env"))
    problems += not env_file.exists()
    for name in ("GEMINI_API_KEY", "YOUTUBE_API_KEY"):
        present = bool(get_secret(name, required=False))
        print(f"  {OK if present else BAD} {name} " + ("set" if present else "not set"))
        problems += not present

    kaggle_json = Path(os.path.expanduser("~")) / ".kaggle" / "kaggle.json"
    has_kaggle = kaggle_json.exists() or bool(os.environ.get("KAGGLE_USERNAME"))
    print(f"  {OK if has_kaggle else WARN} Kaggle API token "
          + ("found" if has_kaggle else "not found (only needed for Stage 4 sung vocals)"))

    if online:
        print("\nOnline checks:")
        problems += _online_checks()

    print("\n" + ("🎉 All required checks passed!" if problems == 0
                  else f"Found {problems} problem(s). Fix the ❌ items above, then run doctor again."))
    return 0 if problems == 0 else 1


def _online_checks() -> int:
    problems = 0
    yt_key = get_secret("YOUTUBE_API_KEY", required=False)
    if yt_key:
        try:
            from googleapiclient.discovery import build
            yt = build("youtube", "v3", developerKey=yt_key, cache_discovery=False)
            yt.i18nLanguages().list(part="snippet", hl="en").execute()  # costs 1 unit
            print(f"  {OK} YouTube Data API key works")
        except Exception as exc:  # noqa: BLE001
            print(f"  {BAD} YouTube Data API key failed: {str(exc)[:200]}")
            print("     → Check the key, and that 'YouTube Data API v3' is ENABLED in your Google Cloud project.")
            problems += 1

    gm_key = get_secret("GEMINI_API_KEY", required=False)
    if gm_key:
        try:
            from google import genai
            client = genai.Client(api_key=gm_key)
            names = [m.name.replace("models/", "") for m in client.models.list()
                     if "generateContent" in (getattr(m, "supported_actions", None) or [])]
            print(f"  {OK} Gemini key works. Models your key can use for text:")
            for n in sorted(names)[:25]:
                print(f"       - {n}")
            print("     → Put the free 'flash' models you want in gemini.models in config.yaml.")
        except Exception as exc:  # noqa: BLE001
            print(f"  {BAD} Gemini key failed: {str(exc)[:200]}")
            problems += 1
    return problems
