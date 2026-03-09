#!/usr/bin/env python3
"""
Audio/video transcription for the legal-transcriber plugin.

Transcribes audio using faster-whisper with optional speaker diarization
via pyannote-audio. All processing is 100% local -- no audio data leaves
the machine.

Usage:
    python3 transcribe_audio.py <input_file> <work_dir> [options]

Options:
    --model       Model name: tiny, base, small, medium, large-v3, auto (default: auto)
    --language    Language code (en, es, etc.) or auto (default: auto)
    --no-diarize  Disable speaker diarization
    --max-speakers  Max speakers for diarization (default: auto-detect)
    --hf-token    HuggingFace token (overrides env/file)
"""
import argparse
import json
import os
import subprocess
import shutil
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency imports with graceful fallback
# ---------------------------------------------------------------------------
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("ERROR: faster-whisper is required. Run: pip install faster-whisper",
          file=sys.stderr)
    sys.exit(2)

try:
    from pydub import AudioSegment
    from pydub.utils import mediainfo
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

PYANNOTE_AVAILABLE = False
try:
    from pyannote.audio import Pipeline as PyannotePipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".wma", ".aac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

MODEL_SIZES = {
    "tiny": "~75 MB",
    "base": "~141 MB",
    "small": "~466 MB",
    "medium": "~1.5 GB",
    "large-v3": "~2.9 GB",
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_hf_token(cli_token: str = None) -> str | None:
    """Resolve HuggingFace token from CLI arg, env vars, or token files."""
    if cli_token:
        return cli_token

    token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    if token:
        return token

    for path in [
        os.path.expanduser("~/.huggingface/token"),
        os.path.expanduser("~/.cache/huggingface/token"),
    ]:
        if os.path.exists(path):
            with open(path) as f:
                token = f.read().strip()
            if token:
                return token

    return None


def is_video(filepath: str) -> bool:
    """Check if file is a video format."""
    return Path(filepath).suffix.lower() in VIDEO_EXTENSIONS


def get_audio_duration(filepath: str) -> float:
    """Get audio duration in seconds. Returns 0.0 on failure."""
    # Try pydub first
    if PYDUB_AVAILABLE:
        try:
            audio = AudioSegment.from_file(filepath)
            return len(audio) / 1000.0
        except Exception:
            pass

    # Fallback to ffprobe
    if shutil.which("ffprobe"):
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries",
                 "format=duration", "-of", "csv=p=0", filepath],
                capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass

    return 0.0


def extract_audio_from_video(video_path: str, work_dir: str) -> str:
    """Extract audio track from video file using ffmpeg."""
    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg is required for video files.", file=sys.stderr)
        print("Install with: brew install ffmpeg (macOS) or "
              "sudo apt install ffmpeg (Linux)", file=sys.stderr)
        sys.exit(1)

    output_path = os.path.join(work_dir, "extracted_audio.wav")
    print(f"Extracting audio from video: {os.path.basename(video_path)}")

    result = subprocess.run(
        ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
         "-ar", "16000", "-ac", "1", "-y", output_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ffmpeg extraction failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"Audio extracted: {output_path}")
    return output_path


def select_model(explicit_model: str, duration_seconds: float) -> str:
    """Select Whisper model. 'auto' defaults to 'small'."""
    if explicit_model != "auto":
        if explicit_model not in MODEL_SIZES:
            print(f"WARNING: Unknown model '{explicit_model}'. Using 'small'.",
                  file=sys.stderr)
            return "small"
        return explicit_model
    return "small"


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------
def run_transcription(
    audio_path: str,
    model_name: str,
    language: str,
) -> tuple[list[dict], dict]:
    """
    Transcribe audio using faster-whisper.

    Returns (segments, info_dict) where each segment has:
        start, end, text, words
    """
    print(f"Loading model '{model_name}' (size: {MODEL_SIZES.get(model_name, '?')})...")
    print("(First run will download the model — this only happens once)")

    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    lang_arg = language if language != "auto" else None
    print(f"Transcribing: {os.path.basename(audio_path)}")
    print(f"Language: {'auto-detect' if lang_arg is None else lang_arg}")

    start_time = time.time()

    segments_gen, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        language=lang_arg,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    segments = []
    for seg in segments_gen:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
            "words": [
                {
                    "start": round(w.start, 2),
                    "end": round(w.end, 2),
                    "word": w.word,
                }
                for w in (seg.words or [])
            ],
        })
        if len(segments) % 50 == 0:
            print(f"  Processed {len(segments)} segments...")

    elapsed = time.time() - start_time
    print(f"Transcription complete: {len(segments)} segments in {elapsed:.1f}s")

    info_dict = {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "duration": round(info.duration, 2),
    }

    return segments, info_dict


# ---------------------------------------------------------------------------
# Speaker diarization
# ---------------------------------------------------------------------------
def run_diarization(
    audio_path: str,
    hf_token: str,
    max_speakers: int = None,
) -> list[dict]:
    """Run pyannote speaker diarization. Returns speaker turns."""
    print("Running speaker diarization...")
    print("(First run will download the diarization model — this only happens once)")

    start_time = time.time()

    pipeline = PyannotePipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )

    kwargs = {}
    if max_speakers and max_speakers > 0:
        kwargs["max_speakers"] = max_speakers

    diarization = pipeline(audio_path, **kwargs)

    turns = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append({
            "start": round(turn.start, 2),
            "end": round(turn.end, 2),
            "speaker": speaker,
        })

    elapsed = time.time() - start_time
    speakers = set(t["speaker"] for t in turns)
    print(f"Diarization complete: {len(speakers)} speakers, "
          f"{len(turns)} turns in {elapsed:.1f}s")

    return turns


def merge_transcript_with_diarization(
    segments: list[dict],
    turns: list[dict],
) -> list[dict]:
    """Assign speaker labels to transcript segments based on time overlap."""
    for seg in segments:
        best_speaker = "UNKNOWN"
        best_overlap = 0.0
        for turn in turns:
            overlap_start = max(seg["start"], turn["start"])
            overlap_end = min(seg["end"], turn["end"])
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn["speaker"]
        seg["speaker"] = best_speaker
    return segments


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------
def compute_speaker_stats(segments: list[dict]) -> dict:
    """Aggregate per-speaker metrics."""
    stats = {}
    for seg in segments:
        speaker = seg.get("speaker", "UNKNOWN")
        if speaker not in stats:
            stats[speaker] = {"total_seconds": 0.0, "segment_count": 0, "word_count": 0}
        stats[speaker]["total_seconds"] += seg["end"] - seg["start"]
        stats[speaker]["segment_count"] += 1
        stats[speaker]["word_count"] += len(seg["text"].split())

    # Round values
    for s in stats.values():
        s["total_seconds"] = round(s["total_seconds"], 1)

    return stats


def write_outputs(
    segments: list[dict],
    metadata: dict,
    work_dir: str,
):
    """Write metadata.json, transcript.json, and transcript.txt."""
    os.makedirs(work_dir, exist_ok=True)

    # --- metadata.json ---
    meta_path = os.path.join(work_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # --- transcript.json ---
    transcript_data = {
        "segments": [
            {
                "id": i + 1,
                "start": seg["start"],
                "end": seg["end"],
                "speaker": seg.get("speaker"),
                "text": seg["text"],
                "words": seg.get("words", []),
            }
            for i, seg in enumerate(segments)
        ]
    }
    transcript_json_path = os.path.join(work_dir, "transcript.json")
    with open(transcript_json_path, "w") as f:
        json.dump(transcript_data, f, indent=2)

    # --- transcript.txt ---
    transcript_txt_path = os.path.join(work_dir, "transcript.txt")
    with open(transcript_txt_path, "w") as f:
        for seg in segments:
            ts = format_timestamp(seg["start"])
            te = format_timestamp(seg["end"])
            speaker = seg.get("speaker")
            if speaker:
                f.write(f"[{ts} - {te}] {speaker}: {seg['text']}\n")
            else:
                f.write(f"[{ts} - {te}] {seg['text']}\n")

    print(f"Outputs written to: {work_dir}")
    print(f"  metadata.json  ({os.path.getsize(meta_path)} bytes)")
    print(f"  transcript.json ({os.path.getsize(transcript_json_path)} bytes)")
    print(f"  transcript.txt  ({os.path.getsize(transcript_txt_path)} bytes)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio/video recordings for legal use."
    )
    parser.add_argument("input_file", help="Path to audio or video file")
    parser.add_argument("work_dir", help="Directory for output files")
    parser.add_argument("--model", default="auto",
                        help="Model: tiny, base, small, medium, large-v3, auto (default: auto)")
    parser.add_argument("--language", default="auto",
                        help="Language code (en, es, etc.) or auto (default: auto)")
    parser.add_argument("--no-diarize", action="store_true",
                        help="Disable speaker diarization")
    parser.add_argument("--max-speakers", type=int, default=0,
                        help="Max speakers for diarization (0 = auto)")
    parser.add_argument("--hf-token", default=None,
                        help="HuggingFace token (overrides env/file)")
    args = parser.parse_args()

    input_file = os.path.abspath(args.input_file)
    work_dir = os.path.abspath(args.work_dir)

    # --- Validate input ---
    if not os.path.isfile(input_file):
        print(f"ERROR: File not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    ext = Path(input_file).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        print(f"ERROR: Unsupported format '{ext}'", file=sys.stderr)
        print(f"Supported audio: {', '.join(sorted(AUDIO_EXTENSIONS))}", file=sys.stderr)
        print(f"Supported video: {', '.join(sorted(VIDEO_EXTENSIONS))}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(work_dir, exist_ok=True)

    # --- Extract audio from video if needed ---
    audio_path = input_file
    if is_video(input_file):
        audio_path = extract_audio_from_video(input_file, work_dir)

    # --- Get duration ---
    duration = get_audio_duration(audio_path)
    if duration > 0:
        print(f"Audio duration: {format_timestamp(duration)} ({duration:.1f}s)")
    else:
        print("WARNING: Could not determine audio duration.")

    # --- Select model ---
    model_name = select_model(args.model, duration)
    print(f"Using model: {model_name}")

    # --- Transcribe ---
    segments, info = run_transcription(audio_path, model_name, args.language)

    if not segments:
        print("WARNING: No speech detected in the recording.")
        # Still write empty outputs
        metadata = {
            "source_file": input_file,
            "filename": os.path.basename(input_file),
            "duration_seconds": duration,
            "duration_formatted": format_timestamp(duration),
            "model_used": model_name,
            "language_detected": info.get("language", "unknown"),
            "language_probability": info.get("language_probability", 0.0),
            "has_diarization": False,
            "speaker_count": 0,
            "segment_count": 0,
            "word_count": 0,
            "speakers": {},
        }
        write_outputs([], metadata, work_dir)
        result = {"status": "success", "warning": "no_speech_detected", **metadata}
        print(json.dumps(result))
        return

    # --- Speaker diarization (optional) ---
    has_diarization = False
    if not args.no_diarize and PYANNOTE_AVAILABLE:
        hf_token = get_hf_token(args.hf_token)
        if hf_token:
            try:
                turns = run_diarization(
                    audio_path, hf_token,
                    max_speakers=args.max_speakers if args.max_speakers > 0 else None,
                )
                segments = merge_transcript_with_diarization(segments, turns)
                has_diarization = True
            except Exception as e:
                print(f"WARNING: Diarization failed: {e}", file=sys.stderr)
                print("Proceeding without speaker labels.")
        else:
            print("No HuggingFace token found. Skipping speaker diarization.")
    elif not args.no_diarize and not PYANNOTE_AVAILABLE:
        print("pyannote.audio not installed. Skipping speaker diarization.")

    # --- Compute stats ---
    word_count = sum(len(seg["text"].split()) for seg in segments)
    speaker_stats = compute_speaker_stats(segments) if has_diarization else {}

    # --- Build metadata ---
    metadata = {
        "source_file": input_file,
        "filename": os.path.basename(input_file),
        "duration_seconds": duration if duration > 0 else info.get("duration", 0),
        "duration_formatted": format_timestamp(
            duration if duration > 0 else info.get("duration", 0)
        ),
        "model_used": model_name,
        "language_detected": info.get("language", "unknown"),
        "language_probability": info.get("language_probability", 0.0),
        "has_diarization": has_diarization,
        "speaker_count": len(speaker_stats),
        "segment_count": len(segments),
        "word_count": word_count,
        "speakers": speaker_stats,
    }

    # --- Write outputs ---
    write_outputs(segments, metadata, work_dir)

    # --- Print JSON status to stdout (matches chunk_document.py pattern) ---
    result = {"status": "success", **metadata}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
