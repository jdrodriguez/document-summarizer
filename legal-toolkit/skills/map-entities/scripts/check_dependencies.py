#!/usr/bin/env python3
"""Check and auto-install dependencies for the legal-entity-mapper skill."""
import importlib.util
import subprocess
import shutil
import sys

PYTHON_DEPS = {
    "spacy": "spacy",
    "pandas": "pandas",
    "networkx": "networkx",
    "plotly": "plotly",
    "xlsxwriter": "XlsxWriter",
    "pdfplumber": "pdfplumber",
    "docx": "python-docx",
}

# npm packages needed for output generation (.docx)
NPM_DEPS = ["docx"]

# spaCy model required
SPACY_MODEL = "en_core_web_sm"

# Optional deps
OPTIONAL_DEPS = {
    "fitz": "PyMuPDF",
}


def is_package_available(module_name: str) -> bool:
    """Check if a package is importable WITHOUT actually importing it."""
    return importlib.util.find_spec(module_name) is not None


def check_python_deps():
    missing = []
    for module, package in PYTHON_DEPS.items():
        if not is_package_available(module):
            missing.append(package)
    return missing


def check_spacy_model():
    """Check if the spaCy model is installed."""
    try:
        import spacy
        spacy.load(SPACY_MODEL)
        return True
    except (ImportError, OSError):
        return False


def install_spacy_model():
    """Download the spaCy model."""
    print(f"Downloading spaCy model: {SPACY_MODEL}")
    result = subprocess.run(
        [sys.executable, "-m", "spacy", "download", SPACY_MODEL],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"spaCy model download failed: {result.stderr}", file=sys.stderr)
        return False
    return True


def check_npm_deps():
    """Check which npm packages are missing."""
    if not shutil.which("npm"):
        return NPM_DEPS  # can't check, assume all missing
    missing = []
    for pkg in NPM_DEPS:
        result = subprocess.run(
            ["npm", "list", "-g", pkg],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            result2 = subprocess.run(
                ["npm", "list", pkg],
                capture_output=True, text=True
            )
            if result2.returncode != 0:
                missing.append(pkg)
    return missing


def install_python_packages(packages):
    cmd = [sys.executable, "-m", "pip", "install", "--quiet"] + packages
    print(f"Installing Python packages: {' '.join(packages)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"pip install failed: {result.stderr}", file=sys.stderr)
        return False
    return True


def install_npm_packages(packages):
    if not shutil.which("npm"):
        print("npm not found. Cannot install Node.js packages.", file=sys.stderr)
        print("Install Node.js from https://nodejs.org/ then re-run.", file=sys.stderr)
        return False
    cmd = ["npm", "install", "-g"] + packages
    print(f"Installing npm packages: {' '.join(packages)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"npm install failed: {result.stderr}", file=sys.stderr)
        return False
    return True


def main():
    installed_something = False

    # Check prerequisites
    if not shutil.which("python3") and not shutil.which("python"):
        print("ERROR: Python 3 is required but not found.", file=sys.stderr)
        print("Install from https://python.org/downloads/", file=sys.stderr)
        sys.exit(2)

    if not shutil.which("node"):
        print("WARNING: Node.js not found. Output generation (.docx) will not work.")
        print("Install from https://nodejs.org/")

    # Python deps (required)
    missing_py = check_python_deps()
    if missing_py:
        if not install_python_packages(missing_py):
            sys.exit(2)
        installed_something = True
        still_missing = check_python_deps()
        if still_missing:
            print(f"Still missing after install: {', '.join(still_missing)}", file=sys.stderr)
            sys.exit(2)

    # spaCy model (required)
    if not check_spacy_model():
        if not install_spacy_model():
            print("ERROR: Could not install spaCy model.", file=sys.stderr)
            print("Try manually: python3 -m spacy download en_core_web_sm", file=sys.stderr)
            sys.exit(2)
        installed_something = True

    # npm deps (required for output generation)
    missing_npm = check_npm_deps()
    if missing_npm:
        if install_npm_packages(missing_npm):
            installed_something = True
        else:
            print("WARNING: npm packages not installed. Output generation may fail.")

    # Optional Python deps (best-effort)
    missing_optional = []
    for module, package in OPTIONAL_DEPS.items():
        if not is_package_available(module):
            missing_optional.append(package)
    if missing_optional:
        try:
            install_python_packages(missing_optional)
            installed_something = True
        except Exception:
            print(f"Optional: {', '.join(missing_optional)} unavailable (this is OK)")

    if installed_something:
        print("All dependencies installed successfully.")
        sys.exit(1)  # 1 = installed something
    else:
        print("All dependencies already satisfied.")
        sys.exit(0)  # 0 = already good


if __name__ == "__main__":
    main()
