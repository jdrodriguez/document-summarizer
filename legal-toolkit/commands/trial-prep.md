---
description: Generate a comprehensive DUI trial preparation guide with NHTSA analysis, chronology, witness profiles, and motion opportunities
argument-hint: "<case files, arrest reports, or file paths>"
---

# /trial-prep -- DUI Trial Prep Guide

Generate a complete DUI/DWI trial preparation notebook from case files. Reads arrest reports, body cam transcripts, witness statements, lab results, and calibration records, then cross-references against the NHTSA manual to produce a structured, print-ready trial notebook.

@$1

## Workflow

- **Detect input type**: file paths (PDF/DOCX/TXT/MD), directories, or pasted case details
- **Extract text** from provided files; chain to OCR if scanned PDFs are detected
- **Confirm jurisdiction** to apply correct DUI/DWI statutes and per se thresholds
- **Build the trial prep guide**: case snapshot, chronology, witness profiles, NHTSA compliance analysis, evidence inventory, cross-document inconsistencies, chemical test analysis, motion opportunities, next steps, and trial strategy
- **Cite everything** to source documents; flag case law as [VERIFY] and gaps as [NEEDS INVESTIGATION]
- Refer to the `trial-prep-guide` skill (SKILL.md) for the full trial notebook structure and output format
