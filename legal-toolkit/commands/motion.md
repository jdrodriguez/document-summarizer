---
description: Draft filing-ready criminal defense motions from case documents and templates
argument-hint: "<case documents, motion type, or file paths>"
---

# /motion -- Motion Drafter

Draft complete criminal defense motions (suppress, dismiss, exclude, limine, compel, sentencing memo) from case documents and optional firm templates. Extracts facts from PDFs, DOCX, or text, fills templates with case-specific details, and produces filing-ready drafts with IRAC/CRAC arguments, evidence citations, and prayer for relief. All case law is flagged [VERIFY] for attorney confirmation.

@$1

## Workflow

- **Gather inputs** -- identify case documents, motion type, optional template, jurisdiction, and drafting preferences
- **Extract text** from provided files (PDF, DOCX, TXT). If a scanned PDF is detected, chain to `/legal-toolkit:extract-text` for text extraction first
- **Draft the motion** with filled caption, statement of facts drawn exclusively from case documents, legal standard, structured arguments (IRAC/CRAC), evidence references with page citations, and prayer for relief
- **Flag all citations** with [VERIFY] and all missing information with [FILL -- not found in case file] or [NEEDS INVESTIGATION]
- **Present for review** with a gaps checklist, verification list, and suggestions for strengthening arguments
- Refer to the `draft-motion` skill (SKILL.md) for templates, formatting standards, and edge case handling
