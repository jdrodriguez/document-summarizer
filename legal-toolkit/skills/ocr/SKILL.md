---
name: ocr
description: "Extract text from scanned PDFs and images using OCR. Uses PaddleOCR (primary, highest accuracy) with pytesseract fallback. Includes image preprocessing (deskewing, contrast enhancement, noise reduction), confidence scoring, and multi-language support. Use when: (1) a user has scanned PDFs or images that need text extraction, (2) a user says 'OCR this document', 'extract text from this scan', 'read this scanned PDF', or 'process this image', (3) document-summarizer reports empty extraction and suggests OCR, (4) a user has a directory of scanned legal documents to batch-process, (5) a user needs to make scanned documents searchable."
---

# Legal OCR Engine

Extract text from scanned PDFs and images using high-accuracy OCR with confidence scoring.

**Supported formats**: `.pdf` (scanned), `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`
**Input modes**: single file OR a directory of scanned documents

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path. If not, ask: "Please provide the path to the scanned PDF or image file you want to OCR."
2. Determine if the path is a file or directory:
   - **File**: verify it exists and has a supported extension (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`)
   - **Directory**: verify it exists; the script will find all supported files inside it
3. If a directory, tell the user which files were found before proceeding.
4. Ask the user if they have a language preference (default: English). PaddleOCR supports 80+ languages.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).
- **Important**: PaddleOCR + PaddlePaddle is ~738MB on first install. Warn the user this may take a few minutes.

### Step 3: Run OCR Processing

Determine the output directory:
- **Single file**: `OUTPUT_DIR="{parent_dir}/{filename_without_ext}_ocr_output"`
- **Directory**: `OUTPUT_DIR="{directory_path}/_ocr_output"`

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/ocr_process.py" \
  --input "<file_or_directory_path>" \
  --output-dir "$OUTPUT_DIR" \
  --engine paddleocr \
  --language en \
  --dpi 300
```

The script prints JSON to stdout with the processing results. Progress messages go to stderr.

**Engine options**:
- `paddleocr` (default): Highest accuracy, best for legal documents
- `tesseract`: Lighter weight fallback, requires tesseract system package

### Step 4: Present Results

Read the script's JSON output. Present to the user:

1. **Documents processed**: count and filenames
2. **Per-document results**:
   - Pages processed
   - Average confidence score (flag anything below 0.85 as potentially unreliable)
   - Any warnings (low confidence pages, skipped pages)
3. **Overall statistics**: total pages, average confidence, processing time

Read `$OUTPUT_DIR/extraction_report.txt` and present the key findings.

If any pages have confidence below 0.70, warn the user:
> "Pages X, Y, Z had low OCR confidence. The extracted text may contain errors. Consider re-scanning these pages at higher resolution."

### Step 5: Offer Next Steps

Present these options to the user:

1. **Summarize the extracted text**: "Would you like me to summarize the extracted content? I can pipe it to `/legal-toolkit:doc-summary`."
2. **Generate a searchable PDF**: "I can create a searchable PDF with the OCR text layer embedded."
3. **Generate a Word document**: "I can create a .docx report with the extracted text, organized by page."
4. **Review specific pages**: "Would you like to review the extracted text for specific pages?"

### Step 6: Generate Output Report (if requested)

If the user wants a .docx report, use the npm `docx` package to generate a Word document containing:

- **Title**: "OCR Extraction Report: {filename}"
- **Metadata**: Source file, pages processed, OCR engine, average confidence
- **Per-page content**: Page number heading, extracted text, confidence score
- **Flagged sections**: Pages with low confidence highlighted

Output file: `{OUTPUT_DIR}/{original_filename}_ocr_report.docx`

## Error Handling

- **Path not found**: Ask user to verify the path
- **Unsupported format**: Supported types are `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`
- **Empty directory**: No supported files found -- ask user to check the folder
- **PaddleOCR not available**: Fall back to tesseract. If neither available, report to user.
- **Very low confidence (<0.5)**: Document may be too degraded. Suggest re-scanning or manual review.
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
