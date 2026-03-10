---
description: Build a strategic criminal defense playbook from case files with defense theory, cross-examination angles, and jury strategy
argument-hint: "<case details, charging documents, or file paths>"
---

# /case-playbook -- Case Playbook Builder

Analyze criminal defense case files and produce a strategic defense playbook. Accepts police reports, discovery materials, witness statements, lab results, body cam transcripts, or direct case descriptions. Files can be PDF, DOCX, TXT, or MD -- scanned documents are automatically routed through OCR.

@$1

## Workflow

- **Detect input type**: file paths (PDF/DOCX/TXT/MD), directories, or pasted case details
- **Extract text** from provided files; chain to OCR if scanned PDFs are detected
- **Confirm jurisdiction** if not apparent from the case materials
- **Build the playbook**: defense theory, prosecution evidence neutralization, cross-examination angles, jury considerations, recommended motions, and risk assessment
- **Cite everything** to source documents; flag case law as [VERIFY] and gaps as [NEEDS INVESTIGATION]
- Refer to the `build-case-playbook` skill (SKILL.md) for strategy frameworks and playbook structure
