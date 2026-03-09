---
description: Build a master case chronology from legal documents with interactive timeline and gap analysis
argument-hint: "<file or folder of case documents>"
---

# /build-chronology -- Case Chronology Builder

Extract all dated events from legal documents, build an interactive timeline, detect gaps and date conflicts, and produce a comprehensive chronology spreadsheet.

@$1

## Workflow

- **Validate** the input path (file or directory) and check for supported formats (.pdf, .docx, .txt, .md)
- **Extract** dated events using the `build-chronology` skill's Python script with NLP-based date recognition
- **Present** chronology summary: total events, date range, events by type, gaps detected, and date conflicts found
- **Highlight** date conflicts between documents and significant gaps in the timeline for review
- **Generate** output files: chronology.xlsx, timeline.html (interactive), gap_analysis.json, date_conflicts.json
- Refer to the `build-chronology` skill (SKILL.md) for multi-agent processing of large document sets (10+) and formal narrative report options
