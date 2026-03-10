---
name: redline
description: "Generate tracked-changes redline documents from two contract versions (.docx) with risk analysis and change categorization. Use when: (1) a user wants to create a redline of two contract versions, (2) a user says 'redline these contracts', 'generate tracked changes', 'create a redline', 'show me what changed in this contract', or 'compare these contract versions', (3) a user has original and revised .docx contracts and needs Word tracked-changes markup, (4) a user needs risk analysis of contract changes, (5) a user wants to identify material vs administrative changes in a contract revision."
---

# Contract Redline Generator

Generate Word documents with native tracked-changes markup from two contract versions, with risk-rated change analysis.

**Supported format**: `.docx` (both files must be Word documents)
**Input**: two .docx paths (original contract and revised contract)

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided two .docx file paths. If not, ask: "Please provide the paths to the original and revised contract (.docx files). The first should be the original, and the second the revised version."
2. Verify both files exist and have the `.docx` extension.
3. If a user provides PDFs or other formats, suggest converting to .docx first, or suggest using `/legal-toolkit:doc-diff` which supports more formats.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).

### Step 3: Generate Redline

Determine the output directory based on the original file's location:
- `OUTPUT_DIR="{original_parent_dir}/{original_name_without_ext}_redline"`

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/generate_redline.py" \
  --original "<path_to_original.docx>" \
  --revised "<path_to_revised.docx>" \
  --output-dir "$OUTPUT_DIR"
```

The script prints JSON to stdout with the redline results. Progress messages go to stderr.

### Step 4: Present Material Changes

Read the script's JSON output and `$OUTPUT_DIR/material_changes.txt`. Present to the user:

1. **Overview**: "Generated redline comparing {original} against {revised}"
2. **Change summary**:
   - Total changes: X
   - By risk level: HIGH (X), MEDIUM (Y), LOW (Z)
   - By category: Substantive (X), Administrative (Y), Risk-relevant (Z)
3. **HIGH-risk changes** (present each one):
   - What changed (old text -> new text)
   - Where in the document (section/paragraph)
   - Why it's flagged as high risk
4. **MEDIUM-risk changes**: Summarize the themes

Read `$OUTPUT_DIR/redline_summary.txt` for the full statistics.

### Step 5: Direct User to Redline Document

Tell the user:
> "The redline document is at `$OUTPUT_DIR/redline.docx`. Open it in Microsoft Word to:
> - See insertions (red underline) and deletions (red strikethrough)
> - Accept or reject individual changes using Word's Review tab
> - Navigate between changes using the Previous/Next buttons
>
> The document uses native Word tracked-changes markup, so all standard Word review features work."

### Step 6: Offer AI Analysis

Present these options:

1. **Deep analysis of high-risk changes**: "Would you like me to analyze each high-risk change in detail? I can explain the legal implications of each modification."
2. **Generate a change memo**: Use the `docx` skill to create a formal change memorandum suitable for client review, listing all material changes with risk ratings.
3. **Compare with original summary**: "If you have a summary of the original contract, I can highlight which key terms were affected by the changes."
4. **Visual comparison**: "For a visual side-by-side diff, use `/legal-toolkit:doc-diff` with these same files."


## Accuracy and QA (Required)

Read the full QA protocol at `$SKILL_DIR/../../QA_AND_ACCURACY.md` and follow it.

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, launch a QA agent (`subagent_type: "general-purpose"`) following the protocol in the file above. The QA agent reads all outputs and source materials, checks for hallucination and accuracy, and writes `qa_review.md`. Apply any fixes before presenting to the user.

## Error Handling

- **Path not found**: Ask user to verify the paths
- **Not .docx format**: This tool requires .docx files. Suggest `/legal-toolkit:doc-diff` for PDFs and other formats.
- **Identical documents**: Report that no differences were found
- **Corrupted .docx**: If python-docx cannot open the file, report the error and suggest the user verify the file opens in Word
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
