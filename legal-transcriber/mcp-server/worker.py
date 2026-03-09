#!/usr/bin/env python3
"""
Standalone transcription worker for the legal-transcriber plugin.

Runs as a detached subprocess launched by the MCP server. Does all heavy
work (model loading, transcription, diarization) and writes progress to
{work_dir}/status.json at each stage.

Usage:
    python3 worker.py <input_file> <work_dir> [options]

Options:
    --model MODEL        Whisper model (tiny|base|small|medium|large-v3|auto) [default: auto]
    --language LANG      Language code or "auto" [default: auto]
    --no-diarize         Skip speaker diarization
    --max-speakers N     Max speakers for diarization (0 = auto) [default: 0]
    --hf-token TOKEN     HuggingFace token override
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

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
# Status file management (atomic writes)
# ---------------------------------------------------------------------------
def write_status(work_dir: str, data: dict):
    """Write status.json atomically via temp file + rename."""
    status_path = os.path.join(work_dir, "status.json")
    tmp_fd, tmp_path = tempfile.mkstemp(dir=work_dir, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, status_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def update_status(work_dir: str, stage: str, progress: float, message: str,
                  started_at: str, **extra):
    """Helper to write a running status update."""
    data = {
        "status": "running",
        "progress": round(progress, 2),
        "stage": stage,
        "message": message,
        "started_at": started_at,
        "pid": os.getpid(),
        **extra,
    }
    write_status(work_dir, data)


def write_error(work_dir: str, error: str, error_type: str, started_at: str):
    """Write an error status."""
    write_status(work_dir, {
        "status": "error",
        "error": error,
        "error_type": error_type,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
    })


def write_completed(work_dir: str, result: dict, files_written: list,
                    started_at: str):
    """Write a completed status with results."""
    write_status(work_dir, {
        "status": "completed",
        "progress": 1.0,
        "stage": "done",
        "message": "Transcription complete",
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "result": result,
        "files_written": files_written,
    })


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _log(msg: str):
    """Log to stderr."""
    print(msg, file=sys.stderr, flush=True)


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
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(filepath)
        return len(audio) / 1000.0
    except Exception:
        pass

    if shutil.which("ffprobe"):
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries",
                 "format=duration", "-of", "csv=p=0", filepath],
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass

    return 0.0


def extract_audio_from_video(video_path: str, work_dir: str) -> str:
    """Extract audio track from video file using ffmpeg."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg is required for video files. "
            "Install with: brew install ffmpeg (macOS) or "
            "sudo apt install ffmpeg (Linux)"
        )

    output_path = os.path.join(work_dir, "extracted_audio.wav")
    _log(f"Extracting audio from video: {os.path.basename(video_path)}")

    result = subprocess.run(
        ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
         "-ar", "16000", "-ac", "1", "-y", output_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg extraction failed: {result.stderr}")

    _log(f"Audio extracted: {output_path}")
    return output_path


def select_model(explicit_model: str, duration_seconds: float) -> str:
    """Select Whisper model based on recording duration.

    For legal transcription, accuracy matters more than speed.
    Auto selection:
      - < 30 min: 'small' (good balance of speed and accuracy)
      - 30-60 min: 'medium' (better accuracy for longer recordings)
      - > 60 min: 'medium' (large-v3 is too slow on CPU for long recordings)
    """
    if explicit_model != "auto":
        if explicit_model not in MODEL_SIZES:
            _log(f"WARNING: Unknown model '{explicit_model}'. Using 'medium'.")
            return "medium"
        return explicit_model

    if duration_seconds <= 0:
        # Duration unknown — default to medium for legal accuracy
        _log("Duration unknown. Using 'medium' for best accuracy.")
        return "medium"
    elif duration_seconds < 1800:  # < 30 min
        _log(f"Short recording ({format_timestamp(duration_seconds)}). Using 'small'.")
        return "small"
    else:
        _log(f"Long recording ({format_timestamp(duration_seconds)}). Using 'medium'.")
        return "medium"


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------
def run_transcription(
    audio_path: str,
    model_name: str,
    language: str,
    work_dir: str,
    started_at: str,
) -> tuple[list[dict], dict]:
    """Transcribe audio using faster-whisper."""
    from faster_whisper import WhisperModel

    update_status(work_dir, "loading_model", 0.1,
                  f"Loading model '{model_name}' ({MODEL_SIZES.get(model_name, '?')})...",
                  started_at)

    _log(f"Loading model '{model_name}' (size: {MODEL_SIZES.get(model_name, '?')})...")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    lang_arg = language if language != "auto" else None
    _log(f"Transcribing: {os.path.basename(audio_path)}")

    update_status(work_dir, "transcribing", 0.2,
                  "Transcribing audio...", started_at)

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
            _log(f"  Processed {len(segments)} segments...")
            update_status(work_dir, "transcribing",
                          min(0.2 + len(segments) * 0.001, 0.6),
                          f"Processed {len(segments)} segments...",
                          started_at)

    elapsed = time.time() - start_time
    _log(f"Transcription complete: {len(segments)} segments in {elapsed:.1f}s")

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
    work_dir: str = None,
    started_at: str = None,
) -> list[dict]:
    """Run pyannote speaker diarization. Returns speaker turns."""
    from pyannote.audio import Pipeline as PyannotePipeline

    if work_dir and started_at:
        update_status(work_dir, "diarizing", 0.65,
                      "Running speaker diarization...", started_at)

    _log("Running speaker diarization...")
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
    _log(f"Diarization complete: {len(speakers)} speakers, "
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

    for s in stats.values():
        s["total_seconds"] = round(s["total_seconds"], 1)

    return stats


def write_outputs(segments: list[dict], metadata: dict, work_dir: str):
    """Write metadata.json, transcript.json, and transcript.txt."""
    os.makedirs(work_dir, exist_ok=True)

    meta_path = os.path.join(work_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

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

    _log(f"Outputs written to: {work_dir}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Legal Transcriber Worker")
    parser.add_argument("input_file", help="Path to audio/video file")
    parser.add_argument("work_dir", help="Output directory for work files")
    parser.add_argument("--model", default="auto",
                        help="Whisper model (tiny|base|small|medium|large-v3|auto)")
    parser.add_argument("--language", default="auto",
                        help="Language code or 'auto'")
    parser.add_argument("--no-diarize", action="store_true",
                        help="Skip speaker diarization")
    parser.add_argument("--max-speakers", type=int, default=0,
                        help="Max speakers for diarization (0 = auto)")
    parser.add_argument("--hf-token", default="",
                        help="HuggingFace token override")
    args = parser.parse_args()

    input_file = os.path.abspath(args.input_file)
    work_dir = os.path.abspath(args.work_dir)
    started_at = datetime.now(timezone.utc).isoformat()

    os.makedirs(work_dir, exist_ok=True)

    # Write initial status
    update_status(work_dir, "starting", 0.0, "Worker started", started_at)

    try:
        # --- Validate input ---
        if not os.path.isfile(input_file):
            write_error(work_dir, f"File not found: {input_file}",
                        "file_not_found", started_at)
            sys.exit(1)

        ext = Path(input_file).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            write_error(work_dir, f"Unsupported format '{ext}'",
                        "unsupported_format", started_at)
            sys.exit(1)

        # --- Extract audio from video if needed ---
        audio_path = input_file
        if is_video(input_file):
            update_status(work_dir, "extracting_audio", 0.05,
                          "Extracting audio from video...", started_at)
            audio_path = extract_audio_from_video(input_file, work_dir)

        # --- Get duration ---
        duration = get_audio_duration(audio_path)
        if duration > 0:
            _log(f"Audio duration: {format_timestamp(duration)} ({duration:.1f}s)")

        # --- Select model ---
        model_name = select_model(args.model, duration)
        _log(f"Using model: {model_name}")

        # --- Transcribe ---
        segments, info = run_transcription(
            audio_path, model_name, args.language, work_dir, started_at,
        )

        if not segments:
            _log("WARNING: No speech detected in the recording.")
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
            write_completed(work_dir, {
                "warning": "no_speech_detected",
                **metadata,
            }, ["metadata.json", "transcript.json", "transcript.txt"], started_at)
            return

        # --- Speaker diarization (optional) ---
        has_diarization = False
        pyannote_available = False
        try:
            import pyannote.audio  # noqa: F401
            pyannote_available = True
        except ImportError:
            pass

        if not args.no_diarize and pyannote_available:
            resolved_token = get_hf_token(args.hf_token if args.hf_token else None)
            if resolved_token:
                try:
                    turns = run_diarization(
                        audio_path, resolved_token,
                        max_speakers=args.max_speakers if args.max_speakers > 0 else None,
                        work_dir=work_dir, started_at=started_at,
                    )
                    segments = merge_transcript_with_diarization(segments, turns)
                    has_diarization = True
                except Exception as e:
                    _log(f"WARNING: Diarization failed: {e}")
                    _log("Proceeding without speaker labels.")
            else:
                _log("No HuggingFace token found. Skipping speaker diarization.")
        elif not args.no_diarize and not pyannote_available:
            _log("pyannote.audio not installed. Skipping speaker diarization.")

        # --- Compute stats ---
        update_status(work_dir, "writing_outputs", 0.9,
                      "Writing output files...", started_at)

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

        # --- Write final status ---
        write_completed(work_dir, metadata,
                        ["metadata.json", "transcript.json", "transcript.txt"],
                        started_at)

        _log("Worker finished successfully.")

    except Exception as e:
        _log(f"Worker error: {e}")
        write_error(work_dir, str(e), "transcription_failed", started_at)
        sys.exit(1)


if __name__ == "__main__":
    main()
