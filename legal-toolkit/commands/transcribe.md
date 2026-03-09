---
description: Transcribe audio/video recordings into professional Word documents with timestamps and speaker labels
argument-hint: "<audio or video file path>"
---

# /transcribe -- Legal Transcriber

Transcribe recordings using the local Whisper AI model via the legal-transcriber MCP server. All processing is 100% local -- no audio data leaves the machine. Produces a .docx with timestamps, speaker labels, and analysis.

@$1

## Workflow

- **Validate** the input file and check supported formats (.wav, .mp3, .m4a, .mp4, .mov, etc.)
- **Check dependencies** via the `check_dependencies` MCP tool and prepare the Whisper model
- **Transcribe** using the `transcribe_audio` MCP tool with async polling for progress updates
- **Analyze** the transcript -- directly for small transcripts, or via parallel agents for large ones (500+ lines)
- **Generate** a professional .docx via the `create_document` MCP tool with executive summary, key topics, action items, speaker statistics, full transcript, and notable quotes
- Refer to the `transcribe` skill (SKILL.md) for MCP tool parameters, polling workflow, and agent coordination details
