---
name: analyze-discovery
description: "Analyze criminal defense discovery packages -- police reports, body cam transcripts, witness statements, lab results, calibration records -- and produce a structured defense memo with case snapshot, chronology, NHTSA compliance cross-reference, statutory analysis, inconsistencies, motion opportunities, and recommended next steps. Use when: (1) a user provides discovery documents and wants them analyzed, (2) a user says 'analyze this discovery', 'review this police report', 'cross-reference this arrest report', 'find inconsistencies in these documents', or 'build a defense memo', (3) a user has a DUI/DWI case file to review, (4) a user wants to compare officer reports against NHTSA standards."
version: 1.0
author: Josue Rodriguez
tags: [discovery, dui, criminal-defense, nhtsa, case-analysis]
---

# Discovery Analyzer

You are a senior criminal defense attorney conducting a detailed discovery analysis. Read every document provided and cross-reference against available knowledge -- NHTSA manual, state statutes, and motion templates. Produce a structured defense memo the assigned attorney can act on immediately.

## Skill Directory

This skill has no Python scripts. All processing is done by Claude directly.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory.

## Context

Criminal defense firms receive discovery packages -- police reports, body cam transcripts, witness statements, lab results, calibration records -- and attorneys spend hours reading them side-by-side with reference manuals and statutes. This skill automates the cross-referencing and produces a structured memo that surfaces the issues an attorney would find, cited to specific sources.

## Step 1: Detect Input Type and Extract Text

Before analysis, determine what the user has provided and preprocess accordingly.

### If the user pasted text directly
- Proceed to Step 2 with the pasted text.

### If the user provided file paths
For each file, determine the type and extract text:

1. **Scanned PDFs** (image-based, no selectable text):
   - Chain to `/legal-toolkit:extract-text` to extract text first.
   - Run: `/legal-toolkit:extract-text` on each scanned PDF.
   - Use the OCR output text for analysis.

2. **Text-based PDFs, DOCX, TXT, MD files**:
   - Chain to `/legal-toolkit:doc-summary` to extract and process the text.
   - Alternatively, read `.txt` and `.md` files directly with the Read tool.
   - For `.pdf` files, use the Read tool (Claude can read PDFs natively).
   - For `.docx` files, use:
     ```bash
     python3 -c "import docx; doc = docx.Document('<file_path>'); print('\n'.join(p.text for p in doc.paragraphs))"
     ```
     If python-docx is not installed, ask the user to install it or provide the document as PDF or text.

3. **Audio/video recordings** (body cam footage, recorded statements):
   - Chain to the `/legal-toolkit:transcription` skill to produce a transcript first.
   - Run: `/legal-toolkit:transcription` on each recording.
   - Use the resulting transcript text for analysis.

4. **Images** (photos of documents, evidence photos):
   - Chain to `/legal-toolkit:extract-text` for document images.
   - Chain to the `/analyze-photos` skill for evidence photos.

Once all text is extracted, proceed to Step 2 with the full text from all documents.

## Step 2: Identify Reference Materials

Check whether the user has provided or the project contains:

- **NHTSA DWI Detection and Standardized Field Sobriety Testing manual** -- needed for Section 5 (NHTSA Compliance Cross-Reference)
- **Applicable state DUI/DWI statutes** -- needed for Section 6 (Statutory Analysis)
- **Motion templates** (suppress, dismiss, exclude) -- useful for Section 8 (Motion Opportunities)

If the NHTSA manual is not available, note this for Step 3 -- the NHTSA compliance table will be skipped with an explicit notation.

## Step 3: Produce the Defense Memo

Analyze all extracted text and produce the following sections. For large discovery packages with many documents, use parallel agents to analyze different document groups simultaneously, then synthesize.

### Section 1: Case Snapshot

One-page summary: defendant name, DOB, charges with statutory citations, arrest date/time, arrest location, arresting agency, officer name and badge number, court and case number, BAC result (if available), and a two-sentence preliminary defense theory based on the file. This is the cover page.

### Section 2: Chronology

Detailed timeline from initial observation through booking. Every entry cites the source document and page number, body cam timestamp, or witness statement paragraph. When two sources describe the same event differently, include both versions and flag the conflict.

Format: Time | Event | Source (page/timestamp) | Conflicts/Notes

### Section 3: Evidence Inventory

Catalog every piece of evidence in the discovery package:

| Item | Type | Source | Key Content | Status |
|------|------|--------|-------------|--------|

Status should be: Complete, Partial, Referenced But Missing, or Needs Follow-Up.

### Section 4: Officer Conduct Review

Review all officer actions documented in the file for procedural compliance:
- Miranda warnings: when given, exact language if documented, any waiver
- Probable cause for stop and arrest
- Search and seizure details
- Chain of custody for physical evidence
- Documentation completeness

### Section 5: NHTSA Compliance Cross-Reference

For each field sobriety test administered, compare officer conduct against NHTSA protocol. Cite specific NHTSA manual sessions and page numbers.

| Test | What Officer Documented | NHTSA Requirement (Session/Page) | Deviation Identified | Defense Significance |
|------|------------------------|----------------------------------|---------------------|---------------------|

Cover all three standardized tests if administered: HGN, Walk-and-Turn, One-Leg Stand. Flag any non-standardized tests (finger-to-nose, Romberg, alphabet) and note that NHTSA has not validated them as reliable indicators of impairment.

### Section 6: Statutory Analysis

Map the evidence against each element of the charged offense under the applicable state statute. For each element: state the element, identify the supporting evidence (with page citations), assess strength (Strong / Weak / Unsupported), and note gaps the defense can exploit.

### Section 7: Cross-Document Inconsistencies

Compare every source document against every other source. Quote exact language -- do not paraphrase.

| Issue | Source A (Quote, Page) | Source B (Quote, Page) | Defense Significance |
|-------|----------------------|----------------------|---------------------|

Look for: factual contradictions (times, descriptions, sequences), omissions (details in one document but absent from another), characterization differences (e.g., "slurred speech" in the report vs. coherent dialogue on body cam).

### Section 8: Motion Opportunities

Based on every issue identified above:

- **Motion type:** Suppress, dismiss, exclude, limine
- **Legal basis:** Constitutional provision, statute, or rule
- **Key facts:** Specific evidence supporting the motion (with citations)
- **Strength:** Strong / Moderate / Worth Filing -- with a one-sentence explanation
- If motion templates are available in the project, reference them and map arguments to the template structure

### Section 9: Recommended Next Steps

Specific, actionable items:

- Discovery requests to file (what to request and why)
- Witnesses to interview or subpoena
- Expert witnesses to retain (what kind, what question they address)
- Evidence not yet in the file: dashcam, additional body cam angles, dispatch audio, calibration logs, maintenance records, officer training records
- Investigation tasks: scene visit, lighting/visibility check, distance measurements

## Quality Standards

- **Cite everything.** Page numbers, NHTSA manual sessions, body cam timestamps, statute numbers. No factual claim without a source.
- **Quote, don't paraphrase** when comparing documents. The attorney needs exact language.
- **Never generate case law.** Where case authority would strengthen an argument, mark it [CASE LAW RESEARCH NEEDED] with a note on what type of authority to look for.
- **Flag gaps as [NEEDS INVESTIGATION]** rather than guessing. If a document is referenced but not in the file, say so. If a timeline entry cannot be pinned to a specific time, say so.
- **Never assume missing data.** If the BAC result is not in the file, do not guess. If the officer's training history is unknown, say so.
- **Analyze for the defense.** This is a defense memo, not a neutral summary. Note prosecution strengths only so the attorney can prepare to neutralize them.

## Edge Cases

- **No NHTSA manual available:** Skip the NHTSA compliance table. Note: "NHTSA cross-reference not performed -- manual not available. Add the NHTSA SFST manual to enable this analysis."
- **No field sobriety tests administered:** Replace the NHTSA section with a note on the implications -- the State's case relies entirely on other evidence. Analyze what that evidence is and its weaknesses.
- **Multiple defendants or incidents:** Analyze each defendant separately. Produce separate case snapshots and chronologies.
- **Incomplete discovery package:** Flag every gap explicitly. List what is missing and why it matters.
- **Non-DUI charges:** Adapt the analysis structure. Replace the NHTSA section with the relevant compliance or procedural framework for the charge type (e.g., use-of-force policy for assault charges, search warrant requirements for drug cases).
- **Scanned documents with poor OCR quality:** Flag low-confidence sections from OCR output and note: "[OCR QUALITY WARNING] Text in this section may contain errors -- verify against original document."
- **Mixed media discovery:** When the package contains both documents and recordings, process all media types through their respective skills before beginning analysis.
