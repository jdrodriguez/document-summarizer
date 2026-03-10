---
description: Score an intake call transcript against a coaching rubric with evidence-backed ratings
argument-hint: "<transcript text, audio file, or PDF path>"
---

# /intake-scorecard -- Intake Call Scorer

Score intake call transcripts against a structured rubric for criminal defense firms. Accepts audio/video recordings, PDFs (including scanned), or plain text. Produces weighted scores (1-5) per category with evidence citations, actionable coaching notes, and sign probability.

@$1

## Workflow

- **Detect input type** and preprocess: audio/video files are transcribed first via the `transcribe` skill, scanned PDFs are OCR'd first via the `ocr` skill, readable PDFs and text proceed directly
- **Identify rubric** -- use the firm's custom rubric if provided, otherwise apply the default 7-category rubric (Opening & Rapport, Qualification, Urgency & Education, Objection Handling, Fee Presentation, Close Attempt, Compliance)
- **Score each category** 1-5 with mandatory evidence quotes from the transcript and actionable coaching notes containing specific alternative phrases
- **Calculate overall weighted score** as X.X / 5.0 with a summary
- **Highlight top strength** (best moment, quoted) and **top coaching opportunity** (worst moment with exact alternative phrasing)
- **List all objections** raised by the caller with rep's response, assessment, and suggested alternatives
- **Assess sign probability** (High / Medium / Low) with reasoning
- Refer to the `score-intake` skill (SKILL.md) for full rubric, scoring anchors, and edge case handling
