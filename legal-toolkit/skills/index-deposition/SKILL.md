---
name: index-deposition
description: "Index deposition video/audio recordings with transcription, speaker identification, topic indexing, and key moment detection. Use when: (1) a user provides a deposition recording and asks for it to be indexed, transcribed, or analyzed, (2) a user says 'index this deposition', 'transcribe this video', 'find key moments', 'create a depo index', or 'testimony timeline', (3) any litigation support task requiring searchable deposition transcripts with timecodes, (4) a user needs page:line format transcripts, topic indexes, or key moment flagging from recorded testimony."
---

# Deposition Video Indexer

Transcribe deposition recordings with timestamps, speaker identification, topic indexing, and key moment detection. All processing is 100% local — no data leaves the machine.

**Supported formats**: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.wav`, `.mp3`, `.m4a`, `.flac`, `.ogg`, `.wma`, `.aac`
**Input**: single audio or video file

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path to an audio/video file. If not, ask: "Please provide the path to the deposition recording you want to index."
2. Verify the file exists and has a supported extension.
3. If the file is a video format, note that audio will be extracted first.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).
- Note whether pyannote.audio is available (for speaker diarization). If not, inform the user: "Speaker diarization is not available — the transcript will not have speaker labels. To enable it, install pyannote.audio manually."
- Note: On first run, the Whisper model will be downloaded automatically (~466 MB for small, ~1.5 GB for medium).

### Step 3: Warn About Processing Time

Before starting, tell the user:

> **Heads up before we begin:** Deposition indexing involves AI transcription, which is computationally intensive. A few things to keep in mind:
> - **Processing time** depends on recording length. A 30-minute deposition may take 5-10 minutes; a 2-hour deposition could take 30-60 minutes.
> - **Whisper model download** on first run: ~466 MB (small) or ~1.5 GB (medium). This only happens once.
> - Your computer's fans may spin up — that's completely normal.
> - I'll monitor progress and give you regular updates.

### Step 4: Run the Indexer

Set `OUTPUT_DIR` to `{parent_dir}/{filename_without_ext}_depo_index`.

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/index_deposition.py" \
  --input "<audio_or_video_path>" \
  --output-dir "$OUTPUT_DIR"
```

Optional flags:
- `--model small` — force a specific Whisper model (default: auto based on duration)
- `--language en` — force language (default: auto-detect)
- `--no-diarize` — skip speaker diarization even if pyannote is available
- `--max-speakers 4` — maximum number of speakers to detect (default: 4)

The script prints progress to stderr and JSON results to stdout. **This can take a long time.** Monitor stderr for progress updates and relay them to the user with friendly messages:
- "Extracting audio from video file..."
- "Loading the Whisper AI model..."
- "Transcribing audio... X% complete"
- "Identifying speakers..."
- "Building topic index..."
- "Detecting key moments..."
- "Writing output files..."

For long depositions (>3 progress updates at the same stage), add reassurance: "Still working — this is normal for longer recordings."

### Step 5: Present Deposition Summary

Read `$OUTPUT_DIR/deposition_summary.txt` and present to the user:
- Recording duration
- Number of speakers identified
- Total word count
- Number of transcript pages (page:line format)
- Number of key moments detected
- Number of topics identified

### Step 6: Highlight Key Moments

Read `$OUTPUT_DIR/key_moments.json` and present the most important findings:

**Admissions**: List any statements where the witness made admissions
**Objections**: Note objection patterns and frequency
**Key Legal Terms**: Highlight uses of "I don't recall", "to the best of my recollection", etc.
**Contradictions**: Flag any potential inconsistencies in testimony

For each key moment, include the timecode and brief context so the user can jump to that point in the recording.

### Step 7: Direct to Interactive Timeline

Tell the user:
> Your testimony timeline is ready at: `$OUTPUT_DIR/testimony_timeline.html`
> Open it in a browser to navigate the deposition visually. Topics are marked on the timeline and key moments are flagged.

Also mention the full outputs:
- `transcript.txt` — full timestamped transcript
- `page_line_transcript.txt` — court reporter style page:line format
- `topic_index.json` — searchable topic index with timecodes
- `key_moments.json` — all flagged moments
- `index_metadata.json` — full metadata

### Step 8: Offer Additional Analysis

Ask the user:

1. "Would you like me to generate a formal deposition summary as a Word document (.docx)?" — If yes, use the `docx` skill to produce a professional document with:
   - Title page with deposition details
   - Executive summary of testimony
   - Key testimony highlights
   - Topic-by-topic breakdown
   - Full transcript appendix

2. "Would you like me to run the transcript through `/legal-toolkit:summarize` for a detailed analysis?" — If yes, pipe `$OUTPUT_DIR/transcript.txt` to the summarizer skill.

## Error Handling

- **Path not found**: Ask user to verify the path
- **Unsupported format**: Supported types listed above
- **ffmpeg not found**: "ffmpeg is required for audio/video processing. Install with: brew install ffmpeg"
- **Whisper model download fails**: Check internet connection; suggest retrying
- **Out of memory**: Suggest using a smaller model (`--model small` or `--model tiny`)
- **Corrupt audio**: "The audio file may be corrupted. Try re-exporting from the original source."
- **No speech detected**: "No speech was detected in the recording. Verify the correct file was provided."
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
