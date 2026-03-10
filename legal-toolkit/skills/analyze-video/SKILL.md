---
name: analyze-video
description: "Analyze video files frame-by-frame for forensic review with scene detection and multi-pass extraction. Use when: (1) a user provides a video file and wants frame-by-frame analysis, (2) a user says 'analyze this video', 'review body cam footage', 'forensic video review', 'analyze surveillance footage', 'evidence video review', or 'body cam analysis', (3) any forensic or evidentiary task involving video recordings such as body cam, dashcam, surveillance, or cell phone video, (4) a user needs a detailed timeline of events from video footage with key moment flagging and scene change detection."
---

# Forensic Video Analyzer

Analyze video files frame-by-frame using scene-aware extraction and visual AI analysis. Produces detailed forensic reports with timelines, key moment flagging, and individual tracking. All frame extraction runs locally via ffmpeg.

**Supported formats**: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.ts`, `.mts`, `.m2ts`
**Input**: single video file

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Agent Delegation (Required)

Video analysis is extremely token-intensive — processing 50-500+ frames through vision will exceed a single agent's context window. You MUST delegate frame analysis to subagents.

### Orchestrator Workflow

1. **You handle**: Steps 1-4 below (validate, check deps, warn user, extract frames).
2. **After frame extraction**, read the chapter directory structure to get chapter count and frame counts per chapter.
3. **Launch one subagent per chapter in parallel** (Agent tool, `subagent_type: "general-purpose"`). Run `mkdir -p "$OUTPUT_DIR/chapters"` first. Substitute the resolved `$OUTPUT_DIR` path literally into each agent's prompt — do not pass shell variable names. Each agent's prompt:
   > "You are analyzing video frames for forensic review. Read `$OUTPUT_DIR/frames/chapter_{NNN}/metadata.json` for the chapter's time range. Then read all frame images in `$OUTPUT_DIR/frames/chapter_{NNN}/` in chronological order, in batches of 10-20.
   >
   > For each frame, describe: visible elements, actions, environment, visible text, and changes from previous frame. Flag key moments: use of force, weapons, new individuals, evidence handling, restraints, camera shifts. Group similar consecutive frames into segments with timestamp ranges.
   >
   > Write your analysis to `$OUTPUT_DIR/chapters/chapter_{NNN}_analysis.md` with: chapter summary, frame descriptions (grouped into segments), key moments table, and individuals observed."

4. **Collect and compile**: After all chapter agents complete, read all `chapter_*_analysis.md` files. Assemble the forensic report (Step 6) from the chapter analyses — compile the timeline, key moments, individuals, and evidence notes. Write `forensic_report.md`. Do NOT re-analyze frames yourself.
5. **Present**: Show Video Summary and Key Moments per Step 7.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path to a video file. If not, ask: "Please provide the path to the video file you want to analyze."
2. Verify the file exists and has a supported extension.
3. Note the file size and warn if it is very large (>2 GB): "This is a large video file. Frame extraction may take several minutes."

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).
- ffmpeg is required. If not found, tell the user: "ffmpeg is required for video frame extraction. Install with: `brew install ffmpeg`"

### Step 3: Warn About Processing

Before starting, tell the user:

> **Heads up before we begin:** Video analysis involves extracting frames and analyzing each one visually. A few things to keep in mind:
> - **Frame extraction** uses ffmpeg locally — no video data leaves your machine.
> - **Processing time** depends on video length and extraction density. A 10-minute video typically produces 50-200 frames and takes a few minutes to extract.
> - **Visual analysis** of each frame uses Claude's vision capabilities. I'll process frames in batches and give you progressive updates.
> - For long videos (>30 minutes), I'll deliver chapter-by-chapter summaries as I go so you see results immediately.

### Step 4: Extract Frames

Set `OUTPUT_DIR` to `{parent_dir}/{filename_without_ext}_video_analysis`.

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/extract_frames.py" "<video_path>" --output-dir "$OUTPUT_DIR"
```

#### Extraction Options

All options are optional — defaults are tuned for forensic review:

| Flag | Default | Description |
|---|---|---|
| `--coarse-fps` | `0.5` | Frames per second for coarse pass (1 frame every 2 seconds) |
| `--dense-fps` | `2.0` | Frames per second for dense pass around scene changes |
| `--scene-threshold` | `0.3` | Scene change detection sensitivity (0.0-1.0, lower = more sensitive) |
| `--dense-window` | `3.0` | Seconds before/after a scene change to apply dense extraction |
| `--chapter-duration` | `120` | Duration in seconds for each chapter grouping |
| `--max-frames` | `500` | Maximum total frames to extract |
| `--offset-pass` | _(disabled)_ | Enable a secondary extraction pass with a time offset for gap coverage |

For short clips (<5 minutes), consider increasing `--coarse-fps` to `1.0` or `2.0` for more coverage.
For very long videos (>60 minutes), consider decreasing `--coarse-fps` to `0.25` and increasing `--chapter-duration` to `300`.

The script creates a directory structure under `$OUTPUT_DIR/frames/`:
```
frames/
  chapter_001/
    metadata.json
    frame_000001_00m05s.jpg
    frame_000002_00m07s.jpg
    ...
  chapter_002/
    metadata.json
    ...
```

Monitor stderr for progress and relay to the user:
- "Detecting scene changes..."
- "Running coarse extraction pass..."
- "Running dense extraction around scene changes..."
- "Organizing frames into chapters..."
- "Extraction complete: X frames in Y chapters."

### Step 5: Analyze Frames Chapter by Chapter

**Note:** This step is handled by the per-chapter subagents launched in the Agent Delegation section above. Skip to Step 6 to compile the report from their outputs.

The following instructions are the specifications each subagent follows. For each chapter:

1. **Read `metadata.json`** to understand the chapter's time range, frame count, and any scene change markers.

2. **Batch frames in groups of 10-20** for efficient analysis with context continuity. Read each frame image in chronological order within the batch.

3. **For each frame, describe:**
   - **Visible elements**: People, objects, vehicles, furniture, text, badges, weapons, tools, evidence items
   - **Actions**: Walking, talking, reaching, running, standing, sitting, gesturing, struggling, writing
   - **Environment**: Indoor/outdoor, lighting conditions (bright, dim, dark, artificial), weather if visible, room type, location identifiers
   - **Visible text**: Signs, documents, license plates, badges, name tags, timestamps overlaid on video
   - **Changes from previous frame**: Movement, new elements, departures, posture changes, camera angle shifts

4. **Flag key moments** — mark any frame containing:
   - Use of force or physical contact between individuals
   - Weapons drawn, displayed, or visible
   - New individuals entering the scene
   - Handcuffs, restraints, or detention actions
   - Evidence handling (picking up, bagging, tagging, photographing)
   - Doors opening or closing, entering/exiting vehicles or buildings
   - Gestures that may indicate distress, compliance, or resistance
   - Sudden camera movement or perspective shifts (especially for body cam)

5. **Group consecutive similar frames** into segments with a single description and a timestamp range (e.g., "00:02:15 - 00:02:45: Officer walks through parking lot toward building entrance, no other individuals visible").

6. **For long videos, deliver a chapter summary to the user as each chapter completes** so they see progressive results. Format:
   > **Chapter 3 (04:00 - 06:00):** Brief summary of events in this chapter. Key moments: [list if any].

### Step 6: Generate the Report

Save the full report as `$OUTPUT_DIR/forensic_report.md` with these sections:

#### Video Summary
- File name, duration, resolution (if available from metadata)
- Location (if visible in footage or overlay text)
- Number of distinct individuals observed
- Total key events flagged
- Overall description of what the video depicts

#### Timeline of Events
Chronological list with:
- **Timestamp** (from frame metadata)
- **Description** of what occurs
- **Significance**: `routine` | `notable` | `critical`

Example:
```
| Timestamp | Event | Significance |
|-----------|-------|-------------|
| 00:00:05 | Officer exits patrol vehicle in parking lot | routine |
| 00:01:12 | Officer approaches individual standing near building entrance | notable |
| 00:02:45 | Individual reaches toward waistband; officer issues verbal command | critical |
```

#### Key Moments
Detailed analysis of each flagged critical frame:
- Timestamp and frame reference (file name)
- Full description of what is visible
- Why it was flagged
- Context from surrounding frames

#### Individuals Observed
For each distinct person visible in the footage:
- Physical description (clothing, build, distinguishing features visible)
- First appearance timestamp
- Last appearance timestamp
- Role if identifiable (officer, civilian, witness, suspect, etc.)
- Key actions taken

#### Evidence Notes
Any items, documents, weapons, contraband, or evidence visible:
- What it is
- When it first appears
- Who handles it
- Chain of custody observations (who touched it, was it bagged/tagged)

#### Scene Changes
Summary of major transitions:
- Location changes
- Camera perspective shifts
- Lighting changes
- Time gaps (if timestamps jump)

#### Gaps or Concerns
- Video quality issues (blur, compression artifacts, low resolution)
- Obstructed views (hand over lens, camera pointed at ground)
- Dark or unlit periods where nothing is discernible
- Missing time gaps (timestamp jumps suggesting cuts or pauses)
- Audio references if overlay text mentions audio events not visible in frames

### Step 7: Present Results

1. Present the **Video Summary** section to the user.
2. Highlight the **Key Moments** with timestamps so the user can jump to those points in the original video.
3. Inform the user that the full report is saved at `$OUTPUT_DIR/forensic_report.md`.
4. List all output files:
   - `forensic_report.md` — full forensic analysis report
   - `frames/` — all extracted frames organized by chapter with metadata

### Step 8: Offer Additional Actions

1. **DOCX export**: "Would you like me to generate a formal forensic report as a Word document (.docx)?" — If yes, use the `docx` skill to produce a professional document with title page, table of contents, embedded key frame images, and all report sections.
2. **Specific moment deep-dive**: If the user asks about a specific timestamp or event, locate the nearest frames and provide detailed analysis.
3. **Re-extract with different settings**: If the user wants more detail in a specific time range, re-run extraction with higher `--dense-fps` or adjusted `--scene-threshold`.
4. **Compare with other evidence**: Offer to cross-reference timestamps with other evidence (photos via `analyze-photos`, communications via `analyze-communications`).


## Accuracy and QA (Required)

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, invoke `/legal-toolkit:qa-check` on the work/output directory. Do not skip this step.

## Important Analysis Instructions

- **Be objective and factual.** Describe only what is visible in each frame. Do not speculate about intent, motive, or events not depicted.
- **Use precise timestamps** from the frame metadata. Never estimate or round timestamps.
- **Note limitations honestly.** When the view is obstructed, too dark, blurry, or at an angle that prevents clear identification, say so explicitly.
- **Body cam specifics**: Note camera perspective shifts (looking up, down, sideways, rapid turning). Body cam footage frequently has motion blur and unusual angles — flag these rather than guessing at obscured content.
- **Do not identify individuals by name** unless their name is clearly visible on a badge, name tag, or document in the frame. Use descriptive labels ("Officer 1", "Civilian in red jacket").
- **Batch efficiently**: Process frames in groups of 10-20 to maintain context continuity while keeping analysis manageable.
- **Progressive delivery**: For videos longer than 10 minutes, deliver chapter summaries as each chapter completes so the user receives results incrementally.

## Error Handling

- **Path not found**: Ask user to verify the file path
- **Unsupported format**: List supported formats above and ask user to check the file extension
- **ffmpeg not found**: "ffmpeg is required for video frame extraction. Install with: `brew install ffmpeg`"
- **Extraction produces no frames**: "No frames were extracted. The video file may be corrupted or empty. Try playing it in a media player to verify."
- **Very dark or blank frames**: "Many extracted frames are very dark or blank. The video may have been recorded in low-light conditions or the lens was obstructed."
- **Extraction takes too long**: Suggest reducing `--coarse-fps` or `--max-frames`
- **Too many frames**: Suggest increasing `--scene-threshold` or reducing `--coarse-fps`
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
