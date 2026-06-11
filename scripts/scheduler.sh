#!/usr/bin/env bash

# ============================================================
# scheduler.sh — Non-interactive daily automation runner
# Runs: Ollama + Next.js (DB APIs) + Python scraper
# ============================================================

# ─── Environment (cron has a bare PATH, set it explicitly) ───
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin"
export DISPLAY=:0
export XAUTHORITY=$(ls /run/user/1000/.mutter-Xwaylandauth.* 2>/dev/null | head -1)

set -e

PROJECT_ROOT="/home/rockbot/Documents/ai-tool/linkedin-job-finder"

# ─── Load .env so PLATFORM and other vars are available ──────
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/.env"
  set +a
fi
PLATFORM="${PLATFORM:-ollama}"

LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/scheduler-$(date +%Y-%m-%d).log"

mkdir -p "$LOG_DIR"

# Redirect all output (stdout + stderr) to log file AND terminal
exec > >(tee -a "$LOG_FILE") 2>&1

echo ""
echo "============================================================"
echo "🕐 Scheduler started at $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo "📁 Working dir: $PROJECT_ROOT"

cd "$PROJECT_ROOT"

# ─── Kill stale processes from previous run ───────────────────
echo "🧹 Cleaning up stale processes..."

# Kill leftover Chromium first (it holds the SingletonLock)
pkill -f "chrome-linux64/chrome" 2>/dev/null && echo "   Killed stale Chromium" || echo "   No stale Chromium"
pkill -f "xvfb-run"              2>/dev/null && echo "   Killed stale xvfb-run" || true

# Give processes time to fully die
sleep 2

# Now safe to delete the SingletonLock
SINGLETON="$PROJECT_ROOT/browser_profile/SingletonLock"
if [ -f "$SINGLETON" ]; then
  rm -f "$SINGLETON"
  echo "   Removed stale SingletonLock"
else
  echo "   No SingletonLock found"
fi

# Kill anything on port 3000
fuser -k 3000/tcp 2>/dev/null && echo "   Killed stale process on port 3000" || echo "   Port 3000 is free"

sleep 1

# ─────────────────────────────────────────────────────────────
PIDS=()

cleanup() {
  echo ""
  echo "🛑 Stopping all services at $(date '+%H:%M:%S')..."

  for PID in "${PIDS[@]}"; do
    if kill -0 "$PID" 2>/dev/null; then
      echo "   Killing PID $PID"
      kill "$PID"
    fi
  done

  pkill -f "chrome-linux64/chrome" 2>/dev/null || true
  pkill -f "xvfb-run"              2>/dev/null || true

  echo "✅ All services stopped."
  exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# ─── Paths ───────────────────────────────────────────────────
NEXT_DIR="$PROJECT_ROOT/nextjs"
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"

# ─── Validate venv ───────────────────────────────────────────
if [ ! -f "$VENV_PYTHON" ]; then
  echo "❌ Python venv not found at: $VENV_PYTHON"
  exit 1
fi

echo "🐍 Using Python: $VENV_PYTHON"

# ─── Ensure Ollama is running (skip if using Groq) ───────────
echo "🤖 AI platform: $PLATFORM"
if [ "$PLATFORM" = "groq" ]; then
  echo "   ✅ Using Groq API — Ollama not needed"
else
  echo "   Checking Ollama..."
  if curl -sf http://localhost:11434 >/dev/null 2>&1; then
    echo "   ✅ Ollama already running"
  else
    echo "   Ollama not running — starting it..."
    ollama serve >/dev/null 2>&1 &
    OLLAMA_PID=$!
    PIDS+=($OLLAMA_PID)

    for i in $(seq 1 15); do
      if curl -sf http://localhost:11434 >/dev/null 2>&1; then
        echo "   ✅ Ollama is up (took ${i}s)"
        break
      fi
      if [ "$i" -eq 15 ]; then
        echo "   ❌ Ollama did not start in 15s — aborting"
        exit 1
      fi
      sleep 1
    done
  fi
fi

# ─── Build Next.js if needed ─────────────────────────────────
if [ ! -d "$NEXT_DIR/.next" ]; then
  echo "📦 No existing build found — building Next.js..."
  (cd "$NEXT_DIR" && npm run build)
else
  echo "📦 Using existing Next.js build"
fi

# ─── Start Next.js (required for DB APIs) ────────────────────
echo "▶  Starting Next.js..."
(cd "$NEXT_DIR" && npm run start) &
NEXTJS_PID=$!
PIDS+=($NEXTJS_PID)
echo "   Next.js PID: $NEXTJS_PID"

# Wait for Next.js to be ready
echo "⏳ Waiting for Next.js to be ready..."
for i in $(seq 1 15); do
  if curl -sf http://localhost:3000 >/dev/null 2>&1; then
    echo "   ✅ Next.js is up (took ${i}s)"
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo "   ⚠️  Next.js did not respond in 15s — continuing anyway"
  fi
  sleep 1
done

# ─── Start Python scraper (with visible Chrome window) ────────
echo "▶  Starting Python scraper (Chrome window will open)..."
"$VENV_PYTHON" "$PROJECT_ROOT/main.py" &
SCRAPER_PID=$!
PIDS+=($SCRAPER_PID)
echo "   Scraper PID: $SCRAPER_PID"

echo ""
echo "✅ All services running!"
echo "   Ollama   → http://localhost:11434"
echo "   Next.js  → http://localhost:3000  (PID $NEXTJS_PID)"
echo "   Scraper  → PID $SCRAPER_PID"
echo "   Logs     → $LOG_FILE"
echo ""

# Wait for scraper to finish, then cleanup trap kills everything
wait "${SCRAPER_PID}"

echo ""
echo "🏁 Scraper finished at $(date '+%Y-%m-%d %H:%M:%S')"
echo "   Shutting down Next.js..."