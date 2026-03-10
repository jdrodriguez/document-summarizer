#!/usr/bin/env python3
"""Audio/video transcription for the legal-toolkit plugin.

Uses faster-whisper with optional pyannote diarization. All local processing.
Writes progress to {work_dir}/status.json for polling by CLI skill / MCP server.
"""
import argparse, json, os, signal, shutil, subprocess, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

# --- Constants (no heavy imports at module level — lazy-loaded in functions) ---
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".wma", ".aac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
MODEL_SIZES = {"tiny": "~75 MB", "base": "~141 MB", "small": "~466 MB",
               "medium": "~1.5 GB", "large-v3": "~2.9 GB"}


def _log(msg: str):
    print(msg, file=sys.stderr, flush=True)

# --- Atomic status file management ---

def write_status(work_dir: str, data: dict):
    """Write status.json atomically via tempfile + os.replace()."""
    tmp_fd, tmp_path = tempfile.mkstemp(dir=work_dir, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, os.path.join(work_dir, "status.json"))
    except Exception:
        try: os.unlink(tmp_path)
        except OSError: pass
        raise

def update_status(work_dir, stage, progress, message, started_at, **extra):
    _log(f"[{stage}] {message}")
    write_status(work_dir, {"status": "running", "progress": round(progress, 2),
        "stage": stage, "message": message, "started_at": started_at,
        "pid": os.getpid(), **extra})

def write_error(work_dir, error, error_type, started_at):
    _log(f"ERROR [{error_type}]: {error}")
    now = datetime.now(timezone.utc).isoformat()
    write_status(work_dir, {"status": "error", "progress": 0.0, "stage": "error",
        "message": error, "started_at": started_at, "completed_at": now,
        "pid": os.getpid(), "result": {}, "files_written": [],
        "error": error, "error_type": error_type})

def write_completed(work_dir, result, files_written, started_at):
    _log("Transcription complete.")
    now = datetime.now(timezone.utc).isoformat()
    write_status(work_dir, {"status": "completed", "progress": 1.0, "stage": "done",
        "message": "Transcription complete", "started_at": started_at,
        "completed_at": now, "pid": os.getpid(), "result": result,
        "files_written": files_written, "error": "", "error_type": ""})

# --- Utilities ---

def format_timestamp(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_hf_token(cli_token: str = None) -> str | None:
    """Resolve HuggingFace token from CLI arg, env vars, or token files."""
    if cli_token:
        return cli_token
    token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    if token:
        return token
    for p in ["~/.huggingface/token", "~/.cache/huggingface/token"]:
        full = os.path.expanduser(p)
        if os.path.exists(full):
            with open(full) as f:
                t = f.read().strip()
            if t:
                return t
    return None

def get_audio_duration(filepath: str) -> float:
    """Get audio duration in seconds via pydub or ffprobe."""
    try:
        from pydub import AudioSegment
        return len(AudioSegment.from_file(filepath)) / 1000.0
    except Exception:
        pass
    if shutil.which("ffprobe"):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries",
                 "format=duration", "-of", "csv=p=0", filepath],
                capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return float(r.stdout.strip())
        except Exception:
            pass
    return 0.0

def extract_audio_from_video(video_path: str, work_dir: str) -> str:
    """Extract audio track from video file using ffmpeg."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg required for video. Install: brew install ffmpeg")
    out = os.path.join(work_dir, "extracted_audio.wav")
    r = subprocess.run(
        ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
         "-ar", "16000", "-ac", "1", "-y", out],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg extraction failed: {r.stderr}")
    return out

def select_model(explicit: str, duration: float) -> str:
    """Auto: small for <30 min, medium for 30+ min or unknown duration."""
    if explicit != "auto":
        if explicit not in MODEL_SIZES:
            _log(f"WARNING: Unknown model '{explicit}'. Falling back to 'small'.")
            return "small"
        return explicit
    if duration <= 0:
        _log("Duration unknown. Defaulting to 'medium'.")
        return "medium"
    if duration < 1800:
        _log(f"Short recording ({format_timestamp(duration)}). Using 'small'.")
        return "small"
    _log(f"Long recording ({format_timestamp(duration)}). Using 'medium'.")
    return "medium"

# --- Transcription (lazy import of faster_whisper) ---
def run_transcription(
    audio_path: str, model_name: str, language: str,
    work_dir: str, started_at: str,
) -> tuple[list[dict], dict]:
    """Transcribe audio using faster-whisper (lazy import)."""
    from faster_whisper import WhisperModel

    update_status(work_dir, "loading_model", 0.10,
                  f"Loading model '{model_name}' ({MODEL_SIZES.get(model_name, '?')})...",
                  started_at)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    lang_arg = language if language != "auto" else None
    update_status(work_dir, "transcribing", 0.20,
                  f"Transcribing ({os.path.basename(audio_path)})...", started_at)

    start_time = time.time()
    segments_gen, info = model.transcribe(
        audio_path, word_timestamps=True, language=lang_arg,
        vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
    )

    segments = []
    for seg in segments_gen:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
            "words": [
                {"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word}
                for w in (seg.words or [])
            ],
        })
        if len(segments) % 50 == 0:
            progress = min(0.20 + len(segments) * 0.001, 0.60)
            update_status(work_dir, "transcribing", progress,
                          f"Processed {len(segments)} segments...", started_at)

    elapsed = time.time() - start_time
    _log(f"Transcription done: {len(segments)} segments in {elapsed:.1f}s")

    return segments, {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "duration": round(info.duration, 2),
    }


# --- Speaker diarization (lazy import of pyannote) ---

def run_diarization(audio_path: str, hf_token: str, max_speakers: int = None,
                    work_dir: str = None, started_at: str = None) -> list[dict]:
    """Run pyannote speaker diarization. Returns speaker turns."""
    from pyannote.audio import Pipeline as PyannotePipeline
    if work_dir and started_at:
        update_status(work_dir, "diarizing", 0.65, "Running speaker diarization...", started_at)
    t0 = time.time()
    pipe = PyannotePipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=hf_token)
    kw = {"max_speakers": max_speakers} if max_speakers and max_speakers > 0 else {}
    result = pipe(audio_path, **kw)
    # pyannote v4.x returns DiarizeOutput; v3.x returns Annotation directly
    annotation = getattr(result, "speaker_diarization", result)
    turns = [{"start": round(t.start, 2), "end": round(t.end, 2), "speaker": s}
             for t, _, s in annotation.itertracks(yield_label=True)]
    spk = {t["speaker"] for t in turns}
    _log(f"Diarization done: {len(spk)} speakers, {len(turns)} turns in {time.time()-t0:.1f}s")
    return turns

def merge_diarization(segments: list[dict], turns: list[dict]) -> list[dict]:
    """Assign speaker labels to transcript segments based on time overlap."""
    for seg in segments:
        best, best_ov = "UNKNOWN", 0.0
        for t in turns:
            ov = max(0.0, min(seg["end"], t["end"]) - max(seg["start"], t["start"]))
            if ov > best_ov:
                best_ov, best = ov, t["speaker"]
        seg["speaker"] = best
    return segments

# --- Output writing ---

def compute_speaker_stats(segments: list[dict]) -> dict:
    stats = {}
    for seg in segments:
        sp = seg.get("speaker", "UNKNOWN")
        if sp not in stats:
            stats[sp] = {"total_seconds": 0.0, "segment_count": 0, "word_count": 0}
        stats[sp]["total_seconds"] += seg["end"] - seg["start"]
        stats[sp]["segment_count"] += 1
        stats[sp]["word_count"] += len(seg["text"].split())
    for v in stats.values():
        v["total_seconds"] = round(v["total_seconds"], 1)
    return stats

def write_outputs(segments: list[dict], metadata: dict, work_dir: str) -> list[str]:
    """Write metadata.json, transcript.json, and transcript.txt."""
    os.makedirs(work_dir, exist_ok=True)
    with open(os.path.join(work_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    with open(os.path.join(work_dir, "transcript.json"), "w") as f:
        json.dump({"segments": [
            {"id": i+1, "start": s["start"], "end": s["end"],
             "speaker": s.get("speaker"), "text": s["text"],
             "words": s.get("words", [])} for i, s in enumerate(segments)
        ]}, f, indent=2)
    with open(os.path.join(work_dir, "transcript.txt"), "w") as f:
        for s in segments:
            ts, te, sp = format_timestamp(s["start"]), format_timestamp(s["end"]), s.get("speaker")
            f.write(f"[{ts} - {te}] {sp}: {s['text']}\n" if sp else f"[{ts} - {te}] {s['text']}\n")
    _log(f"Outputs written to: {work_dir}")
    return ["metadata.json", "transcript.json", "transcript.txt"]

# --- SIGTERM handler ---
_WORK_DIR = _STARTED_AT = None

def _sigterm_handler(signum, frame):
    if _WORK_DIR and _STARTED_AT:
        write_error(_WORK_DIR, "Process cancelled by signal", "cancelled", _STARTED_AT)
    sys.exit(130)

# --- Main pipeline ---

def main():
    global _WORK_DIR, _STARTED_AT
    ap = argparse.ArgumentParser(description="Transcribe audio/video for legal use.")
    ap.add_argument("input_file", help="Path to audio or video file")
    ap.add_argument("work_dir", help="Working directory for output files")
    ap.add_argument("--model", default="auto", help="tiny|base|small|medium|large-v3|auto")
    ap.add_argument("--language", default="auto", help="Language code or auto")
    ap.add_argument("--no-diarize", action="store_true", help="Skip diarization")
    ap.add_argument("--max-speakers", type=int, default=0, help="Max speakers (0=auto)")
    ap.add_argument("--hf-token", default=None, help="HuggingFace token override")
    args = ap.parse_args()

    input_file = os.path.abspath(args.input_file)
    work_dir = os.path.abspath(args.work_dir)
    started_at = datetime.now(timezone.utc).isoformat()
    _WORK_DIR, _STARTED_AT = work_dir, started_at
    signal.signal(signal.SIGTERM, _sigterm_handler)

    os.makedirs(work_dir, exist_ok=True)

    # 1. Initial status
    update_status(work_dir, "starting", 0.0, "Worker started", started_at)

    try:
        # Validate input
        if not os.path.isfile(input_file):
            write_error(work_dir, f"File not found: {input_file}",
                        "file_not_found", started_at)
            sys.exit(1)

        ext = Path(input_file).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            write_error(work_dir, f"Unsupported format '{ext}'", "unsupported_format", started_at)
            sys.exit(1)

        # 2. Extract audio from video if needed
        audio_path = input_file
        if ext in VIDEO_EXTENSIONS:
            update_status(work_dir, "extracting_audio", 0.05,
                          "Extracting audio from video...", started_at)
            audio_path = extract_audio_from_video(input_file, work_dir)

        # Get duration and select model
        duration = get_audio_duration(audio_path)
        if duration > 0:
            _log(f"Audio duration: {format_timestamp(duration)} ({duration:.1f}s)")

        # 3. Load model + 4. Transcribe (status updates inside run_transcription)
        model_name = select_model(args.model, duration)
        segments, info = run_transcription(
            audio_path, model_name, args.language, work_dir, started_at,
        )

        # Handle empty transcript
        if not segments:
            _log("WARNING: No speech detected in the recording.")
            metadata = _build_metadata(input_file, duration, model_name, info,
                                       False, 0, {})
            files = write_outputs([], metadata, work_dir)
            write_completed(work_dir, {"warning": "no_speech_detected", **metadata},
                            files, started_at)
            print(json.dumps({"status": "success", "warning": "no_speech_detected",
                              **metadata}))
            return

        # 5. Speaker diarization (optional)
        has_diarization = False
        pyannote_available = False
        try:
            import pyannote.audio  # noqa: F401
            pyannote_available = True
        except ImportError:
            pass

        if not args.no_diarize and pyannote_available:
            resolved_token = get_hf_token(args.hf_token)
            if resolved_token:
                try:
                    turns = run_diarization(
                        audio_path, resolved_token,
                        max_speakers=args.max_speakers if args.max_speakers > 0 else None,
                        work_dir=work_dir, started_at=started_at,
                    )
                    segments = merge_diarization(segments, turns)
                    has_diarization = True
                except Exception as e:
                    _log(f"WARNING: Diarization failed: {e}. Proceeding without speaker labels.")
            else:
                _log("No HuggingFace token found. Skipping speaker diarization.")
        elif not args.no_diarize and not pyannote_available:
            _log("pyannote.audio not installed. Skipping speaker diarization.")

        # 6. Write outputs
        update_status(work_dir, "writing_outputs", 0.90,
                      "Writing output files...", started_at)

        word_count = sum(len(seg["text"].split()) for seg in segments)
        speaker_stats = compute_speaker_stats(segments) if has_diarization else {}
        metadata = _build_metadata(input_file, duration, model_name, info,
                                   has_diarization, word_count, speaker_stats,
                                   len(segments))
        files = write_outputs(segments, metadata, work_dir)

        # 7. Completed
        write_completed(work_dir, metadata, files, started_at)
        print(json.dumps({"status": "success", **metadata}))

    except Exception as e:
        _log(f"Fatal error: {e}")
        write_error(work_dir, str(e), "transcription_failed", started_at)
        sys.exit(1)

def _build_metadata(input_file, duration, model_name, info,
                    has_diarization, word_count, speaker_stats, segment_count=0):
    d = duration if duration > 0 else info.get("duration", 0)
    return {
        "source_file": input_file, "filename": os.path.basename(input_file),
        "duration_seconds": d, "duration_formatted": format_timestamp(d),
        "model_used": model_name,
        "language_detected": info.get("language", "unknown"),
        "language_probability": info.get("language_probability", 0.0),
        "has_diarization": has_diarization, "speaker_count": len(speaker_stats),
        "segment_count": segment_count, "word_count": word_count,
        "speakers": speaker_stats,
    }

if __name__ == "__main__":
    main()
