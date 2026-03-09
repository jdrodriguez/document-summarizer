#!/usr/bin/env python3
"""
MCP server for the legal-transcriber plugin.

Thin async server that validates inputs and launches a detached worker
subprocess for heavy transcription work. Provides polling via
check_transcription_status so the MCP client never blocks.

Transport: stdio (launched by Claude Code plugin system)

Usage (standalone test):
    python3 server.py
"""
import importlib.metadata
import importlib.util
import json
import os
import signal
import shutil
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP("legal-transcriber")

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

# Path to worker.py (same directory as this file)
WORKER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _log(msg: str):
    """Log to stderr so it doesn't interfere with MCP stdio protocol."""
    print(msg, file=sys.stderr, flush=True)


def _get_model_cache_path(model_name: str) -> str:
    """Get the HuggingFace cache path for a faster-whisper model."""
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    return os.path.join(cache_dir, f"models--Systran--faster-whisper-{model_name}")


def _is_model_cached(model_name: str) -> bool:
    """Check if a Whisper model is already downloaded."""
    cache_path = _get_model_cache_path(model_name)
    snapshots = os.path.join(cache_path, "snapshots")
    return os.path.isdir(snapshots)


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


def _read_status(work_dir: str) -> dict | None:
    """Read status.json from work_dir. Returns None if not found."""
    status_path = os.path.join(work_dir, "status.json")
    if not os.path.isfile(status_path):
        return None
    try:
        with open(status_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _find_python() -> str:
    """Find the Python interpreter to use for the worker subprocess.

    Prefers the venv Python in the same directory as this script,
    falls back to sys.executable.
    """
    server_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(server_dir, ".venv", "bin", "python3")
    if os.path.isfile(venv_python):
        return venv_python
    venv_python2 = os.path.join(server_dir, ".venv", "bin", "python")
    if os.path.isfile(venv_python2):
        return venv_python2
    return sys.executable


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------
@mcp.tool()
async def resolve_path(file_path: str) -> str:
    """Resolve a file path to an absolute path on the host machine.

    Use this BEFORE calling transcribe_audio when running in Cowork,
    because Cowork VM paths differ from host macOS paths.

    Tries the path as-is, then common macOS expansions:
      - ~ expansion
      - /Users/{username}/Desktop/...
      - /Users/{username}/Downloads/...
      - /Users/{username}/Documents/...
      - /Users/{username}/{path}

    Args:
        file_path: The file path to resolve (may be a VM path like /user/folder/file.mp4).

    Returns:
        JSON with the resolved absolute path on the host, or an error if not found.
    """
    import getpass

    candidates = []

    # 1. Try as-is
    expanded = os.path.expanduser(file_path)
    candidates.append(expanded)

    # 2. If path starts with /user/ or /home/, try mapping to macOS home
    username = getpass.getuser()
    home = os.path.expanduser("~")

    for prefix in ["/user/", "/home/", f"/home/{username}/"]:
        if file_path.startswith(prefix):
            relative = file_path[len(prefix):]
            # Try directly under home
            candidates.append(os.path.join(home, relative))
            # Try under common folders
            for folder in ["Downloads", "Desktop", "Documents"]:
                candidates.append(os.path.join(home, folder, relative))

    # 3. If it's just a filename or relative, try common locations
    basename = os.path.basename(file_path)
    if basename == file_path or not file_path.startswith("/"):
        for folder in ["Downloads", "Desktop", "Documents"]:
            candidates.append(os.path.join(home, folder, basename))

    # 4. Try stripping first path component and searching common dirs
    parts = file_path.strip("/").split("/")
    if len(parts) >= 2:
        # e.g. /user/ytvideo/file.mp4 → try ~/Downloads/ytvideo/file.mp4
        sub_path = "/".join(parts[1:])  # skip first component
        candidates.append(os.path.join(home, sub_path))
        for folder in ["Downloads", "Desktop", "Documents"]:
            candidates.append(os.path.join(home, folder, sub_path))

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in candidates:
        c = os.path.abspath(c)
        if c not in seen:
            seen.add(c)
            unique.append(c)

    # Find the first that exists
    for candidate in unique:
        if os.path.isfile(candidate):
            return json.dumps({
                "status": "found",
                "resolved_path": candidate,
                "message": f"File found at: {candidate}",
            })

    return json.dumps({
        "status": "not_found",
        "original_path": file_path,
        "tried": unique[:10],  # Show first 10 candidates
        "message": (
            f"Could not find '{file_path}' on the host machine. "
            f"Tried {len(unique)} locations. "
            f"Please provide the full macOS path (e.g. /Users/{username}/Downloads/file.mp4)."
        ),
    })


@mcp.tool()
async def transcribe_audio(
    input_file: str,
    work_dir: str,
    model: str = "auto",
    language: str = "auto",
    no_diarize: bool = False,
    max_speakers: int = 0,
    hf_token: str = "",
) -> str:
    """Start transcription of an audio or video file as a background job.

    Returns immediately with a job_id. Use check_transcription_status(job_id)
    to poll for progress and results.

    All processing is 100% local -- no audio data leaves the machine.
    Supports: .wav, .mp3, .m4a, .flac, .ogg, .wma, .aac, .mp4, .mov, .avi, .mkv, .webm

    Args:
        input_file: Absolute path to the audio or video file.
        work_dir: Absolute path to the output directory for work files.
        model: Whisper model name (tiny, base, small, medium, large-v3, auto). Default: auto.
        language: Language code (en, es, fr, etc.) or auto for detection. Default: auto.
        no_diarize: Set True to skip speaker diarization. Default: False.
        max_speakers: Maximum speakers for diarization (0 = auto-detect). Default: 0.
        hf_token: HuggingFace token override for diarization models. Default: reads from env.

    Returns:
        JSON string with job_id and status. Poll check_transcription_status(job_id) for results.
    """
    try:
        input_file = os.path.abspath(input_file)
        work_dir = os.path.abspath(work_dir)

        # --- Quick validation (no heavy imports) ---
        if not os.path.isfile(input_file):
            return json.dumps({
                "status": "error",
                "error": f"File not found: {input_file}",
                "error_type": "file_not_found",
            })

        ext = Path(input_file).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return json.dumps({
                "status": "error",
                "error": f"Unsupported format '{ext}'",
                "error_type": "unsupported_format",
                "supported_audio": sorted(AUDIO_EXTENSIONS),
                "supported_video": sorted(VIDEO_EXTENSIONS),
            })

        if not os.path.isfile(WORKER_SCRIPT):
            return json.dumps({
                "status": "error",
                "error": f"Worker script not found: {WORKER_SCRIPT}",
                "error_type": "internal_error",
            })

        os.makedirs(work_dir, exist_ok=True)

        # --- Build worker command ---
        python_bin = _find_python()
        cmd = [python_bin, WORKER_SCRIPT, input_file, work_dir]
        cmd.extend(["--model", model])
        cmd.extend(["--language", language])
        if no_diarize:
            cmd.append("--no-diarize")
        if max_speakers > 0:
            cmd.extend(["--max-speakers", str(max_speakers)])
        if hf_token:
            cmd.extend(["--hf-token", hf_token])

        # --- Launch detached subprocess ---
        log_stdout = os.path.join(work_dir, "worker_stdout.log")
        log_stderr = os.path.join(work_dir, "worker_stderr.log")

        with open(log_stdout, "w") as f_out, open(log_stderr, "w") as f_err:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=f_out,
                stderr=f_err,
                start_new_session=True,
            )

        _log(f"Worker launched: PID={proc.pid}, work_dir={work_dir}")

        return json.dumps({
            "status": "started",
            "job_id": work_dir,
            "pid": proc.pid,
            "message": (
                f"Transcription started (PID {proc.pid}). "
                f"Poll check_transcription_status(job_id='{work_dir}') "
                f"every 10 seconds for progress."
            ),
        })

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": "launch_failed",
        })


@mcp.tool()
async def check_transcription_status(job_id: str) -> str:
    """Check the status of a running transcription job.

    Args:
        job_id: The job_id returned by transcribe_audio (this is the work_dir path).

    Returns:
        JSON string with current status, progress, and results if complete.
    """
    try:
        work_dir = os.path.abspath(job_id)

        if not os.path.isdir(work_dir):
            return json.dumps({
                "status": "error",
                "error": f"Job directory not found: {work_dir}",
                "error_type": "job_not_found",
            })

        status = _read_status(work_dir)

        if status is None:
            return json.dumps({
                "status": "pending",
                "message": "Worker has not written status yet. It may still be starting up.",
                "job_id": work_dir,
            })

        # If status says running, verify the worker PID is still alive
        if status.get("status") == "running":
            pid = status.get("pid")
            if pid and not _is_pid_alive(pid):
                # Worker died without writing final status
                return json.dumps({
                    "status": "error",
                    "error": f"Worker process (PID {pid}) died unexpectedly. Check {work_dir}/worker_stderr.log for details.",
                    "error_type": "worker_crashed",
                    "job_id": work_dir,
                })

        # Return status as-is (includes progress, stage, result, etc.)
        status["job_id"] = work_dir
        return json.dumps(status)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": "status_check_failed",
        })


@mcp.tool()
async def cancel_transcription(job_id: str) -> str:
    """Cancel a running transcription job.

    Args:
        job_id: The job_id returned by transcribe_audio (this is the work_dir path).

    Returns:
        JSON string with cancellation result.
    """
    try:
        work_dir = os.path.abspath(job_id)

        if not os.path.isdir(work_dir):
            return json.dumps({
                "status": "error",
                "error": f"Job directory not found: {work_dir}",
                "error_type": "job_not_found",
            })

        status = _read_status(work_dir)

        if status is None:
            return json.dumps({
                "status": "error",
                "error": "No status file found. Worker may not have started.",
                "error_type": "no_status",
            })

        if status.get("status") in ("completed", "error"):
            return json.dumps({
                "status": "already_finished",
                "message": f"Job already has status: {status.get('status')}",
            })

        pid = status.get("pid")
        if not pid:
            return json.dumps({
                "status": "error",
                "error": "No PID found in status file.",
                "error_type": "no_pid",
            })

        if not _is_pid_alive(pid):
            return json.dumps({
                "status": "already_finished",
                "message": f"Worker process (PID {pid}) is no longer running.",
            })

        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)

        return json.dumps({
            "status": "cancelled",
            "message": f"Sent SIGTERM to worker PID {pid}.",
            "job_id": work_dir,
        })

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": "cancel_failed",
        })


@mcp.tool()
async def prepare_model(model: str = "small") -> str:
    """Check if a Whisper model is cached and ready for transcription.

    Call this BEFORE transcribe_audio to ensure the model is ready.
    Returns immediately — only checks the filesystem cache.

    If the model is not cached, returns instructions to download it.

    Args:
        model: Model name (tiny, base, small, medium, large-v3). Default: small.

    Returns:
        JSON string with model readiness status.
    """
    try:
        if model not in MODEL_SIZES:
            return json.dumps({
                "status": "error",
                "error": f"Unknown model: {model}. Available: {', '.join(MODEL_SIZES.keys())}",
            })

        if _is_model_cached(model):
            return json.dumps({
                "status": "ready",
                "model": model,
                "size": MODEL_SIZES[model],
                "cached": True,
                "message": f"Model '{model}' is already cached and ready to use.",
            })

        # Model not cached — don't import heavy libraries in the server.
        # Instead, return not_cached so the caller knows.
        # The worker subprocess will handle download if needed.
        return json.dumps({
            "status": "not_cached",
            "model": model,
            "size": MODEL_SIZES[model],
            "cached": False,
            "message": (
                f"Model '{model}' ({MODEL_SIZES[model]}) is not cached. "
                f"It will be downloaded automatically when transcription starts. "
                f"First run may take a few extra minutes."
            ),
        })

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": "model_check_failed",
        })


@mcp.tool()
async def check_dependencies() -> str:
    """Check availability of all dependencies for the legal transcriber.

    Returns a JSON report of which packages are available, versions,
    whether speaker diarization is supported, and which models are cached.

    NOTE: Uses importlib to probe packages WITHOUT importing them,
    so heavy libraries (CTranslate2, PyTorch) are never loaded into
    the MCP server process.
    """
    result = {}

    # faster-whisper (check without importing — avoids loading CTranslate2)
    if importlib.util.find_spec("faster_whisper") is not None:
        try:
            ver = importlib.metadata.version("faster-whisper")
        except importlib.metadata.PackageNotFoundError:
            ver = "unknown"
        result["faster_whisper"] = {"available": True, "version": ver}
    else:
        result["faster_whisper"] = {
            "available": False,
            "install_hint": "pip install faster-whisper",
        }

    # pydub (check without importing)
    if importlib.util.find_spec("pydub") is not None:
        try:
            ver = importlib.metadata.version("pydub")
        except importlib.metadata.PackageNotFoundError:
            ver = "unknown"
        result["pydub"] = {"available": True, "version": ver}
    else:
        result["pydub"] = {
            "available": False,
            "install_hint": "pip install pydub",
        }

    # pyannote (optional — check without importing to avoid loading PyTorch)
    # Note: find_spec raises ModuleNotFoundError for dotted names when
    # the parent package is not installed, so we must catch that.
    try:
        pyannote_available = importlib.util.find_spec("pyannote.audio") is not None
    except (ModuleNotFoundError, ValueError):
        pyannote_available = False

    if pyannote_available:
        try:
            ver = importlib.metadata.version("pyannote-audio")
        except importlib.metadata.PackageNotFoundError:
            ver = "unknown"
        result["pyannote"] = {"available": True, "version": ver}
    else:
        result["pyannote"] = {
            "available": False,
            "note": "Optional. Transcription works without it — just no speaker labels.",
        }

    # ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    result["ffmpeg"] = {
        "available": ffmpeg_path is not None,
        "path": ffmpeg_path or "",
    }

    # ffprobe
    ffprobe_path = shutil.which("ffprobe")
    result["ffprobe"] = {
        "available": ffprobe_path is not None,
        "path": ffprobe_path or "",
    }

    # HuggingFace token
    result["hf_token_found"] = get_hf_token() is not None

    # Model cache status (filesystem check only — no imports)
    result["models_cached"] = {
        name: _is_model_cached(name) for name in MODEL_SIZES
    }

    # Summary
    core_ok = (
        result["faster_whisper"]["available"]
        and result["pydub"]["available"]
    )
    diarization_ok = (
        result.get("pyannote", {}).get("available", False)
        and result["hf_token_found"]
    )

    if core_ok and diarization_ok:
        summary = "All dependencies OK. Speaker diarization: available."
    elif core_ok:
        summary = "Core dependencies OK. Speaker diarization: unavailable"
        if not result.get("pyannote", {}).get("available", False):
            summary += " (pyannote.audio not installed)."
        elif not result["hf_token_found"]:
            summary += " (no HuggingFace token found)."
    else:
        missing = []
        if not result["faster_whisper"]["available"]:
            missing.append("faster-whisper")
        if not result["pydub"]["available"]:
            missing.append("pydub")
        summary = f"Missing core dependencies: {', '.join(missing)}. Run install.sh first."

    result["status"] = "ok" if core_ok else "missing_dependencies"
    result["summary"] = summary

    return json.dumps(result)


@mcp.tool()
async def create_document(
    work_dir: str,
    output_path: str,
    executive_summary: str = "",
    key_topics: str = "[]",
    action_items: str = "[]",
    notable_quotes: str = "[]",
) -> str:
    """Generate a professional .docx transcript document.

    Call this AFTER transcription is complete and analysis is done.
    Reads transcript.txt and metadata.json from work_dir, combines with
    the provided analysis, and produces a formatted Word document.

    Args:
        work_dir: Path to the transcript work directory (contains transcript.txt, metadata.json).
        output_path: Full path for the output .docx file.
        executive_summary: 2-3 paragraph summary of the transcript content.
        key_topics: JSON array of key topic strings, e.g. '["Topic 1", "Topic 2"]'.
        action_items: JSON array of action item strings, e.g. '["Do X", "Do Y"]'.
        notable_quotes: JSON array of notable quote strings.

    Returns:
        JSON with status and the output file path.
    """
    try:
        work_dir = os.path.abspath(work_dir)
        output_path = os.path.abspath(output_path)

        if not os.path.isdir(work_dir):
            return json.dumps({
                "status": "error",
                "error": f"Work directory not found: {work_dir}",
            })

        transcript_path = os.path.join(work_dir, "transcript.txt")
        if not os.path.isfile(transcript_path):
            return json.dumps({
                "status": "error",
                "error": f"Transcript file not found: {transcript_path}",
            })

        # Parse analysis arrays from JSON strings
        def safe_json_list(s):
            try:
                val = json.loads(s)
                return val if isinstance(val, list) else []
            except (json.JSONDecodeError, TypeError):
                return []

        analysis = {
            "executive_summary": executive_summary,
            "key_topics": safe_json_list(key_topics),
            "action_items": safe_json_list(action_items),
            "notable_quotes": safe_json_list(notable_quotes),
        }

        # Build the analysis JSON file for the subprocess
        analysis_path = os.path.join(work_dir, "analysis.json")
        with open(analysis_path, "w") as f:
            json.dump(analysis, f, indent=2)

        # Run create_document.py as subprocess (avoids loading python-docx in server)
        create_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "create_document.py"
        )

        if not os.path.isfile(create_script):
            return json.dumps({
                "status": "error",
                "error": f"Document creation script not found: {create_script}",
            })

        python_bin = _find_python()
        cmd = [python_bin, create_script, work_dir, output_path, "--analysis", analysis_path]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            return json.dumps({
                "status": "error",
                "error": result.stderr.strip() or "Document creation failed",
                "error_type": "document_creation_failed",
            })

        # Parse stdout for the result
        try:
            output = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            output = {"status": "ok", "output_path": output_path}

        return json.dumps({
            "status": "ok",
            "output_path": output.get("output_path", output_path),
            "message": f"Document created: {output_path}",
        })

    except subprocess.TimeoutExpired:
        return json.dumps({
            "status": "error",
            "error": "Document creation timed out after 60 seconds.",
            "error_type": "timeout",
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "error_type": "document_creation_failed",
        })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
