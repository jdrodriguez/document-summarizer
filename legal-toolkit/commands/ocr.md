---
description: Extract text from scanned PDFs and images using OCR with confidence scoring and preprocessing
argument-hint: "<scanned file or directory>"
---

# /ocr -- Legal OCR Engine

Extract text from scanned PDFs and images using PaddleOCR (primary) with pytesseract fallback. Includes image preprocessing (deskewing, contrast enhancement, noise reduction), confidence scoring, and multi-language support.

@$1

## Workflow

- **Validate** the input path (file or directory) and check for supported formats (.pdf, .png, .jpg, .jpeg, .tiff, .tif, .bmp)
- **Process** using the `ocr` skill's Python script with PaddleOCR engine, image preprocessing, and confidence scoring
- **Present** results: documents processed, per-document confidence scores, and flag any pages below 0.85 confidence as potentially unreliable
- **Offer next steps**: summarize extracted text, generate searchable PDF, create a .docx report, or review specific pages
- Refer to the `ocr` skill (SKILL.md) for engine options, language support, and output format details
