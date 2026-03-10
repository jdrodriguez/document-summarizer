---
name: transcribe
description: "Transcribe audio or video recordings into professional Word documents with timestamps and speaker labels. Use when a user provides a recording file (.mp3, .wav, .m4a, .mp4, etc.) and wants it transcribed."
---

# Legal Transcriber

Transcribe recordings using the local Whisper AI model. All processing is 100% local — no audio data leaves the machine. Follow these steps in order.

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory.

## Step 1: Validate

Confirm the user gave a path to an audio/video file. Supported: `.wav`, `.mp3`, `.m4a`, `.flac`, `.ogg`, `.wma`, `.aac`, `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`.

## Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

Parse the JSON output:
- If `status` is `"ok"`:
  - Check if `pyannote.available` is true AND `hf_token_found` is true → speaker diarization will work. **Proceed to Step 3.**
  - If `pyannote.available` is false OR `hf_token_found` is false → transcription will work but **without speaker labels**. Tell the user:
    > "Transcription will work, but speaker identification is not available. To enable it, you need a free HuggingFace account and token. Want to proceed without speaker labels, or set that up first?"
  - If the user wants to proceed without speakers, continue normally. The script handles this gracefully.
- If `status` is `"missing_dependencies"` — tell the user what's missing and offer to install.
- If the script **fails** — report the error.

## Step 3: Prepare Model

Check if the Whisper model is already cached:

```bash
ls -d ~/.cache/huggingface/hub/models--Systran--faster-whisper-medium/snapshots 2>/dev/null && echo "cached" || echo "not_cached"
```

- If cached: model is ready, proceed.
- If not cached: tell the user the model will download during transcription (first run only, ~1.5 GB).

## Step 3.5: Resolve File Path

**Important:** File paths may need resolution (~ expansion, relative paths, etc.).

```bash
python3 "$SKILL_DIR/scripts/resolve_path.py" "<user_file_path>"
```

Parse the JSON output:
- If `status` is `"found"` — use the `resolved_path` as the input file for all subsequent steps.
- If `status` is `"not_found"` — ask the user for the full path (e.g. `/Users/name/Downloads/file.mp4`).

## Step 4: Transcribe (Background + Polling)

Set `WORK_DIR` to `{parent_dir}/{filename_without_ext}_transcript_work` (using the **resolved** parent dir from Step 3.5).

1. **Before starting**, tell the user:

   > **Heads up before we begin:** Audio transcription is a computationally intensive process — the Whisper AI model will use a significant amount of your computer's CPU and memory while it runs. A few things to keep in mind:
   > - **Processing time** depends on the length of the recording. A 10-minute file may take 3-5 minutes; a 1-hour file could take 15-30 minutes or more.
   > - **Avoid running other heavy tasks** (video editing, large downloads, other AI tools) while the transcription is in progress — it will slow things down and may cause issues.
   > - Your computer's fans may spin up — that's completely normal.
   > - I'll give you regular progress updates so you always know where things stand.

2. **Launch transcription in background:**

```bash
mkdir -p "$WORK_DIR"
nohup python3 "$SKILL_DIR/scripts/transcribe_audio.py" \
  "<resolved_input_file>" "$WORK_DIR" \
  --model auto --language auto \
  > "$WORK_DIR/worker_stdout.log" 2>"$WORK_DIR/worker_stderr.log" &
echo $!
```

Capture the PID from the `echo $!` output. If the user explicitly asked to skip speaker detection, add `--no-diarize`. If user specified `--max-speakers N`, add that flag too.

3. Tell the user: "Transcription started! Monitoring progress..."

4. **Polling loop** — Read `$WORK_DIR/status.json` using the Read tool every **10 seconds**. **You MUST give the user a status update on every single poll** — never poll silently. Use friendly, varied messages so the user knows things are progressing:

   - If the file doesn't exist yet or `status` is `"starting"`:
     - "Starting up the transcription engine..."
     - If this persists for >3 polls, say: "The engine is still initializing — this can take a moment on first run."

   - If `status` is `"running"`:
     - **Always report** the `stage` and `progress` percentage with a brief message
     - Map stages to user-friendly descriptions:
       - `"extracting_audio"` → "Extracting audio from video file..."
       - `"loading_model"` → "Loading the Whisper AI model..."
       - `"transcribing"` → "Transcribing audio... {progress}% complete"
       - `"diarizing"` → "Identifying speakers..."
       - `"writing_outputs"` → "Almost done — writing transcript files..."
     - Include the `message` field if it has useful detail
     - For long transcriptions (>3 polls at the same stage), add reassurance: "Still working — this is normal for longer recordings."

   - If `status` is `"completed"`:
     - Tell the user: "Transcription complete!" and proceed to Step 5.

   - If `status` is `"error"`:
     - Report the `error` message to the user and stop.

   - To verify the process is still alive (if status seems stale):
     ```bash
     kill -0 <PID> 2>/dev/null; echo $?
     ```
     Exit 0 = alive, non-zero = dead. If dead but status.json doesn't show completed/error, check `$WORK_DIR/worker_stderr.log` for crash details.

5. Once completed, proceed to Step 5.

## Step 5: Analyze Transcript

Read `$WORK_DIR/metadata.json` for duration, language, speakers, etc. Then determine the transcript size:

```bash
wc -l < "$WORK_DIR/transcript.txt"
```

### Small transcript (500 lines or fewer)

Read the entire `$WORK_DIR/transcript.txt` directly. Proceed to Step 6 with the full transcript in context.

### Large transcript (more than 500 lines)

The transcript is too large for a single context window. Use **parallel agents** to analyze it in sections.

1. **Calculate sections** — divide lines evenly into chunks of ~500 lines each:
   - `agent_count = min(5, ceil(total_lines / 500))`
   - Each agent gets a contiguous line range (e.g., Agent 1: lines 1–500, Agent 2: lines 501–1000, etc.)

2. **Create analysis directory:**
   ```bash
   mkdir -p "$WORK_DIR/analysis"
   ```

3. **Spawn agents in parallel** — launch all agents at once using the Agent tool (`subagent_type: "general-purpose"`). Each agent's prompt:

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

4. **Wait for all agents to complete**, then read all `$WORK_DIR/analysis/section_*.md` files.

5. **Synthesize** — combine the agent outputs into a unified analysis:
   - Merge all section summaries into a cohesive Executive Summary (2-3 paragraphs)
   - Consolidate all Key Topics (deduplicate)
   - Collect all Action Items
   - Select the best 5-10 Notable Quotes across all sections

Proceed to Step 6 with the synthesized analysis.

## Step 6: Create Document

First, write the analysis to a JSON file using the Write tool:

Write to `$WORK_DIR/analysis.json`:
```json
{
  "executive_summary": "Your 2-3 paragraph executive summary here",
  "key_topics": ["Topic 1", "Topic 2"],
  "action_items": ["Action item 1", "Action item 2"],
  "notable_quotes": ["\"Quote\" — Speaker (timestamp)"]
}
```

Then generate the document:

```bash
python3 "$SKILL_DIR/scripts/create_document.py" \
  "$WORK_DIR" \
  "{parent_dir}/{filename_without_ext}_transcript.docx" \
  --analysis "$WORK_DIR/analysis.json"
```

The script reads transcript.txt and metadata.json from the work directory and generates a professional .docx with:
1. Title page with filename
2. Metadata table (duration, language, model, speakers, word count, date)
3. Executive Summary
4. Key Topics
5. Action Items (if any)
6. Speaker Statistics (if diarization data available)
7. Full Transcript with timestamps and speaker labels
8. Notable Quotes

If the script succeeds, tell the user where the document was saved. If it fails, report the error.

## Accuracy and QA (Required)

Read the full QA protocol at `$SKILL_DIR/../../QA_AND_ACCURACY.md` and follow it.

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, launch a QA agent (`subagent_type: "general-purpose"`) following the protocol in the file above. The QA agent reads all outputs and source materials, checks for hallucination and accuracy, and writes `qa_review.md`. Apply any fixes before presenting to the user.

