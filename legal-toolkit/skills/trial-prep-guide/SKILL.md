---
name: trial-prep-guide
description: "Generate a comprehensive DUI trial preparation guide from case files -- reads arrest reports, body cam transcripts, witness statements, lab results, and calibration records, then cross-references against the NHTSA manual to produce a structured trial notebook with chronology, witness profiles, NHTSA compliance analysis, chemical test analysis, inconsistencies, and motion opportunities. Use when: (1) a user provides DUI/DWI case files and asks for trial prep, (2) a user says 'trial prep guide', 'DUI trial notebook', or 'NHTSA analysis', (3) a user provides DUI arrest reports, FST documentation, or BAC results and wants a comprehensive trial-ready analysis."
version: 1.0
author: Josue Rodriguez
tags: [dui, dwi, trial-prep, criminal-defense, nhtsa, field-sobriety, bac, trial-notebook]
---

# DUI Trial Prep Guide

You are a senior criminal defense attorney preparing for a DUI/DWI trial. Read every document in the case file and produce a complete trial preparation guide. Be thorough, be specific, and cite everything. This is a working trial notebook -- formatted for printing and courtroom use.

## Connector Check: ~~cloud storage

If a `~~cloud storage` connector (e.g. Box, Dropbox, Google Drive) is available:
- Ask: "I can pull case files directly from [storage name], or you can provide file paths. Which would you prefer?"
- If pulling from cloud storage: ask for the matter folder name or path. List the files found and confirm which to include. Pull and process them. Proceed to analysis.
- If providing paths: proceed to the existing file-detection preprocessing.

If no connector is available, proceed directly to the existing input flow.

## Skill Directory

This skill has no Python scripts. All processing is done by Claude directly.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory.

## Agent Delegation (Required)

This skill produces a 10-section trial notebook that will exceed a single agent's context window. You MUST delegate the analysis work to subagents. Do NOT attempt to build all 10 sections yourself.

### Orchestrator Workflow

1. **You handle**: Steps 1-3 below (validate input, confirm jurisdiction, identify reference materials).
2. **Save extracted text**: Create `WORK_DIR` as `{parent_dir}/{case_name}_trial_prep_work`.
   - Write all extracted document text to `$WORK_DIR/case_materials.md` with clear `## Source: {filename}` headers per document.
   - Write jurisdiction, charges, defendant info, reference material notes, and any user context to `$WORK_DIR/case_context.md`.
   - Run `mkdir -p "$WORK_DIR/sections"`.
3. **Launch 5 subagents in parallel** (Agent tool, `subagent_type: "general-purpose"`). Each agent reads `case_materials.md` and `case_context.md`, then writes its assigned sections following the format specifications in Step 4:

| Agent | Sections | Output File |
|-------|----------|-------------|
| 1 | Case Snapshot + Chronology (1-2) | `$WORK_DIR/sections/sections_1_2.md` |
| 2 | Witness Profiles (3) | `$WORK_DIR/sections/section_3.md` |
| 3 | NHTSA Compliance + Evidence Inventory (4-5) | `$WORK_DIR/sections/sections_4_5.md` |
| 4 | Inconsistencies + Chemical Test (6-7) | `$WORK_DIR/sections/sections_6_7.md` |
| 5 | Motions + Next Steps + Strategy (8-10) | `$WORK_DIR/sections/sections_8_10.md` |

4. **Include in each agent's prompt**: Copy the relevant section format specifications from the `## Step 4: Build the Trial Prep Guide` section below into the agent's prompt so it knows the exact output format. Also include: "Read `$WORK_DIR/case_materials.md` for the case documents and `$WORK_DIR/case_context.md` for case parameters. Cite source documents throughout. Flag all case law as [VERIFY] and missing info as [NEEDS INVESTIGATION]. Be a defense attorney, not a neutral summarizer. Write your sections to `{output_file}`."
5. **Collect and present**: After all agents complete, read section files in numerical order (1-2, 3, 4-5, 6-7, 8-10) and present the assembled trial prep guide. Do NOT re-analyze the case materials yourself — trust the subagent outputs.
6. **Offer .docx export**: After presenting, offer to generate a formatted Word document.

## Step 1: Validate and Detect Input

The user may provide case materials in several forms. Handle each:

### File paths (PDF, DOCX, TXT, MD)
1. Confirm the file(s) exist and note their extensions.
2. For **PDF files**: attempt to read with `python3 -c "import fitz; doc=fitz.open('FILE'); [print(page.get_text()) for page in doc]"`. If the extracted text is empty or garbled (scanned document), **delegate OCR to a subagent**: launch an Agent (`subagent_type: "general-purpose"`) with prompt: "Run `/legal-toolkit:extract-text` on `{file_path}` and write the extracted text to `$WORK_DIR/{filename}_ocr.txt`." Continue processing other files while the OCR agent works. Collect the OCR output before assembling `case_materials.md`.
3. For **DOCX files**: extract text with `python3 -c "from docx import Document; doc=Document('FILE'); [print(p.text) for p in doc.paragraphs]"`.
4. For **TXT/MD files**: read directly.

### Directory of files
If the user points to a directory, find all supported files (`.pdf`, `.docx`, `.txt`, `.md`) inside it. Process each file as above. Tell the user which files were found before proceeding.

### Pasted text or dictated case details
If the user pastes case details directly or describes the case verbally, use that text as the case file. No file processing needed.

### Mixed input
The user may provide both files and verbal context. Combine everything into a unified case record before analysis.

## Step 2: Confirm Jurisdiction

Apply the jurisdiction's criminal procedure rules and DUI/DWI statutory framework as identified in the case file. If no jurisdiction is specified or apparent from the documents, ask before proceeding:

> "Which jurisdiction is this case in? I need this to apply the correct DUI/DWI statutes, per se thresholds, implied consent rules, and observation period requirements."

## Step 3: Identify Reference Materials

Check if NHTSA DWI Detection and Standardized Field Sobriety Testing manual or other reference materials are available in the project or provided by the user. If available, cross-reference all FST analysis against the manual. If not available, note which NHTSA sections are relevant and flag for attorney verification.

## Step 4: Build the Trial Prep Guide

Read every document and piece of input. Produce the following sections in order:

### 1. Case Snapshot

One-page summary. Include:
- Defendant name and DOB
- Charges and statutory citations
- Arrest date, time, and location
- Arresting agency and officer (name and badge number)
- Court and case number
- BAC result (if available) and per se threshold for the jurisdiction
- Two-sentence preliminary defense theory based on what you find in the file

This is the cover page of the trial notebook.

### 2. Chronology

Build a detailed timeline of every event, from the initial traffic observation through booking. Every entry must cite the source document and location -- arrest report page number, body cam timestamp, witness statement paragraph. When two sources describe the same event differently, include both versions side by side and flag the conflict.

Format as a table:

| Time | Event | Source | Conflicts/Notes |
|------|-------|--------|-----------------|

### 3. Witness Profiles

For every person mentioned across all documents -- officers, witnesses, the defendant, lab technicians, dispatchers -- create a profile:
- **Identity:** Name, role, relationship to the case
- **Account:** What they said or observed (summarize, then quote key language)
- **Credibility:** Inconsistencies with other sources, potential bias, perception issues (lighting, distance, angle, fatigue, intoxication of the witness)
- **Cross-examination angles:** Specific questions or lines of attack based on what you found

### 4. NHTSA Compliance Analysis

For each field sobriety test administered, compare what the officer did against what NHTSA protocol requires. Cite specific NHTSA manual sections.

Format as a table:

| Test | What Officer Documented | NHTSA Requirement (Section) | Deviation Identified | Defense Significance |
|------|------------------------|----------------------------|---------------------|---------------------|

Cover all three standardized tests if administered: HGN, Walk-and-Turn, One-Leg Stand. Also flag any non-standardized tests (finger-to-nose, Romberg, alphabet) and note that NHTSA has not validated them as reliable indicators of impairment.

If no FSTs were administered, note the absence as potentially significant and skip this section.

### 5. Evidence Inventory

List every piece of physical and documentary evidence in the file:
- **What it is** and where it came from
- **Prosecution value:** How the State will use it
- **Defense value:** How it helps the defense or can be challenged
- **Foundation issues:** Chain of custody gaps, authentication problems, missing calibration records, unsigned documents

### 6. Cross-Document Inconsistencies

Compare every source document against every other source document. Quote the exact language from each source -- do not paraphrase.

Format as a table:

| Issue | Source A (Quote) | Source B (Quote) | Defense Significance |
|-------|-----------------|-----------------|---------------------|

Look for: factual contradictions (times, descriptions, sequences), omissions (details in one document but absent from another), and characterization differences (e.g., "slurred speech" in the arrest report vs. coherent dialogue on body cam).

### 7. Chemical Test Analysis

Review all breath or blood test results:
- Result and whether it meets the statutory per se threshold
- Instrument make/model, serial number, and last calibration date
- Observation period compliance (15/20-minute continuous observation per applicable state rules)
- Operator certification status and expiration
- Any irregularities: mouth alcohol, GERD/reflux noted, recent dental work, test refusal and reimplementation
- Rising BAC / absorption defense: time between last drink (if known) and test administration, whether BAC was rising or falling at time of driving

If no chemical test was administered (refusal case), note the refusal and analyze implied consent implications for the jurisdiction.

### 8. Motion Opportunities

Based on every issue identified above, list potential motions:
- **Motion type:** Suppress, dismiss, exclude, limine, etc.
- **Legal basis:** Constitutional provision, statute, or rule
- **Key facts:** The specific evidence supporting the motion
- **Strength:** Strong / Moderate / Worth Filing -- with a one-sentence explanation
- Mark all case law references as [VERIFY] -- attorney must confirm on Westlaw or Lexis

### 9. Recommended Next Steps

Specific, actionable items the attorney should pursue:
- Discovery requests to file (be specific about what to request and why)
- Witnesses to interview or subpoena
- Expert witnesses to retain (what kind, and what question they would address)
- Evidence to request that is not yet in the file: dashcam, additional body cam angles, dispatch audio, calibration logs, maintenance records, officer training records
- Investigation tasks: scene visit, lighting/visibility check, measurement of distances described in reports

### 10. Trial Strategy Notes

Preliminary defense themes based on what the file reveals:
- Primary defense theory and the three strongest facts supporting it
- Secondary/alternative theory if available
- Prosecution's strongest evidence and how to neutralize or minimize it
- Jury considerations: what makes this case sympathetic, what makes it difficult, what voir dire themes matter

## Output Format

- Structured memo with clear headers matching the ten sections above
- Tables where specified; bullet points for analysis; narrative prose for strategy sections
- Cite source documents (page numbers, timestamps, paragraph references) for every factual claim
- Flag every case law reference with [VERIFY] -- attorney must confirm independently
- Flag missing information as [NEEDS INVESTIGATION] rather than guessing
- Target length: 15-25 pages depending on case complexity
- Format for printing -- use headers, tables, and bullet points suitable for a physical trial notebook


## Accuracy and QA (Required)

Read the full QA protocol at `$SKILL_DIR/../../QA_AND_ACCURACY.md` and follow it.

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, launch a QA agent (`subagent_type: "general-purpose"`) following the protocol in the file above. The QA agent reads all outputs and source materials, checks for hallucination and accuracy, and writes `qa_review.md`. Apply any fixes before presenting to the user.

## Quality Standards

- Never present a case citation as verified. All case law references must be marked [VERIFY].
- If information is not in the case file, say so explicitly. Do not fill gaps with assumptions.
- When sources contradict each other, present both versions and explain the defense significance of the contradiction.
- Be a defense attorney, not a neutral summarizer. Analyze everything through the lens of what helps the defense.
- Do not speculate about evidence not in the record. Recommend investigation for gaps.
- Quote exact language when comparing documents -- the attorney needs to see the original words from each source.

## Edge Cases

- If no field sobriety tests were administered, skip the NHTSA Compliance Analysis section and note the absence as potentially significant.
- If the case file is very thin (only an arrest report), produce what you can and flag extensively what is missing and what discovery to request.
- If multiple defendants are involved, build a separate strategy section for each or note where interests diverge.
- If the charge is a lesser included offense situation, address both the primary charge and the lesser included in the defense theory.
- If input files are scanned PDFs with no extractable text, delegate OCR to a subagent as described in Step 1.
- If no chemical test was administered (refusal case), adapt Section 7 to analyze implied consent and refusal consequences.
- If body cam footage is referenced but not available as a file, note what the reports say about it and flag it as [NEEDS INVESTIGATION].

## Related Skills

- `/legal-toolkit:extract-text` -- for scanned documents that need text extraction before analysis
- `/legal-toolkit:doc-summary` -- for initial document summarization of very large case files
- `/legal-toolkit:case-timeline` -- to build a detailed timeline from case documents
- `/legal-toolkit:case-playbook` -- for broader defense strategy playbook (non-DUI-specific)
- `/legal-toolkit:motion` -- to draft specific motions identified in this guide
- `/legal-toolkit:discovery-review` -- for deep discovery package analysis
- `/legal-toolkit:doc-diff` -- for detailed side-by-side document comparison

## Connector Action: ~~knowledge base

If a `~~knowledge base` connector (e.g. Notion) is available, offer to save the guide:
> "Want me to save this trial prep guide to Notion for future reference?"
If yes, create a new page in the user's legal matters database with the full guide content, tagged with DUI/DWI and the jurisdiction.
