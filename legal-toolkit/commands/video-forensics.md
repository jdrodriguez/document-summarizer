---
description: Analyze video frame-by-frame for forensic review with scene detection and multi-pass extraction
argument-hint: "<video file path>"
---

# /video-forensics -- Forensic Video Analyzer

Analyze video files frame-by-frame for forensic review. Extracts frames using scene-aware multi-pass extraction (coarse + dense around scene changes), then analyzes each frame visually to produce a detailed forensic report with timeline, key moments, individual tracking, and evidence notes.

@$1

## Workflow

- **Validate** the input video file and check that ffmpeg is available
- **Extract frames** using the `analyze-video` skill's Python script with scene-aware multi-pass extraction (coarse pass + dense pass around detected scene changes)
- **Analyze** each frame chapter-by-chapter, describing visible elements, actions, environment, text, and changes between frames
- **Flag key moments**: use of force, weapons, new individuals, evidence handling, scene transitions, camera perspective shifts
- **Generate** a forensic report with: video summary, timeline of events, key moments, individuals observed, evidence notes, scene changes, and gaps/concerns
- **Save** the full report as `forensic_report.md` in the output directory alongside the extracted frames
- Refer to the `analyze-video` skill (SKILL.md) for detailed extraction parameters, analysis instructions, and report format
