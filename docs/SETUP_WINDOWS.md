# Windows setup — step by step

Takes about 30–45 minutes the first time. Do the steps in order. Everything here is free.

> **Tip:** use **Command Prompt** (search "cmd" in the Start menu) for all commands below.
> After installing any program, **close and reopen** Command Prompt so it sees the new program.

---

## 1. Python 3.11

```bat
winget install Python.Python.3.11
```

(Or download "Python 3.11" from https://www.python.org/downloads/windows/ — on the first installer screen, tick **"Add python.exe to PATH"**.)

Check: `py -3.11 --version` → should print `Python 3.11.x`.

> Why 3.11 and not the newest? Some audio/AI packages used in later stages don't support the newest Python yet. 3.11 works with all of them.

## 2. Git

```bat
winget install Git.Git
```

Check: `git --version`

## 3. Get the project

Pick a folder that is **not** inside OneDrive (OneDrive struggles with big video files), e.g. `C:\Studio`:

```bat
mkdir C:\Studio
cd C:\Studio
git clone https://github.com/Sampath1-1-1/Content-Creation.git
cd Content-Creation
```

Later, to get new stages I build: `git pull`

## 4. Virtual environment + packages

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Your prompt now starts with `(.venv)`. **Every time** you open a new Command Prompt to work on the project:

```bat
cd C:\Studio\Content-Creation
.venv\Scripts\activate
```

## 5. Try the offline demo (no keys needed yet)

```bat
python studio.py --topic "numbers 1 to 10" --fixture tests/fixtures/youtube_sample.json
```

It analyses **made-up sample data** and writes a report to
`projects\numbers-1-to-10__demo\01_research\research_report.html` — open it in your browser.

Run the tests too: `python -m pytest` → all should pass.

## 6. Gemini API key (free)

1. Go to https://aistudio.google.com/apikey and sign in with your Google account.
2. Click **Create API key** (let it create a new project if asked).
3. Copy the key.

> ⚠️ **Never add a billing account / credit card to this Google project.** Without billing you stay on the free tier and can never be charged.

## 7. YouTube Data API key (free)

1. Go to https://console.cloud.google.com/ → top bar project picker → **New project** → name it `kids-video-studio` → Create, and make sure it's selected.
2. Menu ☰ → **APIs & Services → Library** → search **YouTube Data API v3** → **Enable**.
3. **APIs & Services → Credentials → Create credentials → API key**. Copy it.
4. Click the new key → under **API restrictions** choose **Restrict key** → tick **YouTube Data API v3** → **Save**. (So the key is useless for anything else if it ever leaks.)

Again: no billing needed. The free allowance is 10,000 units/day; one research run uses about 1,200–1,500.

## 8. Put both keys in `.env`

```bat
copy .env.example .env
notepad .env
```

Fill in:

```
GEMINI_API_KEY=paste-your-gemini-key
YOUTUBE_API_KEY=paste-your-youtube-key
```

Save and close. `.env` is git-ignored, so it never gets uploaded — **never paste keys anywhere else** (the GitHub repo is public).

## 9. Check everything

```bat
python studio.py doctor --online
```

Fix any ❌ lines (each one says how). The online check also lists the Gemini models your key can use — if `gemini-2.5-flash` isn't in the list, put the free "flash" models it shows into `gemini.models` in `config.yaml`.

## 10. First real research run

```bat
python studio.py --topic "numbers 1 to 10" --only-stage 1
```

Report: `projects\numbers-1-to-10\01_research\research_report.html`

---

## Needed from Stage 4 onwards (you can do these now or later)

### FFmpeg

```bat
winget install Gyan.FFmpeg
```

Reopen Command Prompt. Check: `ffmpeg -version`

### Tesseract OCR

```bat
winget install UB-Mannheim.TesseractOCR
```

If `tesseract --version` says "not recognized", add `C:\Program Files\Tesseract-OCR` to your PATH:
Start → "Edit the system environment variables" → **Environment Variables…** → under *User variables* select **Path** → **Edit** → **New** → paste `C:\Program Files\Tesseract-OCR` → OK → reopen Command Prompt.

### Kaggle (free GPU for sung vocals)

1. Create **one** account at https://www.kaggle.com.
2. **Settings → Phone verification** — required for GPU and internet access in notebooks.
3. **Settings → API → Create New Token**. This downloads `kaggle.json`.
4. Move it to `C:\Users\<your-name>\.kaggle\kaggle.json` (create the `.kaggle` folder if needed).
   If Kaggle's page shows a different kind of token, follow its instructions — `python studio.py doctor` will tell you whether it's found.

Kaggle gives a weekly free GPU allowance (shown on your Kaggle profile). The pipeline tracks it and never reruns a finished song.
