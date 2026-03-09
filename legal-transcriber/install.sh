#!/bin/bash
# Install the legal-transcriber plugin.
#
# Preferred installation method:
#   In Claude Code, run: /plugin install legal-transcriber
#
# This script:
#   1. Installs Python dependencies (faster-whisper, pydub)
#   2. Checks system tools (ffmpeg)
#   3. Checks npm packages (docx, for output generation)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/skills/transcribe/scripts"

echo "=========================================="
echo "  Legal Transcriber - Install"
echo "=========================================="
echo ""

# --- Step 1: Run dependency checker (auto-installs missing packages) ---
echo "Checking and installing dependencies..."
python3 "$SCRIPTS_DIR/check_dependencies.py"
DEP_EXIT=$?

if [ $DEP_EXIT -eq 2 ]; then
    echo ""
    echo "ERROR: Dependency installation failed. See errors above."
    exit 1
fi

# --- Step 2: Check npm dependencies (for .docx output generation) ---
echo ""
echo "Checking npm dependencies..."
if command -v npm &>/dev/null; then
    npm_missing=()
    for pkg in docx; do
        if ! node -e "require('$pkg')" 2>/dev/null; then
            npm_missing+=("$pkg")
        fi
    done

    if [ ${#npm_missing[@]} -gt 0 ]; then
        echo "Installing npm packages: ${npm_missing[*]}"
        npm install -g "${npm_missing[@]}"
        if [ $? -ne 0 ]; then
            echo "WARNING: Failed to install npm packages."
            echo "  Try manually: npm install -g ${npm_missing[*]}"
            echo "  (.docx output generation may not work)"
        fi
    else
        echo "All npm dependencies already satisfied."
    fi
else
    echo "WARNING: npm not found. .docx output generation will not work."
    echo "  Install Node.js from https://nodejs.org/"
fi

echo ""
echo "=========================================="
echo "  Legal Transcriber installed!"
echo "=========================================="
echo ""
echo "  Ready to use! Invoke with:"
echo "    /legal-transcriber:transcribe"
echo ""
