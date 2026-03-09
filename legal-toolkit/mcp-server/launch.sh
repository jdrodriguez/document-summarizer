#!/bin/bash
# Launch the legal-transcriber MCP server.
# Self-bootstraps: creates venv and installs deps if needed.
# All setup output goes to stderr so it doesn't interfere with MCP stdio.
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"

if [ ! -f "$VENV/bin/python" ]; then
    echo "[legal-transcriber] Creating virtual environment..." >&2
    python3 -m venv "$VENV" 2>&2
    echo "[legal-transcriber] Installing dependencies..." >&2
    "$VENV/bin/pip" install --quiet --upgrade pip 2>&2
    "$VENV/bin/pip" install --quiet -r "$DIR/requirements.txt" 2>&2
    echo "[legal-transcriber] Setup complete." >&2
fi

exec "$VENV/bin/python" "$DIR/server.py"
