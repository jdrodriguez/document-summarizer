# Document Summarizer

A Claude Code skill that takes large documents (PDF, DOCX, TXT, Markdown) or entire folders of mixed documents and produces a professional summary report in both Word (.docx) and PDF formats. It automatically splits documents into manageable chunks, coordinates multiple AI agents to summarize sections in parallel, and assembles everything into a single unified report with an executive summary, document structure outline, and section-by-section breakdowns.

## Prerequisites

You need four things installed on your machine before using this skill. Follow the instructions for your operating system.

### macOS users: Install Homebrew first

Most of the tools below can be installed on macOS using Homebrew, a package manager for macOS. If you don't already have it, open **Terminal** (search for "Terminal" in Spotlight) and paste this command:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the on-screen instructions. When it finishes, close and reopen Terminal before continuing.

You can verify Homebrew is installed by running:
```bash
brew --version
```

### 1. Node.js (v18 or newer)

Node.js runs the script that generates the final Word and PDF files.

**macOS**:
Download the macOS installer from https://nodejs.org (choose the LTS version). Open the `.pkg` file and follow the prompts.

Alternatively, if you use Homebrew: `brew install node`

**Windows**:
Download the Windows installer from https://nodejs.org (choose the LTS version). Run it and follow the prompts. Make sure "Add to PATH" is checked during installation.

**Linux (Ubuntu/Debian)**:
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Verify it works by opening a new terminal window and running:
```bash
node --version   # should print v18.x.x or higher
npm --version    # should print 9.x.x or higher
```

### 2. Python 3 (v3.9 or newer)

Python handles the document text extraction and chunking.

**macOS**:
Download the macOS installer from https://www.python.org/downloads/. Open the `.pkg` file and follow the prompts.

Alternatively, if you use Homebrew: `brew install python3`

**Windows**:
Download from https://www.python.org/downloads/. During installation, **check the box that says "Add Python to PATH"** -- this is critical.

**Linux (Ubuntu/Debian)**:
```bash
sudo apt-get install -y python3 python3-pip
```

Verify it works:
```bash
python3 --version   # should print 3.9.x or higher
```

### 3. Poppler (for PDF text extraction)

Poppler provides the `pdftotext` command used as a fallback for extracting text from PDFs. This is optional but recommended for best results with PDFs.

**macOS**:
If you have Homebrew: `brew install poppler`

If you don't have Homebrew, you can install Homebrew first with:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Then run `brew install poppler`.

Alternatively, the skill will still work without Poppler -- it uses PyMuPDF as the primary PDF extractor and only falls back to `pdftotext` when needed.

**Windows**:
Download from https://github.com/ossamamehmood/Poppler/releases. Extract the zip file, then add the `bin/` folder inside it to your system PATH.

**Linux (Ubuntu/Debian)**:
```bash
sudo apt-get install -y poppler-utils
```

### 4. Claude Code

Claude Code is the AI-powered command-line tool that runs this skill. Once you have Node.js installed, open a terminal and run:

```bash
npm install -g @anthropic-ai/claude-code
```

To use Claude Code you need one of the following:
- An **Anthropic API key** -- get one at https://console.anthropic.com, then set it:
  ```bash
  export ANTHROPIC_API_KEY=your-key-here
  ```
- A **Claude Max subscription** -- $100/month plan from Anthropic that includes Claude Code usage

Launch Claude Code for the first time to complete setup:
```bash
claude
```

It will walk you through authentication on first run.

## Installing the Skill

### Step 1: Download this repository

**Option A** -- Clone with git (if you have git installed):
```bash
git clone https://github.com/jdrodriguez/document-summarizer.git
cd document-summarizer
```

**Option B** -- Download the ZIP:
1. Go to https://github.com/jdrodriguez/document-summarizer
2. Click the green "Code" button, then "Download ZIP"
3. Unzip the downloaded file
4. Open a terminal and `cd` into the unzipped folder

### Step 2: Run the install script

```bash
chmod +x install.sh
./install.sh
```

This does three things:
1. Creates a symlink at `~/.claude/skills/document-summarizer` pointing to this folder -- this is how Claude Code discovers and loads the skill
2. Installs required Python packages: `pdfplumber`, `PyMuPDF`, `python-docx`, `tiktoken`
3. Installs required npm packages globally: `docx`, `pdfkit`

If the script reports any errors, see the Troubleshooting section below.

### Step 3: Verify the installation

Open Claude Code:
```bash
claude
```

Then type:
```
/document-summarizer
```

If Claude recognizes the command, you're all set.

### How the skill installation works

Claude Code looks for skills in `~/.claude/skills/`. The install script creates a symlink from `~/.claude/skills/document-summarizer` to wherever you downloaded this repository. This means:
- You can put the repo folder anywhere you like
- If you cloned with git, running `git pull` gives you updates immediately
- To uninstall, just delete the symlink: `rm ~/.claude/skills/document-summarizer`

## Usage

1. Open a terminal and launch Claude Code:
   ```bash
   claude
   ```

2. Ask it to summarize a document by providing the file path:
   ```
   Summarize /path/to/my-report.pdf
   ```

   Or point it at a folder of documents:
   ```
   Summarize everything in /path/to/contracts/
   ```

   Other ways to trigger the skill:
   ```
   Give me an executive summary of /path/to/document.docx
   What does /path/to/policy.pdf say?
   Analyze the reports in /path/to/quarterly-reports/
   ```

3. Sit back. For large documents, Claude will coordinate a team of agents that work in parallel. You'll see progress as each agent finishes its assigned sections.

## What You Get

After processing, you'll find these files **in the same folder as your original document**:

| File | Description |
|------|-------------|
| `{filename}_summary.docx` | Professional Word document with executive summary, TOC, section breakdowns, key findings |
| `{filename}_summary.pdf` | Same content as a PDF |
| `{filename}_summary_work/` | Working directory with intermediate files (see below) |

The `_summary_work/` folder contains:
- `metadata.json` -- document structure, chunk info, and token counts
- `chunks/` -- the individual text chunks extracted from your document (useful for reviewing what the AI saw)
- `summaries/` -- each agent's raw summary output before final assembly
- `final_summary.md` -- plain-text version of the final summary

For directory input, the output files are named `Summary_{foldername}.docx` and `.pdf`, and the work directory is `_summary_work/` inside the source folder.

## Supported File Types

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | Text-based PDFs. Scanned/image-only PDFs need OCR first. |
| Word | `.docx` | Modern Word format. Old `.doc` files are not supported. |
| Plain text | `.txt` | Any plain text file. |
| Markdown | `.md` | Markdown files. |

## Troubleshooting

### "command not found: node" or "command not found: python3"

Your PATH isn't set up correctly. Try closing and reopening your terminal. If that doesn't help:

**macOS/Linux**: Add this to your `~/.zshrc` or `~/.bashrc`:
```bash
export PATH="/usr/local/bin:$PATH"
```
Then run `source ~/.zshrc` (or `~/.bashrc`).

**Windows**: Reinstall Node.js/Python and make sure to check "Add to PATH" during installation.

### "Cannot find module 'docx'" or "Cannot find module 'pdfkit'"

The npm packages aren't installed globally. Run:
```bash
npm install -g docx pdfkit
```

If you still get the error, your Node.js global modules path may not be in NODE_PATH. Find it with:
```bash
npm root -g
```
Then set NODE_PATH before running Claude Code:
```bash
export NODE_PATH=$(npm root -g)
claude
```

Add the `export NODE_PATH` line to your `~/.zshrc` or `~/.bashrc` to make it permanent.

### "No module named 'tiktoken'" or other Python import errors

Run the dependency checker manually:
```bash
python3 ~/.claude/skills/document-summarizer/scripts/check_dependencies.py
```

Or install packages directly:
```bash
pip3 install pdfplumber pymupdf python-docx tiktoken
```

### "pdftotext: command not found"

This is optional. The skill uses PyMuPDF as its primary PDF extractor and only falls back to `pdftotext` when needed. To install it, see the Poppler section under Prerequisites.

### "Empty extraction" or very short summary

The PDF may be scanned (image-only) rather than text-based. This skill doesn't include OCR. You'll need to run the PDF through an OCR tool first (like Adobe Acrobat's "Recognize Text" feature or the open-source `ocrmypdf` tool).

### The Word file shows "This document contains fields that may refer to other files"

This is normal. The document includes a Table of Contents field. Click "No" to dismiss the dialog -- the TOC will display correctly once you update the fields in Word (right-click the TOC and select "Update Field").

### Uninstalling

To remove the skill from Claude Code:
```bash
rm ~/.claude/skills/document-summarizer
```

This only removes the symlink. Your downloaded repository stays intact.
