# Legal Toolkit — Setup Guide

## Quick Start

Most skills work out of the box after installation. A few require additional setup for full functionality.

## Speaker Diarization (Transcribe Skill)

The `/legal-toolkit:transcribe` skill can identify individual speakers in recordings (e.g., "SPEAKER_00", "SPEAKER_01"). This requires a free HuggingFace account and token.

> **Important: Local only.** Speaker diarization requires pyannote.audio + PyTorch (~1.5 GB of dependencies) and significant CPU/memory. This only works when running **Claude Code locally** on your machine. It will **not work in Claude Desktop / Cowork** — the Cowork VM does not have the resources or persistent storage to support PyTorch. In Cowork, transcription still works perfectly, you just won't get speaker labels.

### Why is this needed?

Speaker diarization uses the [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) model, which is hosted on HuggingFace behind a license agreement. The token authenticates you to download the model.

**Without the token:** Transcription works perfectly — you get full text with timestamps. You just won't get speaker labels.

**With the token (local Claude Code only):** Each segment is attributed to a speaker, and you get speaker statistics in the final report.

### Step 1: Create a HuggingFace Account

1. Go to [huggingface.co/join](https://huggingface.co/join)
2. Sign up (free)

### Step 2: Accept the Model License

1. Go to [huggingface.co/pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
2. Click "Agree and access repository" (you must be logged in)
3. Also accept the license for [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)

### Step 3: Create an Access Token

1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Click "New token"
3. Name it something like "legal-toolkit"
4. Select "Read" access (that's all you need)
5. Click "Generate"
6. Copy the token (starts with `hf_...`)

### Step 4: Save the Token

**Option A — Save to file (recommended):**

```bash
mkdir -p ~/.huggingface
echo "hf_YOUR_TOKEN_HERE" > ~/.huggingface/token
```

**Option B — Set as environment variable:**

Add to your `~/.zshrc` (Mac) or `~/.bashrc` (Linux):

```bash
export HF_TOKEN="hf_YOUR_TOKEN_HERE"
```

Then restart your terminal or run `source ~/.zshrc`.

### Step 5: Install pyannote.audio (if not already installed)

```bash
pip install pyannote.audio
```

This installs PyTorch and the diarization pipeline (~1.5 GB). First-time model download adds another ~500 MB.

### Verify Setup

Run the transcribe skill on any recording. If diarization is working, you'll see:
- "Identifying speakers..." during the progress updates
- Speaker labels (SPEAKER_00, SPEAKER_01, etc.) in the transcript
- A "Speaker Statistics" table in the final document

If you see "No HuggingFace token found" in the logs, double-check Step 4.

## Other Skills

All other skills in the Legal Toolkit work without additional setup. Dependencies are auto-installed on first run.

| Skill | Extra Setup Needed? | Works in Cowork? |
|-------|-------------------|-----------------|
| Transcribe (basic) | None | Yes |
| Transcribe (with speakers) | HuggingFace token + pyannote (see above) | No (local Claude Code only) |
| OCR | None (PaddleOCR auto-installs) | Yes |
| All other skills | None | Yes |
