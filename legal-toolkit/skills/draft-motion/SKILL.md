---
name: draft-motion
description: "Draft filing-ready criminal defense motions (suppress, dismiss, exclude, limine, compel, sentencing memo) from case documents and optional templates. Reads case files (PDF, DOCX, TXT), extracts facts, fills templates, produces complete motions with cited facts, IRAC/CRAC arguments, evidence references, and prayer for relief. All case law flagged [VERIFY]. Use when: (1) a user says 'draft a motion', 'write a motion to suppress', 'prepare a motion to dismiss', or similar, (2) a user provides case documents and asks for a motion, (3) a user has a motion template to fill with case facts."
version: 1.0
author: Josue Rodriguez
tags: [motions, criminal-defense, drafting, suppress, dismiss, limine, compel]
---

# Motion Drafter

Draft filing-ready criminal defense motions from case documents and templates. Reads case files, extracts facts, and produces complete motions with case-specific arguments -- not summaries, not outlines, full motions ready for attorney review.

## Skill Directory

Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory.

## Agent Delegation (Conditional)

For cases with **5+ source documents** or **multiple motions requested**, delegate the drafting work to subagents to avoid exceeding the context window.

### When to Delegate

- **5+ case documents**: The combined text extraction + motion drafting exceeds a single agent's context. Delegate.
- **Multiple motions from one case**: Each motion should be drafted by a separate agent. Delegate.
- **Single motion from 1-4 documents**: You may draft directly without delegation.

### Orchestrator Workflow (When Delegating)

1. **You handle**: Steps 1-2 below (gather inputs, extract text from all documents).
2. **Save extracted text**: Create `WORK_DIR` as `{parent_dir}/{case_name}_motion_work`.
   - Write all extracted text to `$WORK_DIR/case_materials.md` with source document headers.
   - Write motion type, jurisdiction, template structure, and drafting preferences to `$WORK_DIR/motion_context.md`.
   - Run `mkdir -p "$WORK_DIR/sections"`.
3. **For a single motion**, launch **2 subagents in parallel**:

| Agent | Task | Output File |
|-------|------|-------------|
| 1 | Caption + Statement of Facts + Evidence References (3a, 3b, 3e) | `$WORK_DIR/sections/motion_facts.md` |
| 2 | Legal Standard + Argument + Prayer for Relief (3c, 3d, 3f) | `$WORK_DIR/sections/motion_law.md` |

4. **For multiple motions**, launch **one agent per motion**, each drafting a complete motion and writing to `$WORK_DIR/sections/motion_{type}.md`.
5. **Include in each agent's prompt**: Copy the relevant format specifications from the `## Step 3: Draft the Motion` section below. Also include: "Read `$WORK_DIR/case_materials.md` and `$WORK_DIR/motion_context.md`. Follow the template if provided. Fill all caption fields from the case file — use [FILL] for missing values. Mark all case law as [VERIFY]. Write output to `{output_file}`."
6. **Collect and assemble**: Read output files in order — `motion_facts.md` first (caption, statement of facts, evidence references), then `motion_law.md` (legal standard, argument, prayer for relief). Merge into a single complete motion document. Present with the gaps/verification checklist from Step 4.

## Step 1: Gather Inputs

Ask the user for the following (if not already provided):

1. **Case documents** (required) -- police report, arrest report, body cam transcript, witness statements, lab results, discovery documents. Can be file paths or pasted text.
2. **Motion type** (required) -- suppress, dismiss, exclude, limine, compel discovery, sentencing memorandum. If unclear from context, ask.
3. **Motion template** (optional) -- the firm's template for this motion type. If provided, follow its structure exactly.
4. **Jurisdiction** (optional but recommended) -- state and court for correct statutory citations.
5. **Drafting preferences** (optional) -- argument structure (IRAC/CRAC), citation style (inline/footnotes), tone, page length target, firm-specific conventions.
6. **Knowledge base** (optional) -- NHTSA manual, state statutes, prior motions for cross-referencing.

## Step 2: Extract Text from Case Documents

If the user provided file paths, extract text before drafting.

### For each provided file:

**PDF files:**
1. First, attempt text extraction using Python:
   ```bash
   python3 -c "
   import sys
   try:
       import fitz
       doc = fitz.open(sys.argv[1])
       text = ''
       for page in doc:
           text += page.get_text()
       if len(text.strip()) < 50:
           print('SCANNED_PDF', file=sys.stderr)
           sys.exit(1)
       print(text)
   except Exception as e:
       print(f'ERROR: {e}', file=sys.stderr)
       sys.exit(1)
   " "<file_path>"
   ```
2. If the PDF appears scanned (exit code 1 with SCANNED_PDF), **delegate OCR to a subagent**: tell the user "This PDF appears to be scanned. Delegating OCR to extract text." Launch an Agent (`subagent_type: "general-purpose"`) with prompt: "Run `/legal-toolkit:extract-text` on `{file_path}` and write the extracted text to `$WORK_DIR/{filename}_ocr.txt`." Continue processing other files while the OCR agent works.

**DOCX files:**
```bash
python3 -c "
import sys
from docx import Document
doc = Document(sys.argv[1])
for p in doc.paragraphs:
    print(p.text)
for table in doc.tables:
    for row in table.rows:
        print('\t'.join(cell.text for cell in row.cells))
" "<file_path>"
```

**TXT/MD files:**
Read directly with the Read tool.

**If the user pasted text directly:** Skip extraction, use the text as-is.

Combine all extracted text into a single case file reference, preserving source file names for citation purposes (e.g., "Arrest Report, p. 3").

## Step 3: Draft the Motion

You are a criminal defense attorney drafting a motion for filing. If a motion template was provided, use it as the structural guide. Draw all facts exclusively from the case documents. Produce a complete, filing-ready draft.

### 3a. Caption and Heading

Fill in every field from the case file: court name, case number, judge, defendant name, State/People/Commonwealth (match jurisdiction), motion title. No placeholders. If information is missing from the case file, flag it as **[FILL -- not found in case file]** rather than guessing.

### 3b. Statement of Facts

Draw exclusively from the case file. Include specific dates, times, locations, officer names, and actions. Cite page numbers from the source documents throughout. Write as factual narrative -- this is advocacy, not a neutral recitation. Emphasize facts favorable to the defense. Include unfavorable facts where necessary for completeness, but frame them strategically.

### 3c. Legal Standard

State the applicable legal standard for the motion type. Reference the relevant constitutional provision, statute, or rule. If the template includes a legal standard section, follow its structure. Mark any case citations with **[VERIFY]**.

### 3d. Argument

Structure arguments following the template and the preferred format (IRAC, CRAC, or the template's own structure). For each argument:

- **Issue:** State the specific legal issue.
- **Rule:** Cite the applicable rule, statute, or constitutional provision. Mark case citations **[VERIFY]**.
- **Application:** Apply the rule to THIS case's specific facts. Quote directly from the police report or case documents with page citations. Do not use generic template language where case-specific facts are available.
- **Conclusion:** State what the court should find.

If the knowledge base includes the NHTSA manual, cite specific manual sections and pages when arguing field sobriety test deviations. If state statutes are available, cite specific sections and subsections.

Order arguments by strength -- lead with the most compelling argument unless the template specifies a different order.

### 3e. Evidence References

When citing officer conduct, witness statements, or test results, quote directly from the source document and include the page number. Format: "(Arrest Report, p. 3)" or "(Body Cam Transcript, 01:23:45)."

### 3f. Prayer for Relief

Match the template's format. Specify the exact relief requested: suppress specific evidence, dismiss specific charges, exclude specific testimony, preclude specific arguments at trial.

## Step 4: Present Draft for Review

Present the complete draft to the attorney. After the draft, include:

1. **Gaps and Outstanding Questions** -- list every [FILL], [NEEDS INVESTIGATION], and [CASE LAW RESEARCH NEEDED] item.
2. **Verification Checklist** -- list every [VERIFY] citation that needs Westlaw/Lexis confirmation.
3. **Suggested Strengthening** -- note arguments that could be stronger with additional evidence or research.

Ask: "Want me to revise any sections, strengthen specific arguments, adjust the tone, or reorder the arguments?"


## Accuracy and QA (Required)

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, invoke `/legal-toolkit:qa-check` on the work/output directory. Do not skip this step.

## Quality Standards

- **No placeholders in the output.** Every [CLIENT NAME], [CASE NUMBER], [COURT], [JUDGE] field must be filled from the case file. If a value cannot be found, use [FILL -- not found in case file] so the attorney knows to add it.
- **Every case citation gets [VERIFY].** No exceptions. Do not present any case citation as confirmed. Format: *State v. Johnson*, 123 So.3d 456 (Fla. 2020) [VERIFY]. Where authority would strengthen an argument but no specific case is known, mark [CASE LAW RESEARCH NEEDED] with a note on what type of authority to look for.
- **Facts come from the case file, not from training data.** Do not add facts, dates, or details not present in the case documents. If the police report does not mention Miranda warnings, do not assume they were or were not given -- flag it as [NEEDS INVESTIGATION].
- **Follow the template structure.** If the firm provided a template, match its section order, heading style, and formatting unless explicitly told otherwise.
- **Write in the firm's voice.** If the firm writes assertively ("The officer violated..."), match that. If the firm writes formally ("The evidence demonstrates that..."), match that. Review any prior motions for voice calibration.
- **Target the firm's typical page length.** If the firm's motions to suppress run 8-12 pages, produce 8-12 pages. Do not produce a 3-page summary when the firm files 10-page motions.

## Supported Motion Types

- **Motion to Suppress** -- challenge evidence obtained through constitutional violations (illegal stop, improper search, Miranda violations, flawed field sobriety tests)
- **Motion to Dismiss** -- argue the State cannot prove an element of the offense, procedural defects, speedy trial violations, statute of limitations
- **Motion to Exclude** -- keep specific evidence out (prejudicial, unreliable, foundation issues, chain of custody failures)
- **Motion in Limine** -- pre-trial rulings on evidence admissibility (prior bad acts, prejudicial testimony, unreliable expert opinions)
- **Motion to Compel Discovery** -- force the State to produce materials it has withheld (body cam, calibration records, training records, dispatch logs)
- **Sentencing Memorandum** -- present mitigation factors, character evidence, and sentencing recommendations

Adapt the output structure for each motion type. A motion to compel looks different from a motion to suppress -- follow the template provided.

## Edge Cases

- **No motion template provided:** Use a standard motion structure for the jurisdiction. Note: "No firm template found -- using standard format for [jurisdiction]. Provide your firm's motion template for future drafts that match your formatting and argument style."
- **Case file is incomplete:** Draft what you can. Flag every gap: [NEEDS INVESTIGATION -- arrest report does not document whether Miranda warnings were administered]. List all missing information in the "Gaps and Outstanding Questions" section.
- **Multiple motion types from one case:** Draft each motion separately. Cross-reference where arguments overlap -- if the motion to suppress and the motion in limine both rely on the same issue, note the connection.
- **Jurisdiction differs from template:** Adapt statutory citations and procedural references to the correct jurisdiction. Note: "Template appears to be from [State A]. Case is in [State B]. Statutory citations have been adapted. Attorney should verify procedural requirements for [State B]."
- **Template has tracked changes or formatting artifacts:** Work from the substance, not the formatting. Note any sections where the template's intent was unclear due to markup.
- **Scanned PDF case documents:** Delegate OCR to a subagent as described in Step 2. Inform the user: "Case document appears to be scanned. Delegating OCR to extract text."
