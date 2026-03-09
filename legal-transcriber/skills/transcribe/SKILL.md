---
name: transcribe
description: "Transcribe audio or video recordings into professional Word documents with timestamps and speaker labels. Use when a user provides a recording file (.mp3, .wav, .m4a, .mp4, etc.) and wants it transcribed."
---

# Legal Transcriber

Transcribe recordings using the `legal-transcriber` MCP server. All processing is 100% local — no audio data leaves the machine. Follow these steps in order.

## Step 1: Validate

Confirm the user gave a path to an audio/video file. Supported: `.wav`, `.mp3`, `.m4a`, `.flac`, `.ogg`, `.wma`, `.aac`, `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`.

## Step 2: Check Dependencies

Call the `check_dependencies` MCP tool.

- If `status` is `"ok"` — **proceed to Step 3**. Note whether `pyannote.available` is true (speaker diarization will work) or false (transcription will work but without speaker labels).
- If `status` is `"missing_dependencies"` — tell the user: "The Legal Transcriber is not set up. Please double-click 'Install Legal Transcriber.command' to install, then restart Claude Desktop."
- If the MCP tool call **fails or errors** — tell the user: "The legal-transcriber MCP server is not running. Please re-run the installer and restart Claude Desktop."

## Step 3: Prepare Model

The model is selected automatically based on recording duration:
- **< 30 minutes**: `small` (~466 MB) — good balance of speed and accuracy
- **30+ minutes**: `medium` (~1.5 GB) — better accuracy for longer recordings

If the user explicitly requests a specific model, use that instead.

Call the `prepare_model` MCP tool with the expected model (default `"medium"` if unknown, or `"small"` if the user mentions a short recording).
- If `status: "ready"` — model is cached, proceed.
- If `status: "not_cached"` — tell the user the model will download during transcription (first run only).

**If either MCP tool fails or is unavailable**, tell the user: "The legal-transcriber MCP server is not running. Please re-run the installer and restart Claude Desktop."

## Step 3.5: Resolve File Path

**Important:** The MCP server runs on the host Mac, not inside Cowork's VM. File paths may differ.

Call the `resolve_path` MCP tool with the user's file path.
- If `status: "found"` — use the `resolved_path` as the `input_file` for all subsequent steps.
- If `status: "not_found"` — ask the user for the full macOS path (e.g. `/Users/name/Downloads/file.mp4`).

## Step 4: Transcribe (Async with Polling)

Set `work_dir` to `{parent_dir}/{filename_without_ext}_transcript_work` (using the **resolved** parent dir from Step 3.5).

1. **Before starting**, tell the user:

   > **Heads up before we begin:** Audio transcription is a computationally intensive process — the Whisper AI model will use a significant amount of your computer's CPU and memory while it runs. A few things to keep in mind:
   > - **Processing time** depends on the length of the recording. A 10-minute file may take 3-5 minutes; a 1-hour file could take 15-30 minutes or more.
   > - **Avoid running other heavy tasks** (video editing, large downloads, other AI tools) while the transcription is in progress — it will slow things down and may cause issues.
   > - Your computer's fans may spin up — that's completely normal.
   > - I'll give you regular progress updates so you always know where things stand.

2. Call `transcribe_audio` MCP tool with the **resolved** `input_file` path, `work_dir`, `model: "auto"`, `language: "auto"`. **Do NOT pass `no_diarize: true`** — diarization should be attempted by default since speaker identification is core to the deliverable. The worker will gracefully fall back if pyannote is unavailable. Only pass `no_diarize: true` if the user explicitly asks to skip speaker detection. Pass other user preferences if given (language, max_speakers). This returns immediately with a `job_id`.

3. Tell the user: "Transcription started! Monitoring progress..."

4. **Polling loop** — call `check_transcription_status` MCP tool with the `job_id` every **10 seconds**. **You MUST give the user a status update on every single poll** — never poll silently. Use friendly, varied messages so the user knows things are progressing:

   - If `status: "running"`:
     - **Always report** the `stage` and `progress` percentage with a brief message
     - Use the `stage` field to give context. Map stages to user-friendly descriptions:
       - `"extracting_audio"` → "Extracting audio from video file..."
       - `"loading_model"` → "Loading the Whisper AI model..."
       - `"transcribing"` → "Transcribing audio... {progress}% complete"
       - `"diarizing"` → "Identifying speakers..."
       - `"writing_outputs"` → "Almost done — writing transcript files..."
     - Include the `message` field if it has useful detail (e.g., segment counts)
     - For long transcriptions (>3 polls at the same stage), add reassurance: "Still working — this is normal for longer recordings."
     - Wait 10 seconds, then poll again.

   - If `status: "pending"` — tell the user: "Starting up the transcription engine..." Wait 10 seconds and poll again. If pending for >3 polls, say: "The engine is still initializing — this can take a moment on first run."

   - If `status: "completed"` — tell the user: "Transcription complete!" and proceed to Step 5.

   - If `status: "error"` — report the error message to the user and stop.

5. Once completed, read `work_dir/metadata.json`.

## Step 5: Analyze Transcript

Read `work_dir/metadata.json` for duration, language, speakers, etc. Then determine the transcript size:

Run a quick Bash command to count lines:
```bash
wc -l < "{work_dir}/transcript.txt"
```

### Small transcript (500 lines or fewer)

Read the entire `work_dir/transcript.txt` directly. Proceed to Step 6 with the full transcript in context.

### Large transcript (more than 500 lines)

The transcript is too large for a single context window. Use **parallel agents** to analyze it in sections.

1. **Calculate sections** — divide lines evenly into chunks of ~500 lines each:
   - `agent_count = min(5, ceil(total_lines / 500))`
   - Each agent gets a contiguous line range (e.g., Agent 1: lines 1–500, Agent 2: lines 501–1000, etc.)

2. **Create analysis directory:**
   ```bash
   mkdir -p "{work_dir}/analysis"
   ```

3. **Spawn agents in parallel** — launch all agents at once using the Task tool (`subagent_type: "general-purpose"`). Each agent's prompt:

   ```
   You are analyzing a section of a transcript file.

   Read lines {start_line} to {end_line} of: {work_dir}/transcript.txt
   (Use the Read tool with offset={start_line - 1} and limit={end_line - start_line + 1})

   Write your analysis to: {work_dir}/analysis/section_{N}.md

   Use this exact format:

   ## Section {N}: Lines {start_line}–{end_line}

   ### Summary
   [2-3 paragraphs summarizing what was discussed in this section]

   ### Key Topics
   - [Topic 1]
   - [Topic 2]

   ### Action Items
   - [Action item, if any]

   ### Notable Quotes
   - "[Exact quote]" — Speaker (timestamp)
   - "[Exact quote]" — Speaker (timestamp)
   ```

4. **Wait for all agents to complete**, then read all `{work_dir}/analysis/section_*.md` files.

5. **Synthesize** — combine the agent outputs into a unified analysis:
   - Merge all section summaries into a cohesive Executive Summary (2-3 paragraphs)
   - Consolidate all Key Topics (deduplicate)
   - Collect all Action Items
   - Select the best 5-10 Notable Quotes across all sections

Proceed to Step 6 with the synthesized analysis.

## Step 6: Create Document

Call the `create_document` MCP tool with:
- `work_dir`: the transcript work directory path
- `output_path`: `{parent_dir}/{filename_without_ext}_transcript.docx` (same folder as the original recording)
- `executive_summary`: your 2-3 paragraph executive summary
- `key_topics`: JSON array of topic strings, e.g. `'["Topic 1", "Topic 2"]'`
- `action_items`: JSON array of action item strings (pass `'[]'` if none)
- `notable_quotes`: JSON array of 5-10 significant quote strings with speaker attribution

The `create_document` MCP tool reads transcript.txt and metadata.json from the work directory and generates a professional .docx with:
1. Title page with filename
2. Metadata table (duration, language, model, speakers, word count, date)
3. Executive Summary
4. Key Topics
5. Action Items (if any)
6. Speaker Statistics (if diarization data available)
7. Full Transcript with timestamps and speaker labels
8. Notable Quotes

If the tool returns `status: "ok"`, tell the user where the document was saved. If it returns an error, report it.
