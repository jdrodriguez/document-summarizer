#!/usr/bin/env python3
"""Check and auto-install dependencies for the document-summarizer skill."""
import importlib
import subprocess
import shutil
import sys

PYTHON_DEPS = {
    "pdfplumber": "pdfplumber",
    "fitz": "PyMuPDF",
    "docx": "python-docx",
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
    print(f"Installing: {' '.join(packages)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"pip install failed: {result.stderr}", file=sys.stderr)
        return False
    return True

def main():
    installed_something = False

    missing_py = check_python_deps()
    missing_sys = check_system_deps()

    if missing_sys:
        for name, hint in missing_sys:
            print(f"Missing system tool: {name}")
            print(f"  Install with: {hint}")
        # Attempt auto-install on macOS (brew) and Linux (apt)
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

    if missing_py:
        if not install_python_packages(missing_py):
            sys.exit(2)
        installed_something = True
        # Verify installation
        still_missing = check_python_deps()
        if still_missing:
            print(f"Still missing after install: {', '.join(still_missing)}", file=sys.stderr)
            sys.exit(2)

    if installed_something:
        print("All dependencies installed successfully.")
        sys.exit(1)  # 1 = installed something
    else:
        print("All dependencies already satisfied.")
        sys.exit(0)  # 0 = already good

if __name__ == "__main__":
    main()
