---
description: Analyze criminal defense discovery packages and produce a structured defense memo
argument-hint: "<discovery documents, text, or file paths>"
---

# /discovery-review -- Discovery Analyzer

Analyze police reports, body cam transcripts, witness statements, lab results, and other discovery documents. Cross-references against NHTSA standards and state statutes. Produces a structured defense memo with case snapshot, chronology, NHTSA compliance review, statutory analysis, inconsistencies, motion opportunities, and next steps.

@$1

## Workflow

- **Detect input type** -- if scanned PDFs, chain to OCR skill first; if audio/video, chain to transcribe skill first; if document files, extract text; if pasted text, proceed directly
- **Identify reference materials** -- check for NHTSA manual, state statutes, and motion templates in the project
- **Analyze** all documents and cross-reference against available standards and statutes
- **Produce** a structured defense memo with 9 sections: case snapshot, chronology, evidence inventory, officer conduct review, NHTSA compliance cross-reference, statutory analysis, cross-document inconsistencies, motion opportunities, and recommended next steps
- Refer to the `analyze-discovery` skill (SKILL.md) for full details on each section, quality standards, and edge cases
