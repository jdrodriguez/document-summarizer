#!/usr/bin/env python3
"""Check and auto-install dependencies for the document-summarizer skill."""
import importlib
import subprocess
import shutil
import sys

PYTHON_DEPS = {
    "pdfplumber": "pdfplumber",
    "docx": "python-docx",
}

# npm packages needed for output generation (.docx)
NPM_DEPS = ["docx"]

# Optional deps — the chunker handles all of these being missing:
# - PyMuPDF: faster PDF extraction, falls back to pdfplumber
# - tiktoken: accurate token counting, falls back to len(text)//4
OPTIONAL_DEPS = {
    "fitz": "PyMuPDF",
    "tiktoken": "tiktoken",
}


def check_python_deps():
    missing = []
    for module, package in PYTHON_DEPS.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(package)
    return missing


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
            # Also check local
            result2 = subprocess.run(
                ["npm", "list", pkg],
                capture_output=True, text=True
            )
            if result2.returncode != 0:
                missing.append(pkg)
    return missing


def check_system_deps():
    missing = []
    if not shutil.which("pdftotext"):
        if sys.platform == "darwin":
            hint = "brew install poppler"
        elif sys.platform == "win32":
            hint = "download from https://github.com/ossamamehmood/Poppler/releases"
        else:
            hint = "sudo apt-get install -y poppler-utils"
        missing.append(("poppler", hint))
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

    # System deps (optional)
    missing_sys = check_system_deps()
    if missing_sys:
        for name, hint in missing_sys:
            print(f"Missing system tool: {name}")
            print(f"  Install with: {hint}")
        for name, hint in missing_sys:
            if sys.platform == "darwin" and shutil.which("brew"):
                print(f"Attempting: {hint}")
                result = subprocess.run(hint.split(), capture_output=True, text=True)
            elif sys.platform == "linux" and shutil.which("apt-get"):
                print(f"Attempting: {hint}")
                result = subprocess.run(hint.split(), capture_output=True, text=True)
            else:
                print(f"Cannot auto-install {name}. Please install manually: {hint}")
                print("(This is optional -- the skill will still work for most PDFs without it.)")
                continue
            if result.returncode != 0:
                print(f"Auto-install of {name} failed. Install manually: {hint}", file=sys.stderr)
                print("(This is optional -- the skill will still work for most PDFs without it.)")
            else:
                installed_something = True

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
        try:
            importlib.import_module(module)
        except ImportError:
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
