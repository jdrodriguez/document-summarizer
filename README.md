# Document Summarizer

A Claude Code plugin that takes large documents (PDF, DOCX, TXT, Markdown) or entire folders of mixed documents and produces a professional summary report as a Word (.docx) file. It automatically splits documents into manageable chunks, coordinates multiple AI agents to summarize sections in parallel, and assembles everything into a single unified report with an executive summary, document structure outline, and section-by-section breakdowns.

Works with both **Claude Code** (CLI) and **Claude Desktop / Cowork**.

## Prerequisites

### Claude Code (CLI)

You need these installed on your machine:

1. **Node.js** (v18+) — for generating the final Word document
2. **Python 3** (v3.9+) — for document text extraction and chunking
3. **Poppler** (optional) — provides `pdftotext` as a fallback PDF extractor

The plugin will auto-install Python packages (`pdfplumber`, `PyMuPDF`, `python-docx`) and npm packages (`docx`) on first run.

#### macOS (with Homebrew)

```bash
brew install node python3 poppler
```

If you don't have Homebrew, install it first:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### Windows

- **Node.js**: Download from https://nodejs.org (LTS version). Check "Add to PATH" during install.
- **Python 3**: Download from https://www.python.org/downloads/. Check "Add Python to PATH" during install.
- **Poppler** (optional): Download from https://github.com/ossamamehmood/Poppler/releases and add the `bin/` folder to your system PATH.

#### Linux (Ubuntu/Debian)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs python3 python3-pip poppler-utils
```

Verify your setup:
```bash
node --version     # v18+ required
python3 --version  # 3.9+ required
```

### Claude Desktop / Cowork

No prerequisites needed. Cowork's VM has Python and Node.js pre-installed. All dependencies are auto-installed on first run.

## Installing the Plugin

### Option A: Claude Code CLI

Install directly from within Claude Code:

```
/install-plugin https://github.com/jdrodriguez/document-summarizer
```

Or clone and use locally:

```bash
git clone https://github.com/jdrodriguez/document-summarizer.git
claude --plugin-dir /path/to/document-summarizer/document-summarizer
```

### Option B: Claude Desktop / Cowork

1. Download [`document-summarizer.zip`](document-summarizer.zip) from this repository
2. Open Claude Desktop and start a Cowork session
3. Drag and drop the `.zip` file into the chat
4. Claude will install the plugin automatically

> **Note**: The standard marketplace install may not work in Cowork due to a known filesystem issue. The zip upload method is the reliable workaround.

### Verify the installation

Type this in Claude Code or Cowork:
```
/document-summarizer:summarize
```

If Claude recognizes the command, you're all set.

## Usage

Ask Claude to summarize a document by providing the file path:

```
Summarize /path/to/my-report.pdf
```

Or point it at a folder of documents:

```
Summarize everything in /path/to/contracts/
```

Other ways to trigger the plugin:

```
Give me an executive summary of /path/to/document.docx
What does /path/to/policy.pdf say?
Analyze the reports in /path/to/quarterly-reports/
```

You can also invoke it directly:

```
/document-summarizer:summarize /path/to/file.pdf
```

For large documents, Claude coordinates a team of agents that work in parallel. You'll see progress as each agent finishes its assigned sections.

## What You Get

After processing, you'll find these files **in the same folder as your original document**:

| File | Description |
|------|-------------|
| `{filename}_summary.docx` | Professional Word document with executive summary, TOC, section breakdowns, key findings |
| `{filename}_summary_work/` | Working directory with intermediate files (chunks, agent summaries, metadata) |

The `_summary_work/` folder contains:
- `metadata.json` — document structure, chunk info, and token counts
- `chunks/` — the individual text chunks extracted from your document
- `summaries/` — each agent's raw summary output before final assembly
- `final_summary.md` — plain-text Markdown version of the summary

For directory input, the output is named `Summary_{foldername}.docx` and the work directory is `_summary_work/` inside the source folder.

> **Need a PDF?** Open the `.docx` in Word or Google Docs and export to PDF.

## Supported File Types

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | Text-based PDFs. Scanned/image-only PDFs need OCR first. |
| Word | `.docx` | Modern Word format. Old `.doc` files are not supported. |
| Plain text | `.txt` | Any plain text file. |
| Markdown | `.md` | Markdown files. |

## Troubleshooting

### "command not found: node" or "command not found: python3"

Your PATH isn't set up correctly. Close and reopen your terminal. If that doesn't help:

**macOS/Linux**: Add this to your `~/.zshrc` or `~/.bashrc`:
```bash
export PATH="/usr/local/bin:$PATH"
```
Then run `source ~/.zshrc` (or `~/.bashrc`).

**Windows**: Reinstall Node.js/Python and make sure to check "Add to PATH" during installation.

### "Cannot find module 'docx'"

The npm package isn't installed. The plugin auto-installs it, but you can also run manually:
```bash
npm install -g docx
```

If the error persists, your Node.js global modules path may not be in NODE_PATH:
```bash
export NODE_PATH=$(npm root -g)
```
Add that line to your `~/.zshrc` or `~/.bashrc` to make it permanent.

### Python import errors

The plugin auto-installs Python dependencies. To install manually:
```bash
pip3 install pdfplumber pymupdf python-docx
```

### "Empty extraction" or very short summary

The PDF may be scanned (image-only) rather than text-based. This plugin doesn't include OCR. Run the PDF through an OCR tool first (like Adobe Acrobat's "Recognize Text" or the open-source `ocrmypdf` tool).

### The Word file shows "This document contains fields that may refer to other files"

This is normal. The document includes a Table of Contents field. Click "No" to dismiss the dialog. The TOC displays correctly once you update the fields in Word (right-click the TOC and select "Update Field").

### Uninstalling

If installed via plugin system:
```
/plugin uninstall document-summarizer
```

If installed manually:
```bash
rm -rf ~/.claude/skills/document-summarizer
```
