#!/usr/bin/env python3
"""
Deposition Video Indexer — transcribe deposition recordings with timestamps,
speaker identification, topic indexing, and key moment detection.

Usage:
    python3 index_deposition.py --input <video_or_audio> --output-dir <dir> \
        [--model small] [--language en] [--no-diarize] [--max-speakers 4]

Outputs (all written to --output-dir):
    transcript.txt             Full timestamped transcript with speaker labels
    page_line_transcript.txt   Court reporter style page:line format
    topic_index.json           Topics with start/end timecodes
    key_moments.json           Flagged moments with timecode, type, context
    testimony_timeline.html    Interactive Plotly timeline
    deposition_summary.txt     Human-readable overview
    index_metadata.json        Full metadata

Prints JSON summary to stdout. Progress/errors go to stderr.
Exit codes: 0 = success, 1 = partial success, 2 = failure.
"""

import argparse
import json
import math
import os
import re
import sys
import tempfile
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging helpers — progress to stderr, results to stdout
# ---------------------------------------------------------------------------

def log(msg: str):
    print(msg, file=sys.stderr, flush=True)


def log_progress(stage: str, progress: float = 0, detail: str = ""):
    payload = {"stage": stage, "progress": round(progress, 1)}
    if detail:
        payload["detail"] = detail
    print(json.dumps(payload), file=sys.stderr, flush=True)


def format_timecode(seconds: float) -> str:
    """Format seconds into HH:MM:SS.mmm timecode."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    return f"{m:02d}:{s:02d}.{ms:03d}"


def format_timecode_short(seconds: float) -> str:
    """Format seconds into HH:MM:SS for display."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Supported formats
# ---------------------------------------------------------------------------

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".wma", ".aac"}
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


# ---------------------------------------------------------------------------
# Audio extraction
# ---------------------------------------------------------------------------

def get_audio_duration(filepath: str) -> float:
    """Get duration in seconds using pydub."""
    from pydub import AudioSegment
    try:
        audio = AudioSegment.from_file(filepath)
        return len(audio) / 1000.0
    except Exception as e:
        log(f"WARNING: Could not determine duration via pydub: {e}")
        return 0.0


def extract_audio(input_path: str, output_dir: str) -> str:
    """Extract/convert audio to WAV 16kHz mono for Whisper processing.

    Returns path to the WAV file.
    """
    ext = Path(input_path).suffix.lower()
    wav_path = os.path.join(output_dir, "audio_16k_mono.wav")

    log_progress("extracting_audio", 0, f"Converting {ext} to WAV 16kHz mono...")

    from pydub import AudioSegment

    try:
        audio = AudioSegment.from_file(input_path)
    except Exception as e:
        log(f"ERROR: Failed to load audio file: {e}")
        log("Make sure ffmpeg is installed: brew install ffmpeg")
        raise

    # Convert to mono 16kHz
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(wav_path, format="wav")

    duration = len(audio) / 1000.0
    log_progress("extracting_audio", 100, f"Audio extracted: {format_timecode_short(duration)}")
    return wav_path


# ---------------------------------------------------------------------------
# Whisper transcription
# ---------------------------------------------------------------------------

def select_model(duration_seconds: float, user_model: str | None = None) -> str:
    """Select Whisper model based on duration."""
    if user_model and user_model != "auto":
        return user_model
    if duration_seconds < 1800:  # < 30 minutes
        return "small"
    return "medium"


def transcribe_audio(wav_path: str, model_name: str, language: str | None = None) -> dict:
    """Transcribe audio using faster-whisper.

    Returns dict with 'segments' list and 'info' metadata.
    """
    from faster_whisper import WhisperModel

    log_progress("loading_model", 0, f"Loading Whisper model: {model_name}...")

    # Use int8 for speed on CPU, float16 for GPU
    compute_type = "int8"
    device = "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
            compute_type = "float16"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            # MPS (Apple Silicon) — use CPU with int8 for faster-whisper
            device = "cpu"
            compute_type = "int8"
    except ImportError:
        pass

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    log_progress("loading_model", 100, "Model loaded.")

    log_progress("transcribing", 0, "Starting transcription...")

    lang = language if language and language != "auto" else None
    segments_gen, info = model.transcribe(
        wav_path,
        language=lang,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200,
        ),
    )

    # Collect segments with progress tracking
    segments = []
    total_duration = info.duration if hasattr(info, "duration") and info.duration else 0
    last_progress = 0

    for seg in segments_gen:
        segments.append({
            "id": seg.id,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
            "words": [
                {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                for w in (seg.words or [])
            ],
        })

        if total_duration > 0:
            progress = min(99, (seg.end / total_duration) * 100)
            if progress - last_progress >= 2:  # Report every 2%
                log_progress("transcribing", progress,
                             f"Transcribed {format_timecode_short(seg.end)} of "
                             f"{format_timecode_short(total_duration)}")
                last_progress = progress

    log_progress("transcribing", 100, f"Transcription complete: {len(segments)} segments")

    return {
        "segments": segments,
        "language": info.language if hasattr(info, "language") else "unknown",
        "language_probability": info.language_probability if hasattr(info, "language_probability") else 0,
        "duration": info.duration if hasattr(info, "duration") else (
            segments[-1]["end"] if segments else 0
        ),
    }


# ---------------------------------------------------------------------------
# Speaker diarization (optional — requires pyannote.audio)
# ---------------------------------------------------------------------------

def try_diarize(wav_path: str, max_speakers: int = 4) -> dict | None:
    """Attempt speaker diarization using pyannote.audio.

    Returns dict mapping (start, end) -> speaker_label, or None if unavailable.
    """
    try:
        import importlib.util
        if importlib.util.find_spec("pyannote.audio") is None:
            log("Speaker diarization: pyannote.audio not installed. Skipping.")
            return None
    except Exception:
        log("Speaker diarization: pyannote.audio not available. Skipping.")
        return None

    log_progress("diarizing", 0, "Loading speaker diarization model...")

    try:
        from pyannote.audio import Pipeline
        import torch

        # Check for HuggingFace token
        hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
        if not hf_token:
            for token_path in [
                os.path.expanduser("~/.huggingface/token"),
                os.path.expanduser("~/.cache/huggingface/token"),
            ]:
                if os.path.exists(token_path):
                    with open(token_path) as f:
                        hf_token = f.read().strip()
                    break

        if not hf_token:
            log("Speaker diarization: No HuggingFace token found. Skipping.")
            log("  To enable: set HUGGINGFACE_TOKEN env var or run `huggingface-cli login`")
            return None

        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token,
        )

        # Use GPU if available
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))

        log_progress("diarizing", 30, "Running speaker diarization...")
        diarization = pipeline(wav_path, max_speakers=max_speakers)

        # Build speaker map: list of (start, end, speaker)
        speaker_turns = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speaker_turns.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker,
            })

        log_progress("diarizing", 100, f"Identified {len(set(t['speaker'] for t in speaker_turns))} speakers")
        return speaker_turns

    except Exception as e:
        log(f"Speaker diarization failed: {e}")
        log("Continuing without speaker labels.")
        return None


def assign_speakers(segments: list[dict], speaker_turns: list[dict] | None) -> list[dict]:
    """Assign speaker labels to transcript segments based on diarization."""
    if not speaker_turns:
        for seg in segments:
            seg["speaker"] = None
        return segments

    for seg in segments:
        seg_mid = (seg["start"] + seg["end"]) / 2
        best_speaker = None
        best_overlap = 0

        for turn in speaker_turns:
            # Calculate overlap
            overlap_start = max(seg["start"], turn["start"])
            overlap_end = min(seg["end"], turn["end"])
            overlap = max(0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn["speaker"]

        seg["speaker"] = best_speaker

    return segments


# ---------------------------------------------------------------------------
# Page:line transcript generation
# ---------------------------------------------------------------------------

LINES_PER_PAGE = 25  # Standard deposition page


def generate_page_line_transcript(segments: list[dict]) -> str:
    """Convert segments to court reporter style page:line format."""
    lines = []
    current_line = 1
    current_page = 1

    # Header
    lines.append(f"{'':>10}PAGE {current_page}")
    lines.append("")

    for seg in segments:
        speaker = seg.get("speaker") or "UNKNOWN"
        text = seg["text"]
        timecode = format_timecode_short(seg["start"])

        # Speaker label line
        prefix = f"  {current_page:>3}:{current_line:<3}  "
        speaker_line = f"{prefix}{speaker} [{timecode}]:"
        lines.append(speaker_line)
        current_line += 1

        if current_line > LINES_PER_PAGE:
            current_page += 1
            current_line = 1
            lines.append("")
            lines.append(f"{'':>10}PAGE {current_page}")
            lines.append("")

        # Wrap text to ~65 chars per line
        words = text.split()
        line_buf = ""
        for word in words:
            if len(line_buf) + len(word) + 1 > 65:
                prefix = f"  {current_page:>3}:{current_line:<3}  "
                lines.append(f"{prefix}{line_buf.strip()}")
                line_buf = word + " "
                current_line += 1

                if current_line > LINES_PER_PAGE:
                    current_page += 1
                    current_line = 1
                    lines.append("")
                    lines.append(f"{'':>10}PAGE {current_page}")
                    lines.append("")
            else:
                line_buf += word + " "

        if line_buf.strip():
            prefix = f"  {current_page:>3}:{current_line:<3}  "
            lines.append(f"{prefix}{line_buf.strip()}")
            current_line += 1

            if current_line > LINES_PER_PAGE:
                current_page += 1
                current_line = 1
                lines.append("")
                lines.append(f"{'':>10}PAGE {current_page}")
                lines.append("")

    return "\n".join(lines), current_page


# ---------------------------------------------------------------------------
# Topic indexing
# ---------------------------------------------------------------------------

def build_topic_index(segments: list[dict], min_topic_duration: float = 60) -> list[dict]:
    """Identify topic changes based on content shifts.

    Uses a simple approach: groups of segments with shared key terms form a topic.
    """
    if not segments:
        return []

    # Combine segments into windows of ~60 seconds
    windows = []
    current_window = {"start": segments[0]["start"], "end": 0, "texts": [], "segments": []}

    for seg in segments:
        current_window["texts"].append(seg["text"])
        current_window["segments"].append(seg)
        current_window["end"] = seg["end"]

        if seg["end"] - current_window["start"] >= min_topic_duration:
            windows.append(current_window)
            current_window = {"start": seg["end"], "end": 0, "texts": [], "segments": []}

    if current_window["texts"]:
        windows.append(current_window)

    # Extract key terms per window (simple approach: most frequent non-stop words)
    stop_words = {
        "the", "a", "an", "is", "was", "were", "are", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
        "us", "them", "my", "your", "his", "its", "our", "their", "mine",
        "yours", "hers", "ours", "theirs", "this", "that", "these", "those",
        "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
        "neither", "each", "every", "all", "any", "few", "more", "most",
        "other", "some", "such", "no", "only", "own", "same", "than",
        "too", "very", "just", "because", "as", "until", "while", "of",
        "at", "by", "for", "with", "about", "against", "between", "through",
        "during", "before", "after", "above", "below", "to", "from", "up",
        "down", "in", "out", "on", "off", "over", "under", "again", "further",
        "then", "once", "here", "there", "when", "where", "why", "how",
        "what", "which", "who", "whom", "if", "whether", "well", "okay",
        "yes", "no", "um", "uh", "like", "know", "right", "going", "think",
        "said", "say", "says", "told", "tell", "tells", "go", "went", "gone",
        "come", "came", "get", "got", "make", "made", "take", "took", "see",
        "saw", "give", "gave", "put", "let",
    }

    topics = []
    for window in windows:
        combined_text = " ".join(window["texts"])
        words = re.findall(r'\b[a-zA-Z]{3,}\b', combined_text.lower())
        word_freq = defaultdict(int)
        for w in words:
            if w not in stop_words:
                word_freq[w] += 1

        # Top 5 terms as topic descriptor
        top_terms = sorted(word_freq.items(), key=lambda x: -x[1])[:5]
        topic_label = ", ".join(t[0].title() for t in top_terms) if top_terms else "General Discussion"

        topics.append({
            "topic": topic_label,
            "start_time": window["start"],
            "end_time": window["end"],
            "start_timecode": format_timecode_short(window["start"]),
            "end_timecode": format_timecode_short(window["end"]),
            "duration_seconds": round(window["end"] - window["start"], 1),
            "segment_count": len(window["segments"]),
            "summary_text": combined_text[:500],
        })

    return topics


# ---------------------------------------------------------------------------
# Key moments detection
# ---------------------------------------------------------------------------

# Pattern categories for key moment detection
KEY_MOMENT_PATTERNS = {
    "admission": [
        r"\bi admit\b", r"\bthat'?s correct\b", r"\byes,?\s*i did\b",
        r"\bi acknowledge\b", r"\bi agree\b", r"\bthat is true\b",
        r"\bi confirm\b", r"\byou'?re right\b", r"\bthat'?s right\b",
        r"\bi concede\b", r"\bi accept\b",
    ],
    "objection": [
        r"\bobjection\b", r"\binstruct the witness\b", r"\bmove to strike\b",
        r"\basked and answered\b", r"\bbeyond the scope\b", r"\bcalls for speculation\b",
        r"\bform of the question\b", r"\bcompound question\b", r"\bargumentative\b",
        r"\bassuming facts\b", r"\bvague and ambiguous\b", r"\blacks foundation\b",
    ],
    "uncertainty": [
        r"\bi don'?t recall\b", r"\bi don'?t remember\b",
        r"\bto the best of my recollection\b", r"\bi'?m not sure\b",
        r"\bi can'?t recall\b", r"\bi can'?t remember\b",
        r"\bi have no recollection\b", r"\bi don'?t know\b",
        r"\bnot to my knowledge\b", r"\bi'?m not certain\b",
        r"\bi believe so\b", r"\bi think so\b",
    ],
    "legal_term": [
        r"\bunder oath\b", r"\bsworn testimony\b", r"\bfor the record\b",
        r"\boff the record\b", r"\blet the record reflect\b",
        r"\bstipulat\w+\b", r"\bexhibit\s+\w+\b", r"\bpreviously marked\b",
        r"\bso stipulated\b", r"\blet me mark\b",
    ],
    "emotional": [
        r"\bi need a break\b", r"\bcan we take a break\b",
        r"\bi'?m upset\b", r"\bthis is difficult\b",
        r"\bi'?d rather not\b", r"\bthat'?s personal\b",
        r"\bi refuse\b", r"\bi won'?t answer\b",
    ],
    "contradiction": [
        r"\bbut you (just |previously )?said\b", r"\bearlier you (stated|said|testified)\b",
        r"\bthat contradicts\b", r"\bthat'?s inconsistent\b",
        r"\bisn'?t it true that\b", r"\bdidn'?t you (just )?say\b",
        r"\bcontrary to\b", r"\bin your (prior |previous )?(testimony|statement|deposition)\b",
    ],
}

COMPILED_KEY_PATTERNS = {
    cat: [re.compile(p, re.IGNORECASE) for p in patterns]
    for cat, patterns in KEY_MOMENT_PATTERNS.items()
}


def detect_key_moments(segments: list[dict]) -> list[dict]:
    """Scan transcript segments for key moments."""
    moments = []

    for seg in segments:
        text = seg["text"]
        timecode = format_timecode_short(seg["start"])
        speaker = seg.get("speaker") or "UNKNOWN"

        for category, patterns in COMPILED_KEY_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    moments.append({
                        "type": category,
                        "timecode": timecode,
                        "time_seconds": seg["start"],
                        "speaker": speaker,
                        "matched_text": match.group(0),
                        "context": text[:500],
                        "segment_id": seg["id"],
                    })
                    break  # One match per category per segment

    return moments


# ---------------------------------------------------------------------------
# Output: full timestamped transcript
# ---------------------------------------------------------------------------

def write_transcript(segments: list[dict], output_path: str):
    """Write full timestamped transcript with speaker labels."""
    lines = []
    for seg in segments:
        tc = format_timecode(seg["start"])
        speaker = seg.get("speaker") or ""
        speaker_prefix = f"[{speaker}] " if speaker else ""
        lines.append(f"[{tc}] {speaker_prefix}{seg['text']}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Output: interactive timeline
# ---------------------------------------------------------------------------

def build_testimony_timeline(segments: list[dict], topics: list[dict],
                              key_moments: list[dict], speaker_turns: list[dict] | None,
                              output_path: str):
    """Create an interactive Plotly timeline HTML."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=3, cols=1,
        row_heights=[0.4, 0.3, 0.3],
        subplot_titles=("Topics", "Key Moments", "Speaker Distribution"),
        vertical_spacing=0.08,
        shared_xaxes=True,
    )

    # Topic bars
    topic_colors = [
        "#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336",
        "#00BCD4", "#795548", "#E91E63", "#3F51B5", "#CDDC39",
    ]
    for i, topic in enumerate(topics):
        color = topic_colors[i % len(topic_colors)]
        fig.add_trace(go.Bar(
            x=[topic["duration_seconds"]],
            y=["Topics"],
            orientation="h",
            base=[topic["start_time"]],
            name=topic["topic"][:40],
            marker=dict(color=color),
            text=topic["topic"][:40],
            textposition="inside",
            hovertext=f"<b>{topic['topic']}</b><br>"
                       f"{topic['start_timecode']} - {topic['end_timecode']}<br>"
                       f"Duration: {topic['duration_seconds']:.0f}s",
            hoverinfo="text",
            showlegend=True,
        ), row=1, col=1)

    # Key moments scatter
    moment_colors = {
        "admission": "#F44336",
        "objection": "#FF9800",
        "uncertainty": "#9E9E9E",
        "legal_term": "#2196F3",
        "emotional": "#E91E63",
        "contradiction": "#9C27B0",
    }
    for moment_type in set(m["type"] for m in key_moments):
        type_moments = [m for m in key_moments if m["type"] == moment_type]
        fig.add_trace(go.Scatter(
            x=[m["time_seconds"] for m in type_moments],
            y=[moment_type.replace("_", " ").title()] * len(type_moments),
            mode="markers",
            name=moment_type.replace("_", " ").title(),
            marker=dict(
                size=10,
                color=moment_colors.get(moment_type, "#9E9E9E"),
                symbol="diamond",
            ),
            text=[
                f"<b>{m['type'].replace('_', ' ').title()}</b><br>"
                f"Time: {m['timecode']}<br>"
                f"Speaker: {m['speaker']}<br>"
                f"Match: \"{m['matched_text']}\"<br>"
                f"<br>{m['context'][:200]}"
                for m in type_moments
            ],
            hoverinfo="text",
        ), row=2, col=1)

    # Speaker distribution
    if speaker_turns:
        speakers = sorted(set(t["speaker"] for t in speaker_turns))
        speaker_colors = ["#2196F3", "#F44336", "#4CAF50", "#FF9800", "#9C27B0",
                          "#00BCD4", "#795548", "#E91E63"]
        for i, speaker in enumerate(speakers):
            turns = [t for t in speaker_turns if t["speaker"] == speaker]
            for turn in turns:
                fig.add_trace(go.Bar(
                    x=[turn["end"] - turn["start"]],
                    y=[speaker],
                    orientation="h",
                    base=[turn["start"]],
                    name=speaker,
                    marker=dict(color=speaker_colors[i % len(speaker_colors)]),
                    showlegend=False,
                    hovertext=f"{speaker}: {format_timecode_short(turn['start'])} - {format_timecode_short(turn['end'])}",
                    hoverinfo="text",
                ), row=3, col=1)
    else:
        fig.add_annotation(
            text="Speaker diarization not available",
            xref="x3", yref="y3",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color="#999"),
            row=3, col=1,
        )

    total_duration = segments[-1]["end"] if segments else 0
    fig.update_layout(
        title="Deposition Testimony Timeline",
        height=800,
        template="plotly_white",
        barmode="stack",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    # Set x-axes to time range
    for i in range(1, 4):
        fig.update_xaxes(range=[0, total_duration], row=i, col=1)
    fig.update_xaxes(title_text="Time (seconds)", row=3, col=1)

    fig.write_html(output_path, include_plotlyjs="cdn")
    log(f"Timeline written to: {output_path}")


# ---------------------------------------------------------------------------
# Output: summary
# ---------------------------------------------------------------------------

def write_summary(segments: list[dict], topics: list[dict], key_moments: list[dict],
                   duration: float, language: str, model_name: str,
                   speakers: list[str], total_pages: int, output_path: str) -> str:
    """Write human-readable deposition summary."""
    total_words = sum(len(seg["text"].split()) for seg in segments)

    lines = []
    lines.append("=" * 60)
    lines.append("DEPOSITION INDEX — SUMMARY")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Duration:          {format_timecode_short(duration)}")
    lines.append(f"Language:          {language}")
    lines.append(f"Whisper Model:     {model_name}")
    lines.append(f"Speakers:          {len(speakers)} ({', '.join(speakers) if speakers else 'N/A'})")
    lines.append(f"Word Count:        {total_words:,}")
    lines.append(f"Transcript Pages:  {total_pages} (page:line format)")
    lines.append(f"Segments:          {len(segments)}")
    lines.append(f"Topics Identified: {len(topics)}")
    lines.append(f"Key Moments:       {len(key_moments)}")
    lines.append("")

    # Key moments by type
    if key_moments:
        lines.append("Key Moments by Type:")
        lines.append("-" * 30)
        moment_counts = defaultdict(int)
        for m in key_moments:
            moment_counts[m["type"]] += 1
        for t, c in sorted(moment_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {t.replace('_', ' ').title():<20} {c:>5}")
        lines.append("")

    # Topics overview
    if topics:
        lines.append("Topics:")
        lines.append("-" * 30)
        for i, topic in enumerate(topics, 1):
            lines.append(f"  {i}. {topic['topic']}")
            lines.append(f"     {topic['start_timecode']} - {topic['end_timecode']} "
                         f"({topic['duration_seconds']:.0f}s)")
        lines.append("")

    # Speaker stats
    if speakers:
        lines.append("Speaker Statistics:")
        lines.append("-" * 30)
        speaker_words = defaultdict(int)
        speaker_segments = defaultdict(int)
        for seg in segments:
            s = seg.get("speaker") or "UNKNOWN"
            speaker_words[s] += len(seg["text"].split())
            speaker_segments[s] += 1
        for s in sorted(speaker_words.keys()):
            pct = (speaker_words[s] / total_words * 100) if total_words else 0
            lines.append(f"  {s:<15} {speaker_words[s]:>6} words ({pct:.1f}%)  "
                         f"{speaker_segments[s]} segments")
        lines.append("")

    text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    log(f"Summary written to: {output_path}")
    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Deposition Video Indexer")
    parser.add_argument("--input", required=True, help="Input audio/video file")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--model", default="auto",
                        help="Whisper model: tiny, base, small, medium, large (default: auto)")
    parser.add_argument("--language", default="auto",
                        help="Language code (e.g., en) or 'auto' for detection")
    parser.add_argument("--no-diarize", action="store_true",
                        help="Skip speaker diarization")
    parser.add_argument("--max-speakers", type=int, default=4,
                        help="Maximum speakers for diarization (default: 4)")
    args = parser.parse_args()

    input_path = args.input
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Validate input ---
    if not os.path.isfile(input_path):
        log(f"ERROR: File not found: {input_path}")
        print(json.dumps({"status": "error", "error": f"File not found: {input_path}"}))
        sys.exit(2)

    ext = Path(input_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        log(f"ERROR: Unsupported format: {ext}")
        print(json.dumps({"status": "error", "error": f"Unsupported format: {ext}"}))
        sys.exit(2)

    filename = Path(input_path).stem
    log(f"Processing: {Path(input_path).name}")

    # --- Extract/convert audio ---
    wav_path = extract_audio(input_path, str(output_dir))

    try:
        duration = get_audio_duration(wav_path)
        log(f"Duration: {format_timecode_short(duration)}")

        # --- Select model ---
        model_name = select_model(duration, args.model)
        log(f"Using Whisper model: {model_name}")

        # --- Transcribe ---
        transcription = transcribe_audio(wav_path, model_name,
                                          args.language if args.language != "auto" else None)
        segments = transcription["segments"]
        detected_language = transcription["language"]
        actual_duration = transcription["duration"]

        if not segments:
            log("ERROR: No speech detected in recording.")
            print(json.dumps({"status": "error", "error": "No speech detected in the recording."}))
            sys.exit(2)

        log(f"Transcription: {len(segments)} segments, language={detected_language}")

        # --- Speaker diarization ---
        speaker_turns = None
        if not args.no_diarize:
            speaker_turns = try_diarize(wav_path, max_speakers=args.max_speakers)
            if speaker_turns:
                segments = assign_speakers(segments, speaker_turns)

        speakers = sorted(set(seg.get("speaker") for seg in segments if seg.get("speaker")))

        # --- Build topic index ---
        log_progress("topic_indexing", 0, "Building topic index...")
        topics = build_topic_index(segments)
        log(f"Topics identified: {len(topics)}")

        # --- Detect key moments ---
        log_progress("key_moments", 0, "Detecting key moments...")
        key_moments = detect_key_moments(segments)
        log(f"Key moments detected: {len(key_moments)}")

        # --- Generate page:line transcript ---
        log_progress("writing_outputs", 0, "Generating page:line transcript...")
        page_line_text, total_pages = generate_page_line_transcript(segments)

        # --- Write all outputs ---
        log_progress("writing_outputs", 20, "Writing transcript files...")

        # transcript.txt
        transcript_path = str(output_dir / "transcript.txt")
        write_transcript(segments, transcript_path)
        log(f"Transcript written to: {transcript_path}")

        # page_line_transcript.txt
        page_line_path = str(output_dir / "page_line_transcript.txt")
        with open(page_line_path, "w", encoding="utf-8") as f:
            f.write(page_line_text)
        log(f"Page:line transcript written to: {page_line_path}")

        # topic_index.json
        topic_path = str(output_dir / "topic_index.json")
        with open(topic_path, "w", encoding="utf-8") as f:
            json.dump(topics, f, indent=2, ensure_ascii=False)
        log(f"Topic index written to: {topic_path}")

        # key_moments.json
        moments_path = str(output_dir / "key_moments.json")
        with open(moments_path, "w", encoding="utf-8") as f:
            json.dump(key_moments, f, indent=2, ensure_ascii=False)
        log(f"Key moments written to: {moments_path}")

        log_progress("writing_outputs", 60, "Generating timeline...")

        # testimony_timeline.html
        timeline_path = str(output_dir / "testimony_timeline.html")
        build_testimony_timeline(segments, topics, key_moments, speaker_turns, timeline_path)

        # deposition_summary.txt
        summary_path = str(output_dir / "deposition_summary.txt")
        write_summary(segments, topics, key_moments, actual_duration, detected_language,
                       model_name, speakers, total_pages, summary_path)

        log_progress("writing_outputs", 90, "Writing metadata...")

        # index_metadata.json
        total_words = sum(len(seg["text"].split()) for seg in segments)
        metadata = {
            "input_file": os.path.abspath(input_path),
            "duration_seconds": actual_duration,
            "duration_formatted": format_timecode_short(actual_duration),
            "language": detected_language,
            "language_probability": transcription.get("language_probability", 0),
            "model": model_name,
            "segments": len(segments),
            "word_count": total_words,
            "pages": total_pages,
            "speakers": speakers,
            "speaker_count": len(speakers),
            "diarization_used": speaker_turns is not None,
            "topics_count": len(topics),
            "key_moments_count": len(key_moments),
            "output_files": {
                "transcript": transcript_path,
                "page_line_transcript": page_line_path,
                "topic_index": topic_path,
                "key_moments": moments_path,
                "testimony_timeline": timeline_path,
                "deposition_summary": summary_path,
            },
        }

        metadata_path = str(output_dir / "index_metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        log(f"Metadata written to: {metadata_path}")

        log_progress("writing_outputs", 100, "All outputs written.")
    finally:
        # Always clean up temp WAV (potentially ~230MB for long depositions)
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
                log(f"Cleaned up temp audio: {wav_path}")
            except OSError:
                pass

    # --- JSON result to stdout ---
    result = {
        "status": "success",
        "duration": format_timecode_short(actual_duration),
        "duration_seconds": actual_duration,
        "language": detected_language,
        "model": model_name,
        "segments": len(segments),
        "word_count": total_words,
        "pages": total_pages,
        "speakers": speakers,
        "speaker_count": len(speakers),
        "diarization_used": speaker_turns is not None,
        "topics": len(topics),
        "key_moments": len(key_moments),
        "key_moments_by_type": dict(
            sorted(
                defaultdict(int, {m["type"]: 0 for m in key_moments}).items()
            )
        ),
        "output_dir": str(output_dir),
        "files": {
            "transcript": transcript_path,
            "page_line_transcript": page_line_path,
            "topic_index": topic_path,
            "key_moments": moments_path,
            "testimony_timeline": timeline_path,
            "deposition_summary": summary_path,
            "index_metadata": metadata_path,
        },
    }

    # Recount key moments properly
    moment_counts = defaultdict(int)
    for m in key_moments:
        moment_counts[m["type"]] += 1
    result["key_moments_by_type"] = dict(sorted(moment_counts.items(), key=lambda x: -x[1]))

    print(json.dumps(result, indent=2))
    log("\nDeposition indexing complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
