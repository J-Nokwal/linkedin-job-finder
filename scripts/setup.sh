#!/usr/bin/env bash
# ============================================================
# LinkedIn Job Finder — Interactive Setup Script
# ============================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"
NEXT_DIR="$PROJECT_ROOT/nextjs"
ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"
DESKTOP_FILE="$HOME/.local/share/applications/linkedin-job-finder.desktop"

# ── Colours ─────────────────────────────────────────────────
BOLD="\033[1m"
CYAN="\033[1;36m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
BLUE="\033[1;34m"
DIM="\033[2m"
RESET="\033[0m"

# ── Helpers ──────────────────────────────────────────────────
section()  { echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"; echo -e "${CYAN}  $1${RESET}"; echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"; }
ok()       { echo -e "  ${GREEN}✅  $1${RESET}"; }
warn()     { echo -e "  ${YELLOW}⚠️   $1${RESET}"; }
info()     { echo -e "  ${BLUE}ℹ️   $1${RESET}"; }
err()      { echo -e "  ${RED}❌  $1${RESET}"; }
ask()      { echo -e -n "  ${BOLD}$1${RESET} "; }
dim()      { echo -e "  ${DIM}$1${RESET}"; }

confirm() {
  local prompt="${1} [y/N] "
  ask "$prompt"
  read -r ans
  [[ "$ans" =~ ^[Yy]$ ]]
}

prompt_value() {
  local label="$1" default="$2"
  if [[ -n "$default" ]]; then
    ask "$label ${DIM}(default: $default)${RESET}:"
  else
    ask "$label:"
  fi
  read -r val
  echo "${val:-$default}"
}

prompt_secret() {
  local label="$1"
  ask "$label (hidden):"
  read -rs val
  echo ""
  echo "$val"
}

# ── Banner ────────────────────────────────────────────────────
clear
echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║       LinkedIn Job Finder — Setup            ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${RESET}"
echo -e "  ${DIM}Project: $PROJECT_ROOT${RESET}"
echo ""

# ═══════════════════════════════════════════════════════════════
section "1 · Environment Configuration"
# ═══════════════════════════════════════════════════════════════

ENV_EXISTS=false
[[ -f "$ENV_FILE" ]] && ENV_EXISTS=true

if $ENV_EXISTS; then
  warn ".env already exists."
  if confirm "  Override existing .env with fresh values?"; then
    CONFIGURE_ENV=true
  else
    info "Keeping existing .env — skipping env setup."
    CONFIGURE_ENV=false
  fi
else
  info "No .env found — will create one."
  CONFIGURE_ENV=true
fi

if $CONFIGURE_ENV; then
  echo ""
  echo -e "  ${BOLD}Choose setup mode:${RESET}"
  echo -e "    ${CYAN}1)${RESET} Interactive — enter each value now"
  echo -e "    ${CYAN}2)${RESET} Copy from .env.example and edit manually later"
  ask "Choice [1/2] (default: 1):"
  read -r setup_mode
  setup_mode="${setup_mode:-1}"

  if [[ "$setup_mode" == "2" ]]; then
    if [[ -f "$ENV_EXAMPLE" ]]; then
      cp "$ENV_EXAMPLE" "$ENV_FILE"
      ok "Copied .env.example → .env"
      warn "Edit $ENV_FILE with your real credentials before running."
    else
      err ".env.example not found. Running interactive setup instead."
      setup_mode="1"
    fi
  fi

  if [[ "$setup_mode" == "1" ]]; then
    echo ""
    echo -e "  ${BOLD}─── LinkedIn Credentials ───────────────────────${RESET}"
    LINKEDIN_EMAIL=$(prompt_value   "LinkedIn email" "")
    LINKEDIN_PASSWORD=$(prompt_secret "LinkedIn password")

    echo ""
    echo -e "  ${BOLD}─── AI Platform ────────────────────────────────${RESET}"
    echo -e "    ${CYAN}1)${RESET} Groq  (cloud, fast, free tier)"
    echo -e "    ${CYAN}2)${RESET} Ollama (local, private)"
    ask "Platform [1/2] (default: 1):"
    read -r plat_choice
    if [[ "$plat_choice" == "2" ]]; then
      PLATFORM="ollama"
      OPENAI_BASE_URL="http://localhost:11434/v1"
      OPENAI_API_KEY="ollama"
      OPENAI_MODELS="llama3"
      AI_ANALYSIS_DELAY="2"
      AI_REQUEST_TIMEOUT="300"
    else
      PLATFORM="groq"
      OPENAI_BASE_URL="https://api.groq.com/openai/v1"
      OPENAI_API_KEY=$(prompt_value "Groq API key" "")
      OPENAI_MODELS=$(prompt_value "Models (comma-separated)" "llama-3.3-70b-versatile,meta-llama/llama-4-scout-17b-16e-instruct,qwen/qwen3-32b")
      AI_ANALYSIS_DELAY=$(prompt_value "Analysis delay (s)" "5")
      AI_REQUEST_TIMEOUT=$(prompt_value "Request timeout (s)" "60")
    fi

    echo ""
    echo -e "  ${BOLD}─── App Settings ───────────────────────────────${RESET}"
    NEXTJS_API_URL=$(prompt_value  "Next.js API URL" "http://localhost:3000")
    CHROME_PROFILE_DIR=$(prompt_value "Chrome profile dir" "./browser_profile")

    cat > "$ENV_FILE" << ENVEOF
LINKEDIN_EMAIL=${LINKEDIN_EMAIL}
LINKEDIN_PASSWORD=${LINKEDIN_PASSWORD}

# ── AI Platform ────────────────────────────────────────────────
PLATFORM=${PLATFORM}

# ── API key ────────────────────────────────────────────────────
OPENAI_API_KEY=${OPENAI_API_KEY}

# ── Overrides ──────────────────────────────────────────────────
OPENAI_BASE_URL=${OPENAI_BASE_URL}
OPENAI_MODELS=${OPENAI_MODELS}
AI_ANALYSIS_DELAY=${AI_ANALYSIS_DELAY}
AI_REQUEST_TIMEOUT=${AI_REQUEST_TIMEOUT}

# ── App ────────────────────────────────────────────────────────
CHROME_PROFILE_DIR=${CHROME_PROFILE_DIR}
NEXTJS_API_URL=${NEXTJS_API_URL}
ENVEOF

    ok ".env created."
  fi
fi

# ═══════════════════════════════════════════════════════════════
section "2 · Python Virtual Environment"
# ═══════════════════════════════════════════════════════════════

PYTHON_BIN=$(which python3 2>/dev/null || which python 2>/dev/null || true)
if [[ -z "$PYTHON_BIN" ]]; then
  err "Python 3 not found. Install it and re-run setup."
  exit 1
fi

PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1)
info "Using: $PYTHON_VERSION ($PYTHON_BIN)"

if [[ -d "$VENV_DIR" ]]; then
  warn "venv already exists."
  if confirm "  Recreate venv? (reinstalls all packages)"; then
    rm -rf "$VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    ok "venv recreated."
  else
    ok "Keeping existing venv."
  fi
else
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  ok "venv created."
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

info "Installing Python packages…"
"$VENV_PIP" install --upgrade pip -q
"$VENV_PIP" install -r "$PROJECT_ROOT/requirements.txt" -q
ok "Python packages installed."

info "Installing Playwright browser (Chromium)…"
"$VENV_DIR/bin/playwright" install chromium
ok "Chromium installed."

# ═══════════════════════════════════════════════════════════════
section "3 · Next.js Dashboard"
# ═══════════════════════════════════════════════════════════════

NODE_BIN=$(which node 2>/dev/null || true)
if [[ -z "$NODE_BIN" ]]; then
  err "Node.js not found. Install Node 18+ and re-run setup."
else
  NODE_VERSION=$("$NODE_BIN" --version)
  info "Node.js: $NODE_VERSION"

  if [[ -d "$NEXT_DIR/node_modules" ]]; then
    warn "node_modules already exists."
    if confirm "  Re-run npm install?"; then
      (cd "$NEXT_DIR" && npm install --silent)
      ok "npm packages updated."
    else
      ok "Skipping npm install."
    fi
  else
    info "Running npm install…"
    (cd "$NEXT_DIR" && npm install --silent)
    ok "npm packages installed."
  fi

  if [[ -d "$NEXT_DIR/.next" ]]; then
    warn "Next.js build already exists."
    if confirm "  Rebuild? (takes ~1 min)"; then
      (cd "$NEXT_DIR" && npm run build)
      ok "Next.js rebuilt."
    else
      ok "Skipping build — using existing."
    fi
  else
    info "Building Next.js…"
    (cd "$NEXT_DIR" && npm run build)
    ok "Next.js built."
  fi
fi

# ═══════════════════════════════════════════════════════════════
section "4 · Cron Job"
# ═══════════════════════════════════════════════════════════════

SCHEDULER="$PROJECT_ROOT/scripts/scheduler.sh"
chmod +x "$SCHEDULER"

EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "$SCHEDULER" || true)

if [[ -n "$EXISTING_CRON" ]]; then
  warn "Cron job already exists:"
  dim "  $EXISTING_CRON"
  if confirm "  Replace with a new schedule?"; then
    DO_CRON=true
  else
    ok "Keeping existing cron job."
    DO_CRON=false
  fi
else
  if confirm "Add a cron job to run the automation daily?"; then
    DO_CRON=true
  else
    info "Skipping cron job."
    DO_CRON=false
  fi
fi

if $DO_CRON; then
  echo ""
  echo -e "  ${BOLD}Choose schedule:${RESET}"
  echo -e "    ${CYAN}1)${RESET} Every day at 11:00 AM ${DIM}(recommended)${RESET}"
  echo -e "    ${CYAN}2)${RESET} Every 5 minutes       ${DIM}(testing)${RESET}"
  echo -e "    ${CYAN}3)${RESET} Custom cron expression"
  ask "Choice [1/2/3] (default: 1):"
  read -r cron_choice
  cron_choice="${cron_choice:-1}"

  case "$cron_choice" in
    2) CRON_EXPR="*/5 * * * *";  CRON_DESC="every 5 minutes (test)" ;;
    3)
      CRON_EXPR=$(prompt_value "Cron expression" "0 11 * * *")
      CRON_DESC="custom: $CRON_EXPR"
      ;;
    *) CRON_EXPR="0 11 * * *";   CRON_DESC="daily at 11:00 AM" ;;
  esac

  CRON_LOG="$PROJECT_ROOT/logs/cron.log"
  CRON_LINE="$CRON_EXPR $SCHEDULER >> $CRON_LOG 2>&1"

  (crontab -l 2>/dev/null | grep -v -F "$SCHEDULER"; echo "# LinkedIn Job Finder — $CRON_DESC"; echo "$CRON_LINE") | crontab -
  ok "Cron job set: $CRON_DESC"
  dim "  $CRON_LINE"
fi

# ═══════════════════════════════════════════════════════════════
section "5 · Desktop Menu Entry"
# ═══════════════════════════════════════════════════════════════

TERMINAL_BIN=$(which ptyxis 2>/dev/null || which gnome-terminal 2>/dev/null || which xterm 2>/dev/null || true)

if [[ -z "$TERMINAL_BIN" ]]; then
  warn "No supported terminal found (ptyxis/gnome-terminal/xterm). Skipping menu entry."
else
  if [[ -f "$DESKTOP_FILE" ]]; then
    warn "Desktop entry already exists."
    if ! confirm "  Overwrite it?"; then
      ok "Keeping existing desktop entry."
      TERMINAL_BIN=""
    fi
  fi

  if [[ -n "$TERMINAL_BIN" ]]; then
    mkdir -p "$(dirname "$DESKTOP_FILE")"
    if [[ "$TERMINAL_BIN" == *ptyxis* || "$TERMINAL_BIN" == *gnome-terminal* ]]; then
      EXEC_CMD="$TERMINAL_BIN -- bash -c \"$PROJECT_ROOT/scripts/run.sh; exec bash\""
    else
      EXEC_CMD="$TERMINAL_BIN -e \"bash -c '$PROJECT_ROOT/scripts/run.sh; exec bash'\""
    fi

    cat > "$DESKTOP_FILE" << DESKEOF
[Desktop Entry]
Name=LinkedIn Job Finder
Comment=Run LinkedIn job scraper and analyser
Exec=$EXEC_CMD
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=true
DESKEOF

    update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
    ok "Desktop entry created → $DESKTOP_FILE"
    info "LinkedIn Job Finder now appears in your app menu."
  fi
fi

# ═══════════════════════════════════════════════════════════════
section "6 · Package & Permission Restrictions"
# ═══════════════════════════════════════════════════════════════

GITIGNORE="$PROJECT_ROOT/.gitignore"
REQUIRED_IGNORES=(".env" "browser_profile/" "logs/" "results/" "venv/" "__pycache__/")
GITIGNORE_UPDATED=false

if [[ ! -f "$GITIGNORE" ]]; then
  touch "$GITIGNORE"
fi

for entry in "${REQUIRED_IGNORES[@]}"; do
  if ! grep -qF "$entry" "$GITIGNORE" 2>/dev/null; then
    echo "$entry" >> "$GITIGNORE"
    GITIGNORE_UPDATED=true
  fi
done

if $GITIGNORE_UPDATED; then
  ok ".gitignore updated with sensitive paths."
else
  ok ".gitignore already covers sensitive paths."
fi

chmod +x "$PROJECT_ROOT/scripts/"*.sh 2>/dev/null || true
ok "scripts/*.sh marked executable."

chmod 600 "$ENV_FILE" 2>/dev/null && ok ".env permissions set to 600 (owner-only)." || true

# ═══════════════════════════════════════════════════════════════
section "Setup Complete"
# ═══════════════════════════════════════════════════════════════

echo ""
echo -e "  ${GREEN}${BOLD}Everything is ready. Here's what to do next:${RESET}"
echo ""
echo -e "  ${CYAN}Run the app interactively:${RESET}"
echo -e "  ${DIM}  bash $PROJECT_ROOT/scripts/run.sh${RESET}"
echo ""
echo -e "  ${CYAN}Or run headless (as cron does):${RESET}"
echo -e "  ${DIM}  bash $PROJECT_ROOT/scripts/scheduler.sh${RESET}"
echo ""
echo -e "  ${CYAN}Dashboard (once running):${RESET}"
echo -e "  ${DIM}  http://localhost:3000${RESET}"
echo ""
echo -e "  ${DIM}To manage the cron job: crontab -e${RESET}"
echo ""
