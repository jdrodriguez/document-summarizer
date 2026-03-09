#!/bin/bash
# Install the legal-toolkit plugin dependencies.
#
# This script checks and installs dependencies for all skills in the toolkit.
# Each skill has its own check_dependencies.py that handles its specific packages.
# Dependencies are also auto-installed on first use of each skill.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/skills"

echo "=== Legal Toolkit Installer ==="
echo ""

# Check that Python 3 is available
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 is required but not found."
    echo "Install Python 3 from https://www.python.org/downloads/"
    exit 1
fi

echo "Python: $(python3 --version)"
echo ""

# Check npm (needed for docx output generation)
if command -v npm &>/dev/null; then
    echo "npm: $(npm --version)"
    # Install shared npm packages
    npm_missing=()
    for pkg in docx; do
        if ! node -e "require('$pkg')" 2>/dev/null; then
            npm_missing+=("$pkg")
        fi
    done
    if [ ${#npm_missing[@]} -gt 0 ]; then
        echo "Installing npm packages: ${npm_missing[*]}"
        npm install -g "${npm_missing[@]}" || echo "WARNING: npm install failed. .docx output may not work."
    else
        echo "npm packages: OK"
    fi
else
    echo "WARNING: npm not found. .docx output generation may not work."
fi

echo ""
echo "=== Checking skill dependencies ==="
echo ""

# Run each skill's dependency checker
failed=0
for skill_dir in "$SKILLS_DIR"/*/; do
    skill_name=$(basename "$skill_dir")
    dep_script="$skill_dir/scripts/check_dependencies.py"

    if [ -f "$dep_script" ]; then
        echo "--- $skill_name ---"
        python3 "$dep_script"
        status=$?
        if [ $status -eq 2 ]; then
            echo "  WARNING: Some dependencies for $skill_name could not be installed."
            failed=1
        elif [ $status -eq 1 ]; then
            echo "  Installed missing dependencies for $skill_name."
        else
            echo "  All dependencies satisfied."
        fi
        echo ""
    fi
done

if [ $failed -eq 1 ]; then
    echo "Some skills had dependency issues. They will attempt to install on first use."
    echo ""
fi

echo "=== Installation complete ==="
echo ""
echo "Available commands:"
echo "  /legal-toolkit:summarize              - Summarize documents"
echo "  /legal-toolkit:transcribe             - Transcribe audio/video"
echo "  /legal-toolkit:calculate-deadlines    - Calculate court deadlines"
echo "  /legal-toolkit:ocr                    - OCR scanned documents"
echo "  /legal-toolkit:redline                - Generate contract redlines"
echo "  /legal-toolkit:compare-documents      - Compare documents"
echo "  /legal-toolkit:build-chronology       - Build case chronology"
echo "  /legal-toolkit:index-deposition       - Index depositions"
echo "  /legal-toolkit:process-emails         - E-discovery email processing"
echo "  /legal-toolkit:map-entities           - Entity & relationship mapping"
echo "  /legal-toolkit:process-intake         - Client intake processing"
echo "  /legal-toolkit:audit-billing          - Billing audit"
echo "  /legal-toolkit:analyze-financials     - Financial forensics"
echo "  /legal-toolkit:analyze-communications - Communication analysis"
echo "  /legal-toolkit:analyze-photos         - Evidence photo analysis"
echo "  /legal-toolkit:search-records         - Public records research"
