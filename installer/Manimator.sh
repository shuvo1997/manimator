#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Manimator launcher
#
# This script is the macOS .app bundle entry point. It:
#   1. Locates Python 3.10+
#   2. Creates / updates a venv in ~/Library/Application Support/Manimator/venv
#   3. Installs / upgrades Python dependencies on first launch or upgrade
#   4. Launches the Manimator Qt app
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── App metadata ──────────────────────────────────────────────────────────────
APP_NAME="Manimator"
APP_VERSION="1.0.0"
SUPPORT_DIR="$HOME/Library/Application Support/$APP_NAME"
VENV_DIR="$SUPPORT_DIR/venv"
VERSION_FILE="$SUPPORT_DIR/.installed_version"
LOG_FILE="$SUPPORT_DIR/launch.log"

# Where this .app bundle lives
BUNDLE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RESOURCES_DIR="$BUNDLE_DIR/Contents/Resources"

mkdir -p "$SUPPORT_DIR"
exec 2>>"$LOG_FILE"
echo "$(date): Manimator $APP_VERSION starting" >> "$LOG_FILE"

# ── Helper: show a macOS dialog ───────────────────────────────────────────────
dialog() {
    osascript -e "display dialog \"$1\" buttons {\"$2\"} default button 1 with title \"Manimator\"" 2>/dev/null || true
}

error_dialog() {
    osascript -e "display dialog \"$1\" buttons {\"Quit\"} default button 1 with title \"Manimator — Error\" with icon stop" 2>/dev/null || true
    exit 1
}

# ── Helper: show a progress window while running a command ───────────────────
run_with_progress() {
    local title="$1"
    local message="$2"
    shift 2

    # Open a terminal-style progress window via osascript
    osascript <<APPLESCRIPT &
tell application "Terminal"
    activate
    do script "echo '${message}'"
end tell
APPLESCRIPT
    PROGRESS_PID=$!

    "$@" >> "$LOG_FILE" 2>&1
    STATUS=$?

    kill $PROGRESS_PID 2>/dev/null || true
    return $STATUS
}

# ── Step 1: Find Python 3.10+ ─────────────────────────────────────────────────
find_python() {
    # Check common locations in order of preference
    local candidates=(
        "/opt/homebrew/bin/python3.14"
        "/opt/homebrew/bin/python3.13"
        "/opt/homebrew/bin/python3.12"
        "/opt/homebrew/bin/python3.11"
        "/opt/homebrew/bin/python3.10"
        "/usr/local/bin/python3.14"
        "/usr/local/bin/python3.13"
        "/usr/local/bin/python3.12"
        "/usr/local/bin/python3.11"
        "/usr/local/bin/python3.10"
        "$(which python3 2>/dev/null || true)"
    )

    for candidate in "${candidates[@]}"; do
        if [[ -x "$candidate" ]]; then
            # Verify version is 3.10+
            version=$("$candidate" -c "import sys; print(sys.version_info >= (3,10))" 2>/dev/null || echo "False")
            if [[ "$version" == "True" ]]; then
                echo "$candidate"
                return 0
            fi
        fi
    done

    return 1
}

PYTHON=$(find_python 2>/dev/null || true)
if [[ -z "$PYTHON" ]]; then
    error_dialog "Manimator requires Python 3.10 or newer.\n\nInstall it with:\n  brew install python@3.14\n\nThen relaunch Manimator."
fi

echo "$(date): Using Python: $PYTHON ($($PYTHON --version 2>&1))" >> "$LOG_FILE"

# ── Step 2: Check ffmpeg ──────────────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
    osascript -e 'display notification "ffmpeg not found — GIF export will not work. Install with: brew install ffmpeg" with title "Manimator"' 2>/dev/null || true
fi

# ── Step 3: Create / update venv ─────────────────────────────────────────────
NEEDS_INSTALL=false

if [[ ! -f "$VENV_DIR/bin/python" ]]; then
    echo "$(date): Creating venv at $VENV_DIR" >> "$LOG_FILE"
    NEEDS_INSTALL=true
elif [[ ! -f "$VERSION_FILE" ]] || [[ "$(cat "$VERSION_FILE" 2>/dev/null)" != "$APP_VERSION" ]]; then
    echo "$(date): Version mismatch — reinstalling deps" >> "$LOG_FILE"
    NEEDS_INSTALL=true
fi

if [[ "$NEEDS_INSTALL" == "true" ]]; then
    # Show a setup notification
    osascript -e "display notification \"Setting up Manimator (first launch may take 1-2 minutes)…\" with title \"Manimator\"" 2>/dev/null || true

    # Create venv if needed
    if [[ ! -f "$VENV_DIR/bin/python" ]]; then
        "$PYTHON" -m venv "$VENV_DIR" >> "$LOG_FILE" 2>&1 || error_dialog "Failed to create Python virtual environment.\nSee log: $LOG_FILE"
    fi

    # Install Python 3.13+ shims if needed
    PY_MINOR=$("$VENV_DIR/bin/python" -c "import sys; print(sys.version_info.minor)")
    PY_MAJOR=$("$VENV_DIR/bin/python" -c "import sys; print(sys.version_info.major)")

    if [[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 13 ]]; then
        "$VENV_DIR/bin/pip" install --quiet --upgrade "setuptools<75" audioop-lts >> "$LOG_FILE" 2>&1 || true
    fi

    # Install / upgrade all dependencies from requirements.txt
    REQUIREMENTS="$RESOURCES_DIR/requirements.txt"
    if [[ ! -f "$REQUIREMENTS" ]]; then
        REQUIREMENTS="$(dirname "$BUNDLE_DIR")/requirements.txt"
    fi

    "$VENV_DIR/bin/pip" install --quiet --upgrade pip >> "$LOG_FILE" 2>&1 || true
    "$VENV_DIR/bin/pip" install --quiet -r "$REQUIREMENTS" >> "$LOG_FILE" 2>&1 \
        || error_dialog "Failed to install dependencies.\n\nSee log:\n$LOG_FILE"

    # Pin pyglet (manimgl requires < 2.0)
    "$VENV_DIR/bin/pip" install --quiet "pyglet==1.5.31" >> "$LOG_FILE" 2>&1 || true

    # Record installed version
    echo "$APP_VERSION" > "$VERSION_FILE"
    osascript -e "display notification \"Manimator is ready!\" with title \"Manimator\"" 2>/dev/null || true
fi

# ── Step 4: Launch the app ────────────────────────────────────────────────────
APP_SRC="$RESOURCES_DIR/app_source"

# Ensure the app source is on PYTHONPATH
export PYTHONPATH="$APP_SRC:${PYTHONPATH:-}"

echo "$(date): Launching main.py from $APP_SRC" >> "$LOG_FILE"
exec "$VENV_DIR/bin/python" "$APP_SRC/main.py" "$@"
