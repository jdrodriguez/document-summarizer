---
name: process-emails
description: "Process email archives for e-discovery legal review. Parses .eml, .msg, .mbox files or directories of mixed email files. Extracts metadata, reconstructs threads, identifies duplicates, flags potentially privileged communications, and generates interactive communication network visualizations. Use when: (1) a user provides email files and asks to process them for legal review, (2) a user says 'process these emails', 'analyze this email archive', 'find privileged emails', 'map email communications', or 'prepare emails for review', (3) any e-discovery task involving email parsing, threading, deduplication, or privilege review, (4) a user needs communication network analysis from email archives."
---

# E-Discovery Email Processor

Parse email archives, reconstruct threads, detect duplicates, flag privilege, and visualize communication networks for legal review.

## Connector Check: ~~email

If an `~~email` connector (e.g. Microsoft 365, Gmail) is available:
- Ask: "I can connect directly to your email to pull messages, or you can provide exported email files (.eml, .mbox, .msg). Which would you prefer?"
- If connecting directly: ask for the folder, date range, sender/recipient, or subject filter. Pull matching emails via the connector. Proceed to processing with the retrieved messages.
- If providing files: proceed to the existing file detection flow.

If no connector is available, proceed directly to the existing input detection.

**Supported formats**: `.eml`, `.msg`, `.mbox`, directories of mixed email files
**Input modes**: single email file, mbox archive, OR a directory containing email files

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Agent Delegation (Conditional)

For large email archives (**100+ emails**), delegate result analysis to avoid context overflow.

### When to Delegate

- **Under 100 emails**: Process and present results directly — no delegation needed.
- **100+ emails**: After the processing script completes, delegate analysis of different output categories to subagents.

### Orchestrator Workflow (When Delegating)

1. **You handle**: Steps 1-4 below (validate, check deps, configure options, run processing).
2. **After processing completes**, launch **3 subagents in parallel** (Agent tool, `subagent_type: "general-purpose"`). Substitute the resolved `$OUTPUT_DIR` path literally into each agent's prompt — do not pass shell variable names:

| Agent | Task | Output File |
|-------|------|-------------|
| 1 | Analyze `privilege_flags.xlsx` — present flagged items with date, from, to, subject, flag reason | `$OUTPUT_DIR/privilege_analysis.md` |
| 2 | Analyze `threads.json` and `communication_network.html` — summarize thread patterns and key relationships | `$OUTPUT_DIR/thread_analysis.md` |
| 3 | Analyze `duplicates.xlsx` and `processing_summary.txt` — compile statistics and duplicate findings | `$OUTPUT_DIR/stats_analysis.md` |

3. **Include in each agent's prompt**: "Read the specified files from `$OUTPUT_DIR`. Write a clear analysis summary to `{output_file}`. For privilege flags, emphasize these are automated flags requiring human review."
4. **Collect and present**: Read analysis files, compile findings, and present to the user per Steps 5-7.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path. If not, ask: "Please provide the path to the email file, mbox archive, or directory of emails you want processed."
2. Determine if the path is a file or directory:
   - **File**: verify it exists and has a supported extension (`.eml`, `.msg`, `.mbox`) or is a directory
   - **Directory**: verify it exists; the script will find all supported email files inside it
3. If a directory, tell the user how many email files were found before proceeding.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).

### Step 3: Configure Processing Options

Ask the user for optional configuration:

1. **Attorney names** (for privilege detection): "Do you have a list of attorney names to flag? (comma-separated, or press enter to skip)"
2. **Privileged domains** (for privilege detection): "Any law firm email domains to flag? (comma-separated, e.g., 'lawfirm.com,counsel.org', or press enter to skip)"
3. **Extract attachments**: "Should I extract email attachments to a separate directory? (yes/no, default: yes)"

Build the command arguments based on responses.

### Step 4: Process Emails

Determine the output directory:
- **Single file**: `OUTPUT_DIR="{parent_dir}/{filename_without_ext}_ediscovery"`
- **Directory**: `OUTPUT_DIR="{directory_path}/_ediscovery_output"`

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/process_emails.py" \
  --input "<file_or_directory_path>" \
  --output-dir "$OUTPUT_DIR" \
  [--attorney-names "Smith,Jones"] \
  [--privileged-domains "lawfirm.com"] \
  [--extract-attachments]
```

The script prints JSON to stdout with processing results. Read this output to present findings.

### Step 5: Present Processing Summary

Read `$OUTPUT_DIR/processing_summary.txt` and present key findings:

1. **Total emails processed** and breakdown by format
2. **Threads reconstructed** with count
3. **Duplicates found** with count
4. **Privilege flags** - highlight this prominently with the count and a warning that these need human review
5. **Attachments extracted** (if enabled)
6. **Date range** of the email corpus

### Step 6: Highlight Privilege Flags

If any privilege flags were detected:

1. Read `$OUTPUT_DIR/privilege_flags.xlsx` summary
2. Present a table of flagged emails: Date, From, To, Subject, Flag Reason
3. **Emphasize**: "These are automated flags only. All flagged communications should be reviewed by qualified counsel before production."

### Step 7: Direct User to Outputs

List all generated files with descriptions:

- `email_metadata.xlsx` - Master spreadsheet with all email metadata
- `threads.json` - Reconstructed conversation threads
- `attachments/` - Extracted email attachments (if enabled)
- `communication_network.html` - Interactive network graph (open in browser)
- `communication_timeline.html` - Email volume over time (open in browser)
- `privilege_flags.xlsx` - Potentially privileged communications
- `duplicates.xlsx` - Identified duplicate messages
- `processing_summary.txt` - Full processing report

Tell the user: "Open the .html files in your browser for interactive visualizations."

### Step 8: Offer Report Generation

Ask: "Would you like me to generate a formal e-discovery processing report (.docx) summarizing these findings?"

If yes, use the `docx` skill to produce a professional report containing:
- Processing methodology
- Corpus statistics
- Communication network summary
- Privilege review summary
- Duplicate analysis
- Recommendations for review


## Accuracy and QA (Required)

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, invoke `/legal-toolkit:qa-check` on the work/output directory. Do not skip this step.

## Error Handling

- **Path not found**: Ask user to verify the path
- **Unsupported format**: Supported types are `.eml`, `.msg`, `.mbox`, or a directory of email files
- **Empty directory**: No supported email files found -- ask user to check the folder
- **Corrupt email**: Skip and log; report skipped files in summary
- **Missing optional deps**: libpff-python for .pst files is optional; inform user if .pst support is needed
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
