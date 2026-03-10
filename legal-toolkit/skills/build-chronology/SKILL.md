---
name: build-chronology
description: "Build a master case chronology from legal documents. Extracts all dated events from PDFs, DOCX, TXT, and MD files, builds an interactive timeline, detects gaps and date conflicts, and produces a comprehensive chronology spreadsheet. Use when: (1) a user provides a directory of case documents and asks for a chronology or timeline, (2) a user says 'build a chronology', 'create a timeline', 'extract dates from these documents', 'find all events', or 'case timeline', (3) any litigation support task requiring date extraction and event tracking across multiple documents, (4) a user needs gap analysis or date conflict detection across case files."
---

# Case Chronology Builder

Extract dated events from legal documents and build a master case chronology with interactive timeline visualization.

**Supported formats**: `.pdf`, `.docx`, `.txt`, `.md`
**Input modes**: single file OR a directory containing multiple files

## Connector Check: ~~cloud storage

If a `~~cloud storage` connector (e.g. Box, Dropbox, Google Drive) is available:
- Ask: "I can pull documents directly from [storage name] to build the chronology, or you can provide file paths. Which would you prefer?"
- If pulling from cloud storage: ask for the matter folder. List documents found. Pull and extract dates and events from all documents in the folder.
- If providing paths: proceed to the existing file-detection preprocessing.

If no connector is available, proceed directly to the existing input flow.

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path. If not, ask: "Please provide the path to the case documents (file or folder) you want to build a chronology from."
2. Determine if the path is a file or directory:
   - **File**: verify it exists and has a supported extension (`.pdf`, `.docx`, `.txt`, `.md`)
   - **Directory**: verify it exists; the script will find all supported files inside it recursively
3. If a directory, tell the user which files were found before proceeding.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).
- Note: On first run, the spaCy `en_core_web_sm` model (~12 MB) will be downloaded automatically.

### Step 3: Build the Chronology

Set up the output directory based on input type:
- **Single file**: `OUTPUT_DIR="{parent_dir}/{filename_without_ext}_chronology"`
- **Directory**: `OUTPUT_DIR="{directory_path}/_chronology"`

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/build_chronology.py" \
  --input "<file_or_directory_path>" \
  --output-dir "$OUTPUT_DIR"
```

Optional flags:
- `--start-date 2020-01-01` — filter events before this date
- `--end-date 2026-12-31` — filter events after this date
- `--event-types all` — comma-separated list of event types to include (default: all)

The script prints JSON to stdout with the chronology results. Read the JSON output to get the summary.

### Step 4: Present Chronology Summary

Read `$OUTPUT_DIR/chronology_summary.txt` and present to the user:
- Total events extracted
- Date range covered
- Number of documents processed
- Events by type breakdown
- Number of gaps detected
- Number of date conflicts found

### Step 5: Highlight Date Conflicts and Gaps

Read `$OUTPUT_DIR/date_conflicts.json` and `$OUTPUT_DIR/gap_analysis.json`.

**Date conflicts**: Present each conflict clearly:
- "Document A says [event] happened on [date1], but Document B says [date2]"
- Ask the user which date is correct, or flag for manual review

**Gaps**: Present significant gaps:
- "No documented events between [date1] and [date2] ([N] days)"
- Suggest the user check for missing documents covering these periods

### Step 6: Direct to Interactive Timeline

Tell the user:
> Your interactive timeline is ready at: `$OUTPUT_DIR/timeline.html`
> Open it in a browser to explore the chronology visually. Events are color-coded by type and you can zoom in on any period.

Also mention the full outputs:
- `chronology.xlsx` — master spreadsheet with all events
- `chronology.json` — structured data for programmatic use
- `gap_analysis.json` — gap details
- `date_conflicts.json` — conflicting dates

### Step 7: Large Document Sets (Multi-Agent Pattern)

For directories with **10+ documents**, use parallel agents to speed up processing:

1. **Split documents** into groups of ~5 files each
2. **Spawn agents in parallel** via Task tool (`subagent_type: "general-purpose"`), each running:

   ```
   You are extracting dated events from legal documents.

   Run this command to process your assigned documents:

   python3 "$SKILL_DIR/scripts/build_chronology.py" \
     --input "<file_path_1>" --input "<file_path_2>" ... \
     --output-dir "$OUTPUT_DIR/agent_{N}" \
     [--start-date ...] [--end-date ...]

   After the script completes, read the JSON output from stdout
   and confirm completion with the list of events found.
   ```

3. **Merge results**: After all agents complete, read each agent's `chronology.json` and merge into a single master chronology. Re-run gap analysis and conflict detection on the merged data.

### Step 8: Offer Formal Narrative

Ask the user: "Would you like me to generate a formal chronology narrative as a Word document (.docx)?"

If yes, use the npm `docx` package to generate a professional Word document containing:
1. Title: "Case Chronology: [case name or directory name]"
2. Date range and document summary
3. Chronological narrative with citations to source documents
4. Gap analysis section
5. Date conflict notes
6. Appendix: full event table


## Accuracy and QA (Required)

Read the full QA protocol at `$SKILL_DIR/../../QA_AND_ACCURACY.md` and follow it.

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, launch a QA agent (`subagent_type: "general-purpose"`) following the protocol in the file above. The QA agent reads all outputs and source materials, checks for hallucination and accuracy, and writes `qa_review.md`. Apply any fixes before presenting to the user.

## Error Handling

- **Path not found**: Ask user to verify the path
- **Unsupported format**: Supported types are `.pdf`, `.docx`, `.txt`, `.md`
- **Empty directory**: No supported files found — ask user to check the folder
- **Empty extraction**: File may be scanned/image-only. **Delegate OCR to a subagent**: launch an Agent (`subagent_type: "general-purpose"`) with prompt: "Run `/legal-toolkit:extract-text` on `{file_path}` and write the extracted text to `$OUTPUT_DIR/{filename}_ocr.txt`." Re-run chronology on the OCR output.
- **No dates found**: Document may not contain recognizable dates; suggest manual review
- **spaCy model missing**: The check_dependencies.py script auto-downloads it; if still failing, suggest `python3 -m spacy download en_core_web_sm`
- **Agent failure**: Process the unprocessed documents directly
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)

## Connector Action: ~~knowledge base

If a `~~knowledge base` connector (e.g. Notion) is available, offer to save the chronology:
> "Want me to save this chronology to Notion?"
If yes, create a structured page with the chronology table and source citations, linked to the matter.
