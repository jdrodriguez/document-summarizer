#!/bin/bash
# Install the document-summarizer plugin dependencies.
#
# Preferred installation method:
#   In Claude Code, run: /plugin install document-summarizer
#
# This script is a fallback that:
#   1. Symlinks the skill into ~/.claude/skills/ (legacy method)
#   2. Installs Python dependencies
#   3. Installs npm dependencies
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SOURCE="$SCRIPT_DIR/skills/summarize"
SKILLS_DIR="$HOME/.claude/skills"
SKILL_LINK="$SKILLS_DIR/document-summarizer"

# Ensure skills directory exists
mkdir -p "$SKILLS_DIR"

# Remove existing link/dir if present
if [ -L "$SKILL_LINK" ] || [ -e "$SKILL_LINK" ]; then
    echo "Removing existing: $SKILL_LINK"
    rm -rf "$SKILL_LINK"
fi

# Create symlink
ln -s "$SKILL_SOURCE" "$SKILL_LINK"
echo "Installed: $SKILL_LINK -> $SKILL_SOURCE"

# Check Python dependencies
echo ""
echo "Checking Python dependencies..."
python3 "$SKILL_SOURCE/scripts/check_dependencies.py"
dep_status=$?

if [ $dep_status -eq 2 ]; then
    echo ""
    echo "Some Python dependencies could not be installed. Check the errors above."
    exit 1
fi

# Check Node.js npm dependencies
echo ""
echo "Checking npm dependencies..."
npm_missing=()
for pkg in docx pdfkit; do
    if ! node -e "require('$pkg')" 2>/dev/null; then
        npm_missing+=("$pkg")
    fi
done

if [ ${#npm_missing[@]} -gt 0 ]; then
    echo "Installing npm packages: ${npm_missing[*]}"
    npm install -g "${npm_missing[@]}"
    if [ $? -ne 0 ]; then
        echo "Failed to install npm packages. Try manually: npm install -g ${npm_missing[*]}"
        exit 1
    fi
else
    echo "All npm dependencies already satisfied."
fi

echo ""
echo "Ready to use! Open Claude Code and invoke with: /document-summarizer:summarize"
