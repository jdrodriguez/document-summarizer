---
description: Generate adaptive intake call scripts with branching logic, objection handling, and demeanor adaptations for criminal defense firms
argument-hint: "<practice areas, past call transcripts, or audio files>"
---

# /intake-script -- Adaptive Intake Script Builder

Build intake call scripts that adapt based on charge type, case facts, caller demeanor, and common objections. Supports learning from past call recordings (chains to transcribe), existing transcripts (PDF/DOCX/TXT), or direct practice area input.

@$1

## Workflow

- **Detect input type** and preprocess: audio/video files chain to `/legal-toolkit:transcription`, PDF/DOCX files get text extracted, plain text is used directly, or proceed from a description alone
- **Analyze source material** (if provided) to extract call patterns, effective language, objection handling, and demeanor adaptation cues from past calls
- **Gather parameters**: charge type(s), key branching facts, demeanor scenarios, and optional firm-specific details
- **Generate** a complete adaptive script with opening hooks, qualification question branches, urgency framing, fee transition language, demeanor adaptations, objection responses, and edge case handling
- **Refine** interactively based on user feedback
- Refer to the `build-intake-script` skill (SKILL.md) for branching logic, charge-specific question trees, and script templates
