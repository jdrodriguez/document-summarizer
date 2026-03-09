---
description: Process client intake data into structured profiles, conflict checks, document checklists, and SOL warnings
argument-hint: "<intake notes file>"
---

# /process-intake -- Legal Intake Processor

Process raw client intake data into structured legal intake outputs. Handles free-form notes, JSON form data, DOCX documents, and CSV files. Extracts client information, classifies matter type, prepares conflict check lists, and calculates statute of limitations deadlines.

@$1

## Workflow

- **Validate** the input file and check for supported formats (.txt, .md, .json, .docx, .csv)
- **Configure** processing: matter type (auto-detect or specify) and jurisdiction for SOL calculations
- **Process** intake using the `process-intake` skill's Python script with NLP-based entity and date extraction
- **Present** structured output: client profile, conflict check entities, matter-specific document checklist, and statute of limitations warnings with days remaining
- **Generate** output files: client_profile.json, conflict_check.xlsx, document_checklist.json, sol_warning.txt
- Refer to the `process-intake` skill (SKILL.md) for supported matter types, jurisdiction handling, and formal intake report generation
