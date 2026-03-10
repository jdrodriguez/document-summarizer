---
description: Transcribe audio/video recordings into professional Word documents with timestamps and speaker labels
argument-hint: "<audio or video file path>"
---

# /transcription -- Legal Transcriber

Transcribe recordings using the local Whisper AI model. All processing is 100% local -- no audio data leaves the machine. Produces a .docx with timestamps, speaker labels, and analysis.

@$1

## Workflow

- **Validate** the input file and check supported formats (.wav, .mp3, .m4a, .mp4, .mov, etc.)
- **Check dependencies** via check_dependencies.py script and verify Whisper model availability
- **Transcribe** by launching transcribe_audio.py in background and polling status.json for progress
- **Analyze** the transcript -- directly for small transcripts, or via parallel agents for large ones (500+ lines)
- **Generate** a professional .docx via create_document.py script with executive summary, key topics, action items, speaker statistics, full transcript, and notable quotes
- Refer to the `transcribe` skill (SKILL.md) for script parameters, polling workflow, and agent coordination details
