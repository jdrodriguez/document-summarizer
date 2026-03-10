---
description: Build objection response playbooks for criminal defense intake teams from call transcripts, notes, or recordings
argument-hint: "<call transcripts, objection notes, or audio files>"
---

# /objection-playbook -- Objection Playbook Builder

Build response playbooks that help intake reps handle prospect objections with empathy, urgency, and confidence. Accepts audio recordings, transcripts, PDFs, or direct text — and produces categorized objection responses with scripts, alternative framings, and escalation guidance.

@$1

## Workflow

- **Detect input type** and preprocess: audio/video files chain to `/legal-toolkit:transcription` first, PDFs/DOCX get text extracted, plain text proceeds directly
- **Extract objections** from the source material — identify price resistance, public defender preference, stalling, competitor comparisons, denial, distrust, and timing concerns
- **Categorize** each objection by type and assess the underlying concern and urgency level
- **Generate response scripts** for each objection: primary script, alternative framings for emotional/analytical/hostile callers, phrases to avoid, and escalation guidance
- **Compile** into a structured playbook with summary table, full entries, and a quick-reference cheat sheet
- Refer to the `build-objection-playbook` skill (SKILL.md) for objection categories, response frameworks, and quality standards
