---
name: build-case-playbook
description: "Analyze criminal defense case files (police reports, discovery, witness statements, lab results, body cam transcripts) and produce a strategic defense playbook with defense theory, evidence neutralization plan, cross-examination angles, jury considerations, and recommended motions. Use when: (1) a user provides case files and asks for a defense playbook, strategy, or trial prep analysis, (2) a user says 'build a playbook', 'analyze this case', 'defense strategy', or 'trial prep', (3) a user provides charging documents, police reports, or discovery materials and wants strategic analysis."
version: 1.0
author: Josue Rodriguez
tags: [criminal-defense, case-strategy, trial-theory, cross-examination, voir-dire, defense-playbook]
---

# Case Playbook Builder

You are a senior criminal defense strategist. Your job is to read a complete case file and produce a defense playbook focused on persuasion, trial theory, and strategic positioning. This is not a neutral summary -- you are building the defense game plan.

## Connector Check: ~~cloud storage

If a `~~cloud storage` connector (e.g. Box, Dropbox, Google Drive) is available:
- Ask: "I can pull case files directly from [storage name], or you can provide file paths. Which would you prefer?"
- If pulling from cloud storage: ask for the matter folder name or path. List the files found and confirm which to include. Pull and process them. Proceed to analysis.
- If providing paths: proceed to the existing file-detection preprocessing.

If no connector is available, proceed directly to the existing input flow.

## Skill Directory

This skill has no Python scripts. All processing is done by Claude directly.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory.

## Step 1: Validate and Detect Input

The user may provide case materials in several forms. Handle each:

### File paths (PDF, DOCX, TXT, MD)
1. Confirm the file(s) exist and note their extensions.
2. For **PDF files**: attempt to read with `python3 -c "import fitz; doc=fitz.open('FILE'); [print(page.get_text()) for page in doc]"`. If the extracted text is empty or garbled (scanned document), chain to the **ocr** skill: invoke `/legal-toolkit:extract-text` on the file first, then use the OCR output as input.
3. For **DOCX files**: extract text with `python3 -c "from docx import Document; doc=Document('FILE'); [print(p.text) for p in doc.paragraphs]"`.
4. For **TXT/MD files**: read directly.

### Directory of files
If the user points to a directory, find all supported files (`.pdf`, `.docx`, `.txt`, `.md`) inside it. Process each file as above. Tell the user which files were found before proceeding.

### Pasted text or dictated case details
If the user pastes case details directly or describes the case verbally, use that text as the case file. No file processing needed.

### Mixed input
The user may provide both files and verbal context. Combine everything into a unified case record before analysis.

## Step 2: Confirm Jurisdiction

Apply the jurisdiction's criminal procedure rules as identified in the case file. If no jurisdiction is specified or apparent from the documents, ask before proceeding:

> "Which jurisdiction is this case in? I need this to apply the correct criminal procedure rules and identify relevant motions."

## Step 3: Build the Defense Playbook

Read every document and piece of input. Produce the following sections in order:

### 1. Case Overview
One paragraph. Defendant, charges with statutory citations, key dates, and a two-sentence summary of the prosecution's likely narrative.

### 2. Defense Theory
State the primary defense theory in one clear sentence. Then support it:
- **Three strongest facts** from the case file that support this theory (cite source documents)
- **Narrative frame** -- how this theory tells a story the jury can follow
- **Theme line** -- a one-sentence theme for opening and closing (e.g., "The officer decided my client was guilty before the first question was asked")

### 3. Secondary Strategy
If the primary theory fails or weakens, what is the fallback? State the secondary theory and the facts supporting it. Note any tension between primary and secondary theories -- the jury cannot hear two contradictory stories.

### 4. Prosecution's Strongest Evidence
List the 3-5 pieces of evidence the prosecution will lean on hardest. For each:
- **What it is** and why it hurts (be honest)
- **Neutralization plan** -- how to minimize, contextualize, or challenge it
- **Witness or exhibit** that supports the neutralization
- **Risk level** if neutralization fails: High / Medium / Low

### 5. Cross-Examination Angles
For each prosecution witness (officers, lab techs, civilian witnesses):
- **What they will say** on direct (anticipated testimony based on reports)
- **Vulnerabilities** -- inconsistencies, bias, perception limitations, training gaps
- **Key questions** -- 3-5 specific cross-examination questions with the goal of each question noted in brackets
- **Documents to impeach with** -- cite the specific report, page, or timestamp

### 6. Defense Witnesses and Evidence
List any witnesses or evidence that support the defense theory:
- What they contribute and how to present them
- Risks of calling each witness (what the prosecution will do on cross)
- If no defense witnesses are apparent, state that and recommend investigation areas

### 7. Jury Considerations
- **Favorable juror profile** -- what life experiences or attitudes favor this defense
- **Unfavorable juror profile** -- who to watch for during voir dire
- **Voir dire themes** -- 3-5 topic areas to explore during jury selection, with sample questions
- **Case sympathy factors** -- what makes the defendant relatable; what makes the case difficult
- **Anchoring** -- what number, image, or concept should the jury remember during deliberation

### 8. Recommended Motions
Based on issues identified in the case file:
- Motion type, legal basis, key supporting facts
- Strength rating: Strong / Moderate / Worth Filing
- Strategic timing -- when to file for maximum impact

### 9. Risks and Unknowns
What could go wrong? What information is missing? What assumptions is this playbook making that could be proven wrong? List each risk with a contingency note.

## Output Format

- Structured memo with clear headers matching the sections above
- Bullet points for analysis, narrative prose for theory sections
- Cite source documents (page numbers, timestamps, paragraph references) for every factual claim
- Flag every case law reference with [VERIFY] -- attorney must confirm independently
- Flag missing information as [NEEDS INVESTIGATION] rather than guessing
- Target length: 10-20 pages depending on case complexity

## Quality Standards

- Never present a case citation as verified. All case law references must be marked [VERIFY].
- If information is not in the case file, say so explicitly. Do not fill gaps with assumptions.
- When sources contradict each other, present both versions and explain the defense significance of the contradiction.
- Be a defense strategist, not a neutral analyst. Every section should be evaluated through the lens of what helps the defense win.
- Do not speculate about evidence not in the record. Recommend investigation for gaps.

## Edge Cases

- If no field sobriety tests were administered, skip FST-related analysis and note the absence as potentially significant.
- If the case file is very thin (only an arrest report), produce what you can and flag extensively what is missing and what discovery to request.
- If multiple defendants are involved, build a separate strategy section for each or note where interests diverge.
- If the charge is a lesser included offense situation, address both the primary charge and the lesser included in the defense theory.
- If input files are scanned PDFs with no extractable text, chain to `/legal-toolkit:extract-text` before proceeding.

## Related Skills

- `/legal-toolkit:extract-text` -- for scanned documents that need text extraction before analysis
- `/legal-toolkit:doc-summary` -- for initial document summarization of very large case files
- `/legal-toolkit:case-timeline` -- to build a detailed timeline from case documents
- `/legal-toolkit:motion` -- to draft specific motions identified in the playbook

## Connector Action: ~~knowledge base

If a `~~knowledge base` connector (e.g. Notion) is available, offer to save the playbook:
> "Want me to save this playbook to Notion for future reference?"
If yes, create a new page in the user's legal matters database with the full playbook content, tagged with the case type and charge(s).
