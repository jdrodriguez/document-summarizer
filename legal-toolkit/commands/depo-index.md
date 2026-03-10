---
description: Index deposition video/audio with transcription, speaker identification, topic indexing, and key moment detection
argument-hint: "<deposition recording file>"
---

# /depo-index -- Deposition Video Indexer

Transcribe deposition recordings with timestamps, speaker identification, topic indexing, and key moment detection. Flags admissions, objections, evasive language, and potential contradictions. All processing is 100% local.

@$1

## Workflow

- **Validate** the input file and check supported formats (.mp4, .mov, .avi, .mkv, .wav, .mp3, .m4a, etc.)
- **Transcribe and index** using the `index-deposition` skill's Python script with Whisper AI and optional speaker diarization
- **Present** deposition summary: duration, speakers identified, word count, transcript pages, key moments, and topics
- **Highlight** key moments: admissions, objections, evasive language ("I don't recall"), and potential contradictions with timecodes
- **Generate** output files: transcript.txt, page_line_transcript.txt, topic_index.json, key_moments.json, testimony_timeline.html
- Refer to the `index-deposition` skill (SKILL.md) for model selection, processing time expectations, and formal deposition summary options
