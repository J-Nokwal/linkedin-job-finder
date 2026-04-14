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
if [ "$1" = "build" ]; then
  echo "📦 Force rebuilding Next.js..."
  (cd "$NEXT_DIR" && npm run build)
elif [ ! -d "$NEXT_DIR/.next" ]; then
  echo "📦 First time build..."
  (cd "$NEXT_DIR" && npm run build)
else
  echo "📦 Using existing build"
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
echo "What do you want to run?"
echo "1) Both automation (scraper) and analyser"
echo "2) Just analyser"
read -p "Enter choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
  echo "▶ Starting Python bot (automation and analyser)..."
  "$VENV_PYTHON" "$PROJECT_ROOT/main.py" &
  PIDS+=($!)
elif [ "$choice" = "2" ]; then
  echo "▶ Starting Python analyser..."
  "$VENV_PYTHON" "$PROJECT_ROOT/worker.py" --ai-timeout 600 &
  PIDS+=($!)
else
  echo "❌ Invalid choice"
  exit 1
fi

echo "✅ All services running!"
echo "Next.js: http://localhost:3000"

wait