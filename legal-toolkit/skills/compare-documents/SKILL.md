---
name: compare-documents
description: "Compare two legal documents (PDF, DOCX, TXT) and generate detailed visual diffs with color-coded changes, change heatmaps, and structured change logs. Use when: (1) a user wants to compare two versions of a document, (2) a user says 'compare these documents', 'what changed between these versions', 'show me the differences', 'diff these files', or 'analyze the changes', (3) a user has an original and revised version of a contract, agreement, or policy, (4) a user needs to review edits made to a legal document, (5) a user wants a visual side-by-side comparison."
---

# Legal Document Comparison Suite

Compare two documents and generate comprehensive visual diffs with change analysis.

**Supported formats**: `.pdf`, `.docx`, `.txt`
**Input**: two document paths (file1 = original, file2 = revised)

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided two document paths. If not, ask: "Please provide the paths to the two documents you want to compare. The first should be the original, and the second the revised version."
2. Verify both files exist and have supported extensions (`.pdf`, `.docx`, `.txt`).
3. The two files do not need to be the same format -- you can compare a PDF against a DOCX.
4. Optionally ask for labels (e.g., "Original" and "Revised", or "Draft v1" and "Draft v2").

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).

### Step 3: Run Comparison

Determine the output directory based on file1's location:
- `OUTPUT_DIR="{file1_parent_dir}/{file1_name_without_ext}_comparison"`

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/compare_documents.py" \
  --file1 "<path_to_original>" \
  --file2 "<path_to_revised>" \
  --output-dir "$OUTPUT_DIR" \
  --labels "Original,Revised"
```

The script prints JSON to stdout with the comparison results. Progress messages go to stderr.

### Step 4: Present Summary

Read the script's JSON output. Present to the user:

1. **Overview**: "Compared {file1} against {file2}"
2. **Change statistics**:
   - Total changes: X additions, Y deletions, Z modifications
   - Percentage of document changed
   - Most-changed sections
3. **Key changes**: List the 5 most significant modifications (largest text changes)
4. **Warnings**: Flag any sections that were completely removed or added

Read `$OUTPUT_DIR/comparison_summary.txt` and present a condensed version.

### Step 5: Direct User to Visual Review

Tell the user:
> "I've generated a visual comparison. Open `$OUTPUT_DIR/comparison.html` in your browser to see the side-by-side diff with color coding:
> - **Green**: Added text
> - **Red**: Deleted text
> - **Yellow**: Modified text
>
> I also generated a change heatmap at `$OUTPUT_DIR/change_heatmap.html` showing which sections had the most changes."

### Step 6: Offer Next Steps

Present these options:

1. **Generate a formal change summary (.docx)**: Use the `docx` skill to create a Word document listing all changes with context.
2. **Focus on specific sections**: "Would you like me to analyze changes in a particular section in more detail?"
3. **Generate redline**: "For a tracked-changes version, use `/legal-toolkit:redline` with the same two files."
4. **Export change log**: "The structured change log is at `$OUTPUT_DIR/change_log.json` if you need it for further processing."

## Error Handling

- **Path not found**: Ask user to verify the paths
- **Unsupported format**: Supported types are `.pdf`, `.docx`, `.txt`
- **Identical documents**: Report that no differences were found
- **Empty extraction**: File may be scanned/image-only; suggest running `/legal-toolkit:ocr` first
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
