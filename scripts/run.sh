#!/usr/bin/env bash

set -e

PROJECT_ROOT="/home/rockbot/Documents/ai-tool/linkedin-job-finder"
cd "$PROJECT_ROOT"

echo "🚀 Starting all services (PRODUCTION MODE)..."
echo "📁 Working dir: $PROJECT_ROOT"

PIDS=()

cleanup() {
  echo ""
  echo "🛑 Stopping all services..."

  for PID in "${PIDS[@]}"; do
    if kill -0 "$PID" 2>/dev/null; then
      kill "$PID"
    fi
  done

  exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 📁 Paths
NEXT_DIR="$PROJECT_ROOT/nextjs"
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"

# 🐍 Validate venv
if [ ! -f "$VENV_PYTHON" ]; then
  echo "❌ Python venv not found"
  exit 1
fi

echo "🐍 Using Python: $VENV_PYTHON"

# 📦 Build Next.js
_need_build=false
if [ "$1" = "build" ]; then
  _need_build=true
  echo "📦 Force rebuild requested..."
elif [ ! -d "$NEXT_DIR/.next" ]; then
  _need_build=true
  echo "📦 No build found — building for the first time..."
else
  # Rebuild if any route/component source is newer than the last build output
  _build_time=$(stat -c %Y "$NEXT_DIR/.next/BUILD_ID" 2>/dev/null || echo 0)
  _newest_src=$(find "$NEXT_DIR/app" "$NEXT_DIR/components" "$NEXT_DIR/lib" \
    -name "*.ts" -o -name "*.tsx" 2>/dev/null \
    | xargs stat -c %Y 2>/dev/null | sort -rn | head -1)
  _newest_src="${_newest_src:-0}"
  if [ "$_newest_src" -gt "$_build_time" ]; then
    _need_build=true
    echo "📦 Source changed since last build — rebuilding..."
  else
    echo "📦 Build is up to date"
  fi
fi

if [ "$_need_build" = "true" ]; then
  (cd "$NEXT_DIR" && npm run build)
fi

# ▶ Start Next.js
echo "▶ Starting Next.js..."
(cd "$NEXT_DIR" && npm run start) &
PIDS+=($!)

# wait a bit for Next.js to boot
sleep 2

# 🌐 Open browser
echo "🌐 Opening http://localhost:3000"
xdg-open http://localhost:3000 >/dev/null 2>&1 &

# Ask user what to run
echo ""
echo "What do you want to run?"
echo "  1) Scrape + Analyse  — open LinkedIn, collect posts, run AI analysis"
echo "  2) Analyse only      — re-analyse the last scrape (no browser, no LinkedIn login)"
read -p "Enter choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
  echo "▶ Starting scraper + analyser..."
  "$VENV_PYTHON" "$PROJECT_ROOT/main.py" &
  PIDS+=($!)
elif [ "$choice" = "2" ]; then
  echo "▶ Starting analyser (loading most recent results file)..."
  "$VENV_PYTHON" "$PROJECT_ROOT/main.py" --skip-scrape &
  PIDS+=($!)
else
  echo "❌ Invalid choice"
  exit 1
fi

echo "✅ All services running!"
echo "Next.js: http://localhost:3000"

wait