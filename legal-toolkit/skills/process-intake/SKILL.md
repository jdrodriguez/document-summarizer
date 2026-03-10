---
name: process-intake
description: "Process raw client intake data into structured legal intake outputs. Handles free-form notes, JSON form data, DOCX documents, and CSV files. Uses NLP to extract client information, classify matter type, prepare conflict check lists, generate document checklists, and calculate statute of limitations deadlines. Use when: (1) a user provides intake notes or client information and asks to process it, (2) a user says 'process this intake', 'structure these client notes', 'prepare conflict check', 'what documents do we need', or 'check statute of limitations', (3) any new client onboarding task requiring structured data extraction from raw notes, (4) a user needs to convert unstructured intake information into organized client profiles and action items."
---

# Legal Intake Processor

Process raw client intake data into structured profiles, conflict checks, document checklists, and statute of limitations warnings.

**Supported formats**: `.txt`, `.md` (free-form notes), `.json` (structured form data), `.docx` (intake forms), `.csv` (batch intake)
**Input modes**: single file with intake data

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path. If not, ask: "Please provide the path to the intake notes file (TXT, JSON, DOCX, or CSV)."
2. Verify the file exists and has a supported extension (`.txt`, `.md`, `.json`, `.docx`, `.csv`)
3. If CSV, note that this will be processed as batch intake (multiple clients).

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).
- Note: On first run, the spaCy model `en_core_web_sm` (~12MB) will be downloaded automatically.

### Step 3: Configure Processing Options

Ask the user for optional configuration:

1. **Matter type**: "Do you know the matter type? (personal_injury, family_law, criminal_defense, immigration, corporate, real_estate, employment, estate_planning, bankruptcy, intellectual_property, or 'auto' to detect automatically)"
   - Default: `auto`
2. **Jurisdiction**: "What jurisdiction? (e.g., CA, NY, TX, or press enter to skip)"
   - Default: none (SOL calculation will be skipped if not provided)

### Step 4: Process Intake

Determine the output directory:
- `OUTPUT_DIR="{parent_dir}/{filename_without_ext}_intake"`

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/process_intake.py" \
  --input "<file_path>" \
  --output-dir "$OUTPUT_DIR" \
  [--matter-type auto] \
  [--jurisdiction CA]
```

The script prints JSON to stdout with processing results. Read this output to present findings.

### Step 5: Present Structured Client Profile

Read `$OUTPUT_DIR/client_profile.json` and present:

1. **Client name** and contact information
2. **Matter type** (detected or provided) with confidence level
3. **Key dates**: incident date, consultation date, any deadlines
4. **Monetary amounts**: damages claimed, fees discussed
5. **Parties involved**: opposing parties, witnesses, relevant organizations
6. **Brief matter summary**

### Step 6: Highlight Conflict Check Entities

Read `$OUTPUT_DIR/conflict_check.xlsx` and present:

1. Table of all entities requiring conflict checking: Name, Type (person/org), Role, Name Variations
2. **Emphasize**: "Run these names through your firm's conflict check system before proceeding."

### Step 7: Present Document Checklist

Read `$OUTPUT_DIR/document_checklist.json` and present:

1. Matter-type-specific document checklist as a formatted list
2. Mark any documents the client mentioned having
3. Highlight critical documents needed first

### Step 8: Statute of Limitations Warning

Read `$OUTPUT_DIR/sol_warning.txt` (if it exists) and present:

1. **Applicable SOL deadlines** based on matter type and jurisdiction
2. **Days remaining** for each deadline
3. **Warning level**: urgent (< 30 days), caution (< 90 days), normal
4. **Emphasize**: "These are estimated deadlines. Verify with current statutes for your specific jurisdiction."

### Step 9: Offer Report Generation

Ask: "Would you like me to generate a formal intake report (.docx) for the client file?"

If yes, use the `docx` skill to produce a professional intake report containing:
- Client profile
- Matter summary
- Conflict check list
- Document checklist
- SOL warnings
- Next steps and recommendations


## Accuracy and QA (Required)

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, invoke `/legal-toolkit:qa-check` on the work/output directory. Do not skip this step.

## Error Handling

- **Path not found**: Ask user to verify the path
- **Unsupported format**: Supported types are `.txt`, `.md`, `.json`, `.docx`, `.csv`
- **Empty file**: No content to process -- ask user to check the file
- **Insufficient data**: If very little information could be extracted, present what was found and ask for additional input
- **Unknown matter type**: If auto-detection fails, ask user to specify the matter type manually
- **No jurisdiction**: SOL calculation requires jurisdiction; inform user it was skipped
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
