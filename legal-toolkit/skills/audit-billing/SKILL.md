---
name: audit-billing
description: "Audit law firm billing data (LEDES files, Excel invoices, CSV time entries) for compliance issues, block billing, excessive hours, rate violations, and billing anomalies. Use when: (1) a user provides billing files and asks for an audit or review, (2) a user says 'audit these invoices', 'review billing', 'check these LEDES files', 'analyze legal spend', or 'find billing issues', (3) any task involving law firm invoice review, outside counsel billing compliance, or legal spend analysis, (4) a user wants to identify block billing, vague descriptions, excessive hours, duplicate entries, or rate violations."
---

# Legal Billing Auditor

Audit law firm billing data for compliance issues, block billing, excessive hours, and rate violations.

**Supported formats**: LEDES 1998B (`.txt`, `.ledes`), Excel (`.xlsx`), CSV (`.csv`)
**Input modes**: single file OR a directory containing multiple billing files

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path to billing data. If not, ask: "Please provide the path to the billing file or folder you want audited."
2. Determine if the path is a file or directory:
   - **File**: verify it exists and has a supported extension (`.txt`, `.ledes`, `.xlsx`, `.csv`)
   - **Directory**: verify it exists; the script will find all supported files inside it
3. If a directory, tell the user which files were found before proceeding.
4. Ask if they have a rate caps file (JSON format) to compare against. This is optional.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).

### Step 3: Run Billing Audit

Determine the output directory:
- **Single file**: `OUTPUT_DIR="{parent_dir}/{filename_without_ext}_audit"`
- **Directory**: `OUTPUT_DIR="{directory_path}/_audit_results"`

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/audit_billing.py" \
  --input "<file_or_directory_path>" \
  --output-dir "$OUTPUT_DIR" \
  [--rate-caps "<rate_caps.json>"] \
  [--max-daily-hours 10]
```

The script prints a JSON summary to stdout. Capture and parse it.

### Step 4: Present Audit Summary

Read the output files and present findings to the user:

1. **Start with the summary**: Read `$OUTPUT_DIR/audit_summary.txt` and present the key metrics:
   - Total entries reviewed
   - Total spend analyzed
   - Number of flags by severity (HIGH / MEDIUM / LOW)
   - Estimated potential savings

2. **Highlight HIGH severity flags**: These require immediate attention. For each HIGH flag, explain:
   - What was flagged and why
   - The specific billing entry details
   - Recommended action

3. **Summarize MEDIUM and LOW flags**: Group by rule type and give counts with examples.

### Step 5: Direct to Detailed Outputs

Tell the user about the generated files:
- `flagged_entries.xlsx` - Full spreadsheet of all flagged entries for review
- `spend_dashboard.html` - Interactive charts showing spend patterns (open in browser)
- `audit_report.json` - Structured data for further processing

### Step 6: Offer Formal Report

Ask: "Would you like me to generate a formal audit report as a Word document (.docx)?"

If yes, use the `docx` skill (invoke with `/docx`) to produce a professional audit report containing:
1. **Title page**: "Billing Audit Report", date, matter information
2. **Executive Summary**: Key findings and estimated savings
3. **Methodology**: Audit rules applied
4. **Findings by Severity**: HIGH, MEDIUM, LOW sections with tables
5. **Spend Analysis**: Key metrics and trends
6. **Recommendations**: Action items based on findings
7. **Appendix**: Full list of flagged entries

## Error Handling

- **Path not found**: Ask user to verify the path
- **Unsupported format**: Supported types are `.txt`, `.ledes`, `.xlsx`, `.csv`
- **Empty directory**: No supported files found -- ask user to check the folder
- **Parse errors**: Some files may have non-standard formats; report which files failed and continue with others
- **No flags found**: Report clean audit -- no issues detected
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
