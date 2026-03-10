---
description: Generate tracked-changes redline documents from two contract versions with risk analysis
argument-hint: "<original.docx> <revised.docx>"
---

# /track-changes -- Contract Redline Generator

Generate Word documents with native tracked-changes markup from two contract versions, with risk-rated change analysis categorizing each change as HIGH, MEDIUM, or LOW risk.

@$1

## Workflow

- **Validate** two .docx file paths (original and revised contracts)
- **Generate** the redline using the `redline` skill's Python script, producing a Word document with native tracked-changes markup
- **Present** material changes: total changes, breakdown by risk level (HIGH/MEDIUM/LOW), and detailed HIGH-risk change analysis
- **Output** redline.docx with insertions (red underline) and deletions (red strikethrough) compatible with Word's Review tab
- Refer to the `redline` skill (SKILL.md) for risk categorization criteria and options for deep analysis of high-risk changes
