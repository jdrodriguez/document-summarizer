#!/bin/bash
# ============================================================================
# Legal Transcriber — One-Click Installer for macOS
#
# Double-click this file to install. It will:
#   1. Create a Python virtual environment at ~/.legal-transcriber/
#   2. Install transcription dependencies (faster-whisper, pydub, mcp)
#   3. Pre-download the Whisper AI model (~466 MB, one-time)
#   4. Register the MCP server in Claude Desktop
#   5. Install the Cowork plugin (skill + commands)
#   6. Ready to use in Cowork!
# ============================================================================
set -e

# --- Config ---
INSTALL_DIR="$HOME/.legal-transcriber"
VENV_DIR="$INSTALL_DIR/.venv"
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
PLUGIN_DIR="$HOME/.claude/plugins"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_SOURCE="$SCRIPT_DIR/mcp-server"

# --- Welcome dialog ---
osascript -e '
display dialog "This will install the Legal Transcriber for Claude Desktop and Cowork.\n\nIt will:\n• Install Python transcription libraries\n• Download the Whisper AI model (~466 MB)\n• Register with Claude Desktop\n• Install the Cowork plugin\n\nThis may take a few minutes." buttons {"Cancel", "Install"} default button "Install" with title "Legal Transcriber Installer" with icon note
' 2>/dev/null || { echo "Installation cancelled."; exit 0; }

echo ""
echo "=========================================="
echo "  Legal Transcriber — Installing"
echo "=========================================="
echo ""

# --- Check Python 3 ---
if ! command -v python3 &>/dev/null; then
    osascript -e '
    display dialog "Python 3 is required but not found.\n\nPlease install Python from:\nhttps://python.org/downloads/" buttons {"OK"} default button 1 with title "Missing Python" with icon stop
    ' 2>/dev/null
    echo "ERROR: Python 3 is required. Install from https://python.org/downloads/"
    exit 1
fi
PYTHON_VER=$(python3 --version 2>&1)
echo "Found: $PYTHON_VER"

# --- Check source files exist ---
if [ ! -f "$MCP_SOURCE/server.py" ]; then
    echo "ERROR: MCP server files not found at $MCP_SOURCE"
    echo "Make sure you extracted the full zip and are running from within it."
    exit 1
fi

# --- Create install directory ---
echo ""
echo "Step 1/6: Setting up install directory..."
mkdir -p "$INSTALL_DIR"

# --- Copy MCP server files ---
echo "Step 2/6: Copying server files..."
cp "$MCP_SOURCE/server.py" "$INSTALL_DIR/server.py"
cp "$MCP_SOURCE/worker.py" "$INSTALL_DIR/worker.py"
cp "$MCP_SOURCE/create_document.py" "$INSTALL_DIR/create_document.py"
cp "$MCP_SOURCE/requirements.txt" "$INSTALL_DIR/requirements.txt"

# Create launch script
cat > "$INSTALL_DIR/launch.sh" << 'LAUNCH_EOF'
#!/bin/bash
# Launch the legal-transcriber MCP server from its installed location.
DIR="$HOME/.legal-transcriber"
VENV="$DIR/.venv"

if [ ! -f "$VENV/bin/python" ]; then
    echo "[legal-transcriber] ERROR: Virtual environment not found at $VENV" >&2
    echo "[legal-transcriber] Please re-run the installer." >&2
    exit 1
fi

exec "$VENV/bin/python" "$DIR/server.py"
LAUNCH_EOF
chmod +x "$INSTALL_DIR/launch.sh"

echo "  Copied to: $INSTALL_DIR"

# --- Create virtual environment ---
echo ""
echo "Step 3/6: Creating Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  Created: $VENV_DIR"
else
    echo "  Already exists: $VENV_DIR"
fi

# --- Install dependencies ---
echo ""
echo "Step 4/6: Installing Python dependencies..."
echo "  (This may take a minute...)"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
echo "  Dependencies installed."

# --- Pre-download Whisper model ---
echo ""
echo "Step 5/6: Downloading Whisper AI model (~466 MB)..."
echo "  (First-time download — this only happens once)"
echo ""

# Check if already cached
MODEL_CACHED=$("$VENV_DIR/bin/python" -c "
import os
cache = os.path.expanduser('~/.cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots')
print('yes' if os.path.isdir(cache) else 'no')
" 2>/dev/null)

if [ "$MODEL_CACHED" = "yes" ]; then
    echo "  Model already cached. Skipping download."
else
    "$VENV_DIR/bin/python" -c "
from faster_whisper import WhisperModel
print('  Downloading and caching model...')
WhisperModel('small', device='cpu', compute_type='int8')
print('  Model downloaded successfully.')
" 2>&1
    if [ $? -ne 0 ]; then
        echo ""
        echo "  WARNING: Model download failed. It will be downloaded on first use."
        echo "  (Make sure you have an internet connection.)"
    fi
fi

# --- Register MCP server + Install Cowork plugin ---
echo ""
echo "Step 6/6: Registering MCP server and installing Cowork plugin..."

# --- 6a: Register in Claude Desktop config ---
mkdir -p "$(dirname "$CLAUDE_CONFIG")"

if [ ! -f "$CLAUDE_CONFIG" ]; then
    echo '{}' > "$CLAUDE_CONFIG"
fi

# Backup existing config
cp "$CLAUDE_CONFIG" "${CLAUDE_CONFIG}.backup_$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true

"$VENV_DIR/bin/python" -c "
import json, os

config_path = os.path.expanduser('~/Library/Application Support/Claude/claude_desktop_config.json')
launch_path = os.path.expanduser('~/.legal-transcriber/launch.sh')

try:
    with open(config_path) as f:
        config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    config = {}

if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers']['legal-transcriber'] = {
    'command': 'bash',
    'args': [launch_path],
    'env': {}
}

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)

print('  MCP server registered in Claude Desktop.')
"

# --- 6b: Create standalone marketplace + install plugin ---
echo "  Installing Cowork plugin..."

# The plugin system discovers plugins from marketplace git repos at:
#   ~/.claude/plugins/marketplaces/{name}/
# Each marketplace needs a .claude-plugin/marketplace.json and must be a git repo.
# We create legal-transcriber as its own standalone marketplace so it won't be
# overwritten when other marketplaces sync from GitHub.

LT_MARKETPLACE="$PLUGIN_DIR/marketplaces/legal-transcriber"
LT_CACHE="$PLUGIN_DIR/cache/legal-transcriber/legal-transcriber/2.0.0"

# --- Create the marketplace repo ---
mkdir -p "$LT_MARKETPLACE/.claude-plugin"
mkdir -p "$LT_MARKETPLACE/skills/transcribe/scripts"

# marketplace.json — this is what the plugin system reads to discover plugins
cat > "$LT_MARKETPLACE/.claude-plugin/marketplace.json" << 'MP_EOF'
{
  "name": "legal-transcriber",
  "owner": {
    "name": "Josue Rodriguez"
  },
  "plugins": [
    {
      "name": "legal-transcriber",
      "source": "./",
      "description": "Transcribe audio/video recordings with speaker diarization into professional transcript documents",
      "version": "2.0.0",
      "author": {
        "name": "Josue Rodriguez"
      }
    }
  ]
}
MP_EOF

# plugin.json
cp "$SCRIPT_DIR/.claude-plugin/plugin.json" "$LT_MARKETPLACE/.claude-plugin/plugin.json"

# Skills
cp "$SCRIPT_DIR/skills/transcribe/SKILL.md" "$LT_MARKETPLACE/skills/transcribe/SKILL.md"
if [ -f "$SCRIPT_DIR/skills/transcribe/scripts/check_dependencies.py" ]; then
    cp "$SCRIPT_DIR/skills/transcribe/scripts/check_dependencies.py" "$LT_MARKETPLACE/skills/transcribe/scripts/check_dependencies.py"
fi
if [ -f "$SCRIPT_DIR/skills/transcribe/scripts/transcribe_audio.py" ]; then
    cp "$SCRIPT_DIR/skills/transcribe/scripts/transcribe_audio.py" "$LT_MARKETPLACE/skills/transcribe/scripts/transcribe_audio.py"
fi

# install.sh
cat > "$LT_MARKETPLACE/install.sh" << 'INST_EOF'
#!/bin/bash
echo "Legal Transcriber: checking installation..."
if [ -d "$HOME/.legal-transcriber/.venv" ]; then
    echo "Dependencies already installed at ~/.legal-transcriber/"
    echo "All good!"
    exit 0
else
    echo "ERROR: Dependencies not found."
    echo "Please run 'Install Legal Transcriber.command' first."
    exit 1
fi
INST_EOF
chmod +x "$LT_MARKETPLACE/install.sh"

# Initialize as a git repo (required for the plugin system)
cd "$LT_MARKETPLACE"
if [ ! -d ".git" ]; then
    git init --quiet
    git add -A
    git commit --quiet -m "Legal Transcriber v2.0.0"
fi
GIT_SHA=$(cd "$LT_MARKETPLACE" && git rev-parse HEAD 2>/dev/null || echo "0000000000000000000000000000000000000000")

echo "  Marketplace created at: $LT_MARKETPLACE"

# --- Copy to plugin cache ---
mkdir -p "$LT_CACHE/.claude-plugin"
mkdir -p "$LT_CACHE/skills/transcribe/scripts"
cp "$LT_MARKETPLACE/.claude-plugin/plugin.json" "$LT_CACHE/.claude-plugin/plugin.json"
cp "$LT_MARKETPLACE/.claude-plugin/marketplace.json" "$LT_CACHE/.claude-plugin/marketplace.json"
cp "$LT_MARKETPLACE/skills/transcribe/SKILL.md" "$LT_CACHE/skills/transcribe/SKILL.md"
if [ -f "$LT_MARKETPLACE/skills/transcribe/scripts/check_dependencies.py" ]; then
    cp "$LT_MARKETPLACE/skills/transcribe/scripts/check_dependencies.py" "$LT_CACHE/skills/transcribe/scripts/check_dependencies.py"
fi
if [ -f "$LT_MARKETPLACE/skills/transcribe/scripts/transcribe_audio.py" ]; then
    cp "$LT_MARKETPLACE/skills/transcribe/scripts/transcribe_audio.py" "$LT_CACHE/skills/transcribe/scripts/transcribe_audio.py"
fi
cp "$LT_MARKETPLACE/install.sh" "$LT_CACHE/install.sh"

echo "  Plugin cached at: $LT_CACHE"

# --- Register marketplace + plugin ---
"$VENV_DIR/bin/python" -c "
import json, os
from datetime import datetime, timezone

home = os.path.expanduser('~')
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
git_sha = '$GIT_SHA'

# 1. Register the marketplace in known_marketplaces.json
km_path = os.path.join(home, '.claude/plugins/known_marketplaces.json')
try:
    with open(km_path) as f:
        km = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    km = {}

km['legal-transcriber'] = {
    'source': {
        'source': 'local',
        'path': os.path.join(home, '.claude/plugins/marketplaces/legal-transcriber')
    },
    'installLocation': os.path.join(home, '.claude/plugins/marketplaces/legal-transcriber'),
    'lastUpdated': now
}

with open(km_path, 'w') as f:
    json.dump(km, f, indent=2)
print('  Marketplace registered in known_marketplaces.json')

# 2. Register plugin in installed_plugins.json
reg_path = os.path.join(home, '.claude/plugins/installed_plugins.json')
try:
    with open(reg_path) as f:
        reg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    reg = {'version': 2, 'plugins': {}}

if 'plugins' not in reg:
    reg['plugins'] = {}

cache_path = os.path.join(home, '.claude/plugins/cache/legal-transcriber/legal-transcriber/2.0.0')

reg['plugins']['legal-transcriber@legal-transcriber'] = [
    {
        'scope': 'user',
        'installPath': cache_path,
        'version': '2.0.0',
        'installedAt': now,
        'lastUpdated': now,
        'gitCommitSha': git_sha
    }
]

with open(reg_path, 'w') as f:
    json.dump(reg, f, indent=2)
print('  Plugin registered: legal-transcriber@legal-transcriber')
"

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "  Install location: $INSTALL_DIR"
echo "  MCP server: registered in Claude Desktop"
echo "  Cowork plugin: installed (legal-transcriber@legal-toolkit)"
echo ""
echo "  NEXT STEP: Quit and restart Claude Desktop."
echo "  Then open Cowork and say:"
echo "    'Transcribe this recording: /path/to/audio.mp3'"
echo ""

# --- Success dialog ---
osascript -e '
display dialog "Legal Transcriber installed successfully!\n\nNext step: Quit and restart Claude Desktop.\n\nThen open Cowork and ask Claude to transcribe any audio or video file." buttons {"OK"} default button 1 with title "Installation Complete" with icon note
' 2>/dev/null

exit 0
