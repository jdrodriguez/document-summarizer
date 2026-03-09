#!/usr/bin/env python3
"""
Check and auto-install dependencies for the legal-transcriber skill.

Uses importlib.util.find_spec() to probe packages WITHOUT importing them,
so heavy libraries (CTranslate2, PyTorch) are never loaded during the check.

Exit codes:
    0 = all dependencies already satisfied
    1 = dependencies were installed (re-run may be needed)
    2 = installation failed
"""
import importlib.util
import os
import subprocess
import shutil
import sys

PYTHON_DEPS = {
    "faster_whisper": "faster-whisper",
    "pydub": "pydub",
    "audioop": "audioop-lts",
}

OPTIONAL_DEPS = {
    "pyannote.audio": "pyannote.audio",
}


def is_package_available(module_name: str) -> bool:
    """Check if a package is importable WITHOUT actually importing it."""
    return importlib.util.find_spec(module_name) is not None


def check_python_deps():
    """Return list of missing required Python packages."""
    missing = []
    for module, package in PYTHON_DEPS.items():
        if not is_package_available(module):
            missing.append(package)
    return missing


def check_system_deps():
    """Return list of missing system tools with install hints."""
    missing = []
    if not shutil.which("ffmpeg"):
        if sys.platform == "darwin":
            hint = "brew install ffmpeg"
        elif sys.platform == "win32":
            hint = "download from https://ffmpeg.org/download.html and add to PATH"
        else:
            hint = "sudo apt-get install -y ffmpeg"
        missing.append(("ffmpeg", hint))
    return missing


def install_python_packages(packages):
    """Install Python packages via pip."""
    cmd = [sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages"] + packages
    print(f"Installing: {' '.join(packages)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Retry without --break-system-packages for older Python versions
        cmd_fallback = [sys.executable, "-m", "pip", "install", "--quiet"] + packages
        result = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"pip install failed: {result.stderr}", file=sys.stderr)
            return False
    return True


def main():
    installed_something = False

    # Check Python is available
    if not shutil.which("python3") and not shutil.which("python"):
        print("ERROR: Python 3 is required but not found.", file=sys.stderr)
        sys.exit(2)

    # System deps (ffmpeg — optional, needed for video/some audio)
    missing_sys = check_system_deps()
    if missing_sys:
        for name, hint in missing_sys:
            print(f"Missing system tool: {name}")
            print(f"  Install with: {hint}")
        # Try auto-install on supported platforms
        for name, hint in missing_sys:
            if sys.platform == "darwin" and shutil.which("brew"):
                print(f"Attempting: {hint}")
                result = subprocess.run(hint.split(), capture_output=True, text=True)
            elif sys.platform == "linux" and shutil.which("apt-get"):
                print(f"Attempting: {hint}")
                result = subprocess.run(hint.split(), capture_output=True, text=True)
            else:
                print(f"Cannot auto-install {name}. Please install manually: {hint}")
                print("(Optional — only needed for video files and some audio formats.)")
                continue
            if result.returncode != 0:
                print(f"Auto-install of {name} failed. Install manually: {hint}",
                      file=sys.stderr)
            else:
                installed_something = True

    # Required Python deps
    missing_py = check_python_deps()
    if missing_py:
        if not install_python_packages(missing_py):
            sys.exit(2)
        installed_something = True
        # Verify installation
        still_missing = check_python_deps()
        if still_missing:
            print(f"Still missing after install: {', '.join(still_missing)}",
                  file=sys.stderr)
            sys.exit(2)

    # Optional Python deps (info only — don't auto-install, pyannote is ~1.5GB)
    missing_optional = []
    for module, package in OPTIONAL_DEPS.items():
        if not is_package_available(module):
            missing_optional.append(package)
    if missing_optional:
        print(f"\nOptional (not installed): {', '.join(missing_optional)}")
        print("  Speaker diarization requires pyannote.audio + PyTorch (~1.5 GB).")
        print("  To install manually: pip install pyannote.audio")
        print("  Transcription works fine without it — just no speaker labels.")

    # HuggingFace token info
    hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    if not hf_token:
        for token_path in [
            os.path.expanduser("~/.huggingface/token"),
            os.path.expanduser("~/.cache/huggingface/token"),
        ]:
            if os.path.exists(token_path):
                hf_token = True
                break
    if not hf_token:
        print("")
        print("Note: No HuggingFace token found.")
        print("  Speaker diarization requires a free token from:")
        print("  https://huggingface.co/settings/tokens")
        print("  Transcription works fine without it — just no speaker labels.")

    if installed_something:
        print("\nDependencies installed successfully.")
        sys.exit(1)  # 1 = installed something
    else:
        print("\nAll dependencies already satisfied.")
        sys.exit(0)  # 0 = already good


if __name__ == "__main__":
    main()
