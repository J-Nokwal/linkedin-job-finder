# LinkedIn Job Finder — Setup Guide

## Quick Start (recommended)

Run the interactive setup script — it handles everything below automatically:

```bash
bash scripts/setup.sh
```

**Safe to run more than once.** Every step checks whether it has already been done and asks before overwriting:

| Step | What it checks before acting |
|------|-------------------------------|
| `.env` | Detects existing file, asks to override or keep |
| `venv` | Detects existing venv, asks before recreating |
| `npm install` | Detects `node_modules/`, asks before re-running |
| `npm run build` | Detects `.next/` build, asks before rebuilding |
| Cron job | Detects existing entry, asks before replacing |
| Desktop entry | Detects existing `.desktop` file, asks before overwriting |
| `.gitignore` | Only appends missing entries, never removes existing ones |

> If you re-run setup after changing credentials or switching AI platform, choose **yes** when prompted to override `.env` and the cron job. Everything else can be skipped.

---

## Prerequisites

Install these before running `scripts/setup.sh`:

| Tool | Minimum version | Purpose |
|------|----------------|---------|
| Python | 3.10+ | Scraper & analyser |
| Node.js | 18+ | Next.js dashboard |
| Git | any | Clone the repo |
| Groq API key **or** Ollama | — | AI job analysis |

Chromium is installed automatically by the setup script via Playwright.

---

## Manual Setup (alternative to scripts/setup.sh)

Follow these steps if you prefer to set things up yourself.

### 1. Clone & enter the project

```bash
git clone <repo-url>
cd linkedin-job-finder
```

---

### 2. Environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=yourpassword

# AI platform: "groq" or "ollama" — sets all AI defaults automatically
PLATFORM=groq

OPENAI_API_KEY=your_groq_api_key_here

# Optional overrides (remove to use PLATFORM defaults)
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODELS=llama-3.3-70b-versatile,meta-llama/llama-4-scout-17b-16e-instruct
AI_ANALYSIS_DELAY=5
AI_REQUEST_TIMEOUT=60

CHROME_PROFILE_DIR=./browser_profile
NEXTJS_API_URL=http://localhost:3000
```

---

### 3. Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

---

### 4. Next.js dashboard

```bash
cd nextjs
npm install
npm run build
cd ..
```

---

### 5. Your profile data

Fill in the four files under `myData/` — the AI uses these to score job fit:

| File | What to put in it |
|------|-------------------|
| `myData/profile.txt` | Your background, years of experience, current role |
| `myData/resume_summary.txt` | A short summary of your CV |
| `myData/projects.txt` | Key projects and tech stacks |
| `myData/preferences.txt` | Job preferences: location, salary, remote, roles |

---

### 6. Customise search queries (optional)

Open `config.py` and edit `CONTENT_SEARCH_QUERIES`. The defaults target Flutter, Go, Next.js, React, AWS, and Python roles.

---

### 7. AI platform

#### Groq (cloud, fast, free tier — recommended)

```bash
# In .env:
PLATFORM=groq
OPENAI_API_KEY=your_groq_api_key
```

Get a free API key at [console.groq.com/keys](https://console.groq.com/keys).

#### Ollama (local, private)

```bash
ollama serve
ollama pull llama3
# In .env:
PLATFORM=ollama
OPENAI_API_KEY=ollama
```

Setting `PLATFORM` is enough — `base_url`, default models, timeout, and delay are all configured automatically.

---

### 8. Cron job

```bash
# Add via scripts/setup.sh, or manually:
crontab -e
```

Daily at 11:00 AM:
```
0 11 * * * /path/to/scripts/scheduler.sh >> /path/to/logs/cron.log 2>&1
```

Every 5 minutes (for testing):
```
*/5 * * * * /path/to/scripts/scheduler.sh >> /path/to/logs/cron.log 2>&1
```

The scheduler reads `PLATFORM` from `.env` automatically and skips the Ollama check when using Groq.

---

### 9. Desktop menu entry

`scripts/setup.sh` creates a launcher in your app menu automatically. To do it manually:

```bash
# Creates ~/.local/share/applications/linkedin-job-finder.desktop
update-desktop-database ~/.local/share/applications/
```

---

## Running the app

### Interactive (recommended)

```bash
bash scripts/run.sh
```

Prompts you to choose:
- **1** — Scraper + analyser (full run)
- **2** — Analyser only (re-analyse already scraped posts)

Or click **LinkedIn Job Finder** in your app menu.

### Headless / automated

```bash
bash scripts/scheduler.sh
```

Used by the cron job. Runs non-interactively and logs to `logs/`.

---

## Results & logs

| Location | Contents |
|----------|----------|
| `http://localhost:3000` | Live dashboard (while app is running) |
| `results/jobs_YYYY-MM-DD.json` | Full AI-analysed job results |
| `logs/scheduler-YYYY-MM-DD.log` | Scheduler run log |
| `logs/cron.log` | Cron job output |

---

## Re-running setup

You can safely re-run `bash scripts/setup.sh` any time — for example after:

- Changing LinkedIn credentials
- Switching AI platform (Groq ↔ Ollama)
- Updating Python packages (`requirements.txt` changed)
- Rebuilding the Next.js dashboard after code changes

The script will prompt you at each step before making any changes.
