#!/usr/bin/env python3
"""
Check and auto-install dependencies for the legal-chronology skill.

Uses importlib.util.find_spec() to probe packages WITHOUT importing them,
so heavy libraries (spaCy, pandas) are never loaded during the check.

Exit codes:
    0 = all dependencies already satisfied
    1 = dependencies were installed (re-run may be needed)
    2 = installation failed
"""
import importlib.util
import subprocess
import shutil
import sys


PYTHON_DEPS = {
    "spacy": "spacy",
    "pdfplumber": "pdfplumber",
    "docx": "python-docx",
    "pandas": "pandas",
    "plotly": "plotly",
    "xlsxwriter": "XlsxWriter",
    "dateutil": "python-dateutil",
}

SPACY_MODEL = "en_core_web_sm"


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


def check_spacy_model():
    """Check if the spaCy model is downloaded."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import spacy; spacy.load('{SPACY_MODEL}')"],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


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


def download_spacy_model():
    """Download spaCy language model."""
    print(f"Downloading spaCy model: {SPACY_MODEL} (~12 MB)...")
    cmd = [sys.executable, "-m", "spacy", "download", SPACY_MODEL, "--quiet"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Try without --quiet flag
        cmd_fallback = [sys.executable, "-m", "spacy", "download", SPACY_MODEL]
        result = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Failed to download spaCy model: {result.stderr}", file=sys.stderr)
            return False
    return True


def main():
    installed_something = False

    # Check Python is available
    if not shutil.which("python3") and not shutil.which("python"):
        print("ERROR: Python 3 is required but not found.", file=sys.stderr)
        sys.exit(2)

    if not shutil.which("node"):
        print("WARNING: Node.js not found. Output generation (.docx) will not work.")
        print("  Install from https://nodejs.org/")

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

    # spaCy model
    if is_package_available("spacy"):
        if not check_spacy_model():
            print(f"spaCy model '{SPACY_MODEL}' not found.")
            if not download_spacy_model():
                print(f"Failed to download spaCy model. Try manually:", file=sys.stderr)
                print(f"  python3 -m spacy download {SPACY_MODEL}", file=sys.stderr)
                sys.exit(2)
            installed_something = True
            # Verify
            if not check_spacy_model():
                print(f"spaCy model still not available after download.", file=sys.stderr)
                sys.exit(2)
            print(f"spaCy model '{SPACY_MODEL}' downloaded successfully.")
        else:
            print(f"spaCy model '{SPACY_MODEL}' already available.")
    else:
        print("spaCy not available — cannot check model.", file=sys.stderr)
        sys.exit(2)

    if installed_something:
        print("\nDependencies installed successfully.")
        sys.exit(1)  # 1 = installed something
    else:
        print("\nAll dependencies already satisfied.")
        sys.exit(0)  # 0 = already good


if __name__ == "__main__":
    main()
