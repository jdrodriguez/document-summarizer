#!/usr/bin/env python3
"""
OCR processing script for the legal-ocr skill.

Extracts text from scanned PDFs and images using PaddleOCR (primary)
with pytesseract fallback. Includes image preprocessing for legal
document quality issues (fax artifacts, stamps, poor scans).

Usage:
    python3 ocr_process.py --input <file_or_dir> --output-dir <dir> \
        [--engine paddleocr|tesseract] [--language en] [--dpi 300]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency imports (with graceful fallbacks)
# ---------------------------------------------------------------------------
try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:
    Image = None
    print("ERROR: Pillow is required. Install with: pip install Pillow", file=sys.stderr)
    sys.exit(2)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

# Cache PaddleOCR instances per language to avoid re-initialization per page
_PADDLE_CACHE = {}


def _get_paddle_ocr(lang):
    """Get or create a cached PaddleOCR instance."""
    if lang not in _PADDLE_CACHE:
        from paddleocr import PaddleOCR
        _PADDLE_CACHE[lang] = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    return _PADDLE_CACHE[lang]

try:
    import pytesseract
except ImportError:
    pytesseract = None

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}

# PaddleOCR language code mapping (subset of common legal languages)
PADDLE_LANG_MAP = {
    "en": "en", "english": "en",
    "es": "es", "spanish": "es",
    "fr": "french", "french": "french",
    "de": "german", "german": "german",
    "pt": "pt", "portuguese": "pt",
    "it": "it", "italian": "it",
    "zh": "ch", "chinese": "ch",
    "ja": "japan", "japanese": "japan",
    "ko": "korean", "korean": "korean",
    "ar": "ar", "arabic": "ar",
    "ru": "ru", "russian": "ru",
}

# Tesseract language code mapping
TESS_LANG_MAP = {
    "en": "eng", "english": "eng",
    "es": "spa", "spanish": "spa",
    "fr": "fra", "french": "fra",
    "de": "deu", "german": "deu",
    "pt": "por", "portuguese": "por",
    "it": "ita", "italian": "ita",
    "zh": "chi_sim", "chinese": "chi_sim",
    "ja": "jpn", "japanese": "jpn",
    "ko": "kor", "korean": "kor",
    "ar": "ara", "arabic": "ara",
    "ru": "rus", "russian": "rus",
}


# ---------------------------------------------------------------------------
# Image preprocessing pipeline
# ---------------------------------------------------------------------------
def preprocess_image(img: "Image.Image") -> "Image.Image":
    """
    Preprocessing pipeline for scanned legal documents:
    1. Convert to grayscale
    2. Deskew (auto-rotate)
    3. Enhance contrast
    4. Reduce noise
    5. Sharpen
    """
    # Convert to grayscale if not already
    if img.mode != "L":
        img = img.convert("L")

    # Auto-contrast to normalize brightness
    img = ImageOps.autocontrast(img, cutoff=1)

    # Enhance contrast (legal docs often have faded text)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)

    # Noise reduction using median filter (good for fax artifacts)
    img = img.filter(ImageFilter.MedianFilter(size=3))

    # Sharpen text edges
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)

    # Binarize using adaptive-like threshold via point operation
    # This helps with stamp marks and uneven lighting
    threshold = 140
    img = img.point(lambda x: 255 if x > threshold else 0, "1")

    # Convert back to grayscale for OCR engines
    img = img.convert("L")

    return img


def deskew_image(img: "Image.Image") -> "Image.Image":
    """
    Attempt to deskew a scanned image.
    Uses a simple approach: find the dominant angle of text lines.
    Falls back to no rotation if detection fails.
    """
    try:
        # Convert to binary for angle detection
        bw = img.convert("L")
        bw = bw.point(lambda x: 0 if x < 128 else 255, "1")

        # Try small rotations and pick the one with the most
        # horizontal alignment (fewest transitions per row)
        best_angle = 0
        best_score = float("inf")

        for angle_tenth in range(-30, 31):  # -3.0 to 3.0 degrees
            angle = angle_tenth / 10.0
            rotated = bw.rotate(angle, fillcolor=1, expand=False)
            # Sample middle rows and count transitions
            width, height = rotated.size
            mid_start = height // 3
            mid_end = 2 * height // 3
            score = 0
            sample_rows = range(mid_start, mid_end, max(1, (mid_end - mid_start) // 20))
            for y in sample_rows:
                row = list(rotated.crop((0, y, width, y + 1)).getdata())
                transitions = sum(1 for i in range(1, len(row)) if row[i] != row[i - 1])
                score += transitions

            if score < best_score:
                best_score = score
                best_angle = angle

        if abs(best_angle) > 0.1:
            print(f"  Deskew: rotating {best_angle:.1f} degrees", file=sys.stderr)
            img = img.rotate(best_angle, fillcolor=255, expand=True)
    except Exception as e:
        print(f"  Deskew failed (proceeding without): {e}", file=sys.stderr)

    return img


# ---------------------------------------------------------------------------
# PDF to image conversion
# ---------------------------------------------------------------------------
def pdf_to_images_pymupdf(pdf_path: str, dpi: int) -> list[tuple["Image.Image", int]]:
    """Convert PDF pages to PIL Images using PyMuPDF."""
    if fitz is None:
        return []
    images = []
    try:
        doc = fitz.open(pdf_path)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=matrix)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append((img, page_num + 1))
        doc.close()
    except Exception as e:
        print(f"PyMuPDF PDF->image failed: {e}", file=sys.stderr)
        return []
    return images


def pdf_to_images_pdf2image(pdf_path: str, dpi: int) -> list[tuple["Image.Image", int]]:
    """Convert PDF pages to PIL Images using pdf2image (poppler)."""
    if convert_from_path is None:
        return []
    images = []
    try:
        pil_images = convert_from_path(pdf_path, dpi=dpi)
        for i, img in enumerate(pil_images):
            images.append((img, i + 1))
    except Exception as e:
        print(f"pdf2image conversion failed: {e}", file=sys.stderr)
        return []
    return images


def pdf_to_images(pdf_path: str, dpi: int) -> list[tuple["Image.Image", int]]:
    """Convert PDF to images with cascading fallbacks."""
    for converter in (pdf_to_images_pymupdf, pdf_to_images_pdf2image):
        images = converter(pdf_path, dpi)
        if images:
            return images
    return []


# ---------------------------------------------------------------------------
# OCR engines
# ---------------------------------------------------------------------------
def ocr_paddleocr(img: "Image.Image", language: str) -> dict:
    """
    Run PaddleOCR on a PIL Image.
    Returns: {"text": str, "words": [...], "confidence": float}
    """
    if PaddleOCR is None:
        return {"text": "", "words": [], "confidence": 0.0, "error": "PaddleOCR not available"}

    paddle_lang = PADDLE_LANG_MAP.get(language.lower(), "en")

    try:
        # Use cached PaddleOCR instance to avoid re-initialization per page
        ocr = _get_paddle_ocr(paddle_lang)

        # Save image to temp file (PaddleOCR works best with file paths)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img.save(tmp.name)
            tmp_path = tmp.name

        try:
            result = ocr.ocr(tmp_path, cls=True)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        if not result or not result[0]:
            return {"text": "", "words": [], "confidence": 0.0}

        words = []
        lines = []
        confidences = []

        for line in result[0]:
            bbox = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            text = line[1][0]
            conf = line[1][1]

            words.append({
                "text": text,
                "confidence": round(conf, 4),
                "bbox": {
                    "x1": int(min(p[0] for p in bbox)),
                    "y1": int(min(p[1] for p in bbox)),
                    "x2": int(max(p[0] for p in bbox)),
                    "y2": int(max(p[1] for p in bbox)),
                },
            })
            lines.append(text)
            confidences.append(conf)

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "text": "\n".join(lines),
            "words": words,
            "confidence": round(avg_confidence, 4),
        }

    except Exception as e:
        return {"text": "", "words": [], "confidence": 0.0, "error": str(e)}


def ocr_tesseract(img: "Image.Image", language: str) -> dict:
    """
    Run Tesseract OCR on a PIL Image.
    Returns: {"text": str, "words": [...], "confidence": float}
    """
    if pytesseract is None:
        return {"text": "", "words": [], "confidence": 0.0, "error": "pytesseract not available"}

    tess_lang = TESS_LANG_MAP.get(language.lower(), "eng")

    try:
        # Get detailed data with confidence scores
        data = pytesseract.image_to_data(img, lang=tess_lang, output_type=pytesseract.Output.DICT)

        words = []
        lines_by_block = {}
        confidences = []

        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = int(data["conf"][i])

            if not text or conf < 0:
                continue

            conf_normalized = conf / 100.0

            words.append({
                "text": text,
                "confidence": round(conf_normalized, 4),
                "bbox": {
                    "x1": data["left"][i],
                    "y1": data["top"][i],
                    "x2": data["left"][i] + data["width"][i],
                    "y2": data["top"][i] + data["height"][i],
                },
            })
            confidences.append(conf_normalized)

            block_num = data["block_num"][i]
            line_num = data["line_num"][i]
            key = (block_num, line_num)
            if key not in lines_by_block:
                lines_by_block[key] = []
            lines_by_block[key].append(text)

        # Reconstruct text preserving line structure
        full_text_lines = []
        for key in sorted(lines_by_block.keys()):
            full_text_lines.append(" ".join(lines_by_block[key]))

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "text": "\n".join(full_text_lines),
            "words": words,
            "confidence": round(avg_confidence, 4),
        }

    except Exception as e:
        return {"text": "", "words": [], "confidence": 0.0, "error": str(e)}


def run_ocr(img: "Image.Image", engine: str, language: str) -> dict:
    """Run OCR with the specified engine, falling back if needed."""
    if engine == "paddleocr":
        result = ocr_paddleocr(img, language)
        if result["text"] or "error" not in result:
            return result
        print(f"  PaddleOCR failed, falling back to tesseract: {result.get('error', 'unknown')}", file=sys.stderr)
        return ocr_tesseract(img, language)
    elif engine == "tesseract":
        result = ocr_tesseract(img, language)
        if result["text"] or "error" not in result:
            return result
        print(f"  Tesseract failed, trying PaddleOCR: {result.get('error', 'unknown')}", file=sys.stderr)
        return ocr_paddleocr(img, language)
    else:
        print(f"  Unknown engine '{engine}', trying PaddleOCR", file=sys.stderr)
        return ocr_paddleocr(img, language)


# ---------------------------------------------------------------------------
# Single-file OCR processing
# ---------------------------------------------------------------------------
def process_image_file(filepath: str, engine: str, language: str, dpi: int) -> dict:
    """Process a single image file through OCR."""
    print(f"  Processing image: {Path(filepath).name}", file=sys.stderr)

    try:
        img = Image.open(filepath)
    except Exception as e:
        return {"error": f"Cannot open image: {e}", "pages": []}

    # Preprocess
    img = deskew_image(img)
    processed = preprocess_image(img)

    # OCR
    result = run_ocr(processed, engine, language)

    page_result = {
        "page": 1,
        "text": result["text"],
        "words": result["words"],
        "confidence": result["confidence"],
        "warnings": [],
    }

    if result["confidence"] < 0.7:
        page_result["warnings"].append(
            f"Low confidence ({result['confidence']:.2f}). Text may contain errors."
        )
    if result["confidence"] < 0.5:
        page_result["warnings"].append(
            "Very low confidence. Consider re-scanning at higher resolution."
        )

    return {
        "source_file": os.path.abspath(filepath),
        "filename": Path(filepath).name,
        "total_pages": 1,
        "pages": [page_result],
        "average_confidence": result["confidence"],
        "engine_used": engine,
    }


def process_pdf_file(filepath: str, engine: str, language: str, dpi: int) -> dict:
    """Process a scanned PDF through OCR."""
    filename = Path(filepath).name
    print(f"  Converting PDF to images: {filename} (dpi={dpi})", file=sys.stderr)

    images = pdf_to_images(filepath, dpi)
    if not images:
        return {
            "error": f"Could not convert PDF to images. Install PyMuPDF or poppler-utils.",
            "source_file": os.path.abspath(filepath),
            "filename": filename,
            "total_pages": 0,
            "pages": [],
        }

    total_pages = len(images)
    print(f"  {total_pages} pages to process", file=sys.stderr)

    pages = []
    all_confidences = []

    for img, page_num in images:
        print(f"  OCR page {page_num}/{total_pages}...", file=sys.stderr)

        # Preprocess
        img = deskew_image(img)
        processed = preprocess_image(img)

        # OCR
        result = run_ocr(processed, engine, language)

        page_result = {
            "page": page_num,
            "text": result["text"],
            "words": result["words"],
            "confidence": result["confidence"],
            "warnings": [],
        }

        if result["confidence"] < 0.7:
            page_result["warnings"].append(
                f"Low confidence ({result['confidence']:.2f}). Text may contain errors."
            )
        if result["confidence"] < 0.5:
            page_result["warnings"].append(
                "Very low confidence. Consider re-scanning this page."
            )

        pages.append(page_result)
        all_confidences.append(result["confidence"])

    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    return {
        "source_file": os.path.abspath(filepath),
        "filename": filename,
        "total_pages": total_pages,
        "pages": pages,
        "average_confidence": round(avg_confidence, 4),
        "engine_used": engine,
    }


def process_file(filepath: str, engine: str, language: str, dpi: int) -> dict:
    """Route processing based on file type."""
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        return process_pdf_file(filepath, engine, language, dpi)
    elif ext in SUPPORTED_EXTENSIONS:
        return process_image_file(filepath, engine, language, dpi)
    else:
        return {"error": f"Unsupported file type: {ext}"}


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------
def write_outputs(results: list[dict], output_dir: str) -> dict:
    """Write all output files and return summary."""
    os.makedirs(output_dir, exist_ok=True)

    all_results = []
    total_pages = 0
    total_confidences = []
    all_warnings = []

    for result in results:
        if "error" in result and not result.get("pages"):
            all_warnings.append(f"{result.get('filename', 'unknown')}: {result['error']}")
            continue

        filename_stem = Path(result["filename"]).stem

        # Write per-document text file
        text_lines = []
        for page in result["pages"]:
            text_lines.append(f"--- Page {page['page']} (confidence: {page['confidence']:.2f}) ---")
            text_lines.append(page["text"])
            text_lines.append("")

        txt_path = os.path.join(output_dir, f"{filename_stem}_ocr.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(text_lines))

        total_pages += result["total_pages"]
        total_confidences.append(result["average_confidence"])

        for page in result["pages"]:
            for warning in page.get("warnings", []):
                all_warnings.append(f"{result['filename']} page {page['page']}: {warning}")

        all_results.append({
            "source_file": result["source_file"],
            "filename": result["filename"],
            "total_pages": result["total_pages"],
            "average_confidence": result["average_confidence"],
            "engine_used": result.get("engine_used", "unknown"),
            "text_output": txt_path,
            "pages": [
                {
                    "page": p["page"],
                    "confidence": p["confidence"],
                    "word_count": len(p["words"]),
                    "char_count": len(p["text"]),
                    "warnings": p.get("warnings", []),
                }
                for p in result["pages"]
            ],
        })

    # Write structured JSON results
    ocr_results = {
        "total_documents": len(all_results),
        "total_pages": total_pages,
        "average_confidence": round(
            sum(total_confidences) / len(total_confidences) if total_confidences else 0.0, 4
        ),
        "warnings": all_warnings,
        "documents": all_results,
    }

    json_path = os.path.join(output_dir, "ocr_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(ocr_results, f, indent=2)

    # Write human-readable extraction report
    report_lines = [
        "OCR Extraction Report",
        "=" * 50,
        "",
        f"Documents processed: {len(all_results)}",
        f"Total pages: {total_pages}",
        f"Average confidence: {ocr_results['average_confidence']:.2%}",
        "",
    ]

    for doc in all_results:
        report_lines.append(f"Document: {doc['filename']}")
        report_lines.append(f"  Pages: {doc['total_pages']}")
        report_lines.append(f"  Average confidence: {doc['average_confidence']:.2%}")
        report_lines.append(f"  Engine: {doc['engine_used']}")
        report_lines.append(f"  Output: {doc['text_output']}")

        low_conf_pages = [p for p in doc["pages"] if p["confidence"] < 0.85]
        if low_conf_pages:
            report_lines.append(f"  Low confidence pages:")
            for p in low_conf_pages:
                report_lines.append(f"    Page {p['page']}: {p['confidence']:.2%}")
        report_lines.append("")

    if all_warnings:
        report_lines.append("Warnings:")
        report_lines.append("-" * 30)
        for warning in all_warnings:
            report_lines.append(f"  - {warning}")
        report_lines.append("")

    report_path = os.path.join(output_dir, "extraction_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    return ocr_results


# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------
def find_supported_files(dirpath: str) -> list[str]:
    """Find all supported files in a directory (non-recursive)."""
    files = []
    for entry in sorted(os.listdir(dirpath)):
        full = os.path.join(dirpath, entry)
        if os.path.isfile(full) and Path(entry).suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(full)
    return files


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="OCR processing for scanned PDFs and images. "
                    "Accepts a single file or a directory of files."
    )
    parser.add_argument("--input", required=True,
                        help="Path to a file or directory of files")
    parser.add_argument("--output-dir", required=True,
                        help="Directory for OCR output")
    parser.add_argument("--engine", default="paddleocr",
                        choices=["paddleocr", "tesseract"],
                        help="OCR engine to use (default: paddleocr)")
    parser.add_argument("--language", default="en",
                        help="Language for OCR (default: en)")
    parser.add_argument("--dpi", type=int, default=300,
                        help="DPI for PDF to image conversion (default: 300)")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output_dir)

    # Validate engine availability
    if args.engine == "paddleocr" and PaddleOCR is None:
        if pytesseract is not None:
            print("PaddleOCR not available, falling back to tesseract", file=sys.stderr)
            args.engine = "tesseract"
        else:
            print(json.dumps({
                "error": "No OCR engine available. Install paddleocr or pytesseract.",
            }))
            sys.exit(2)
    elif args.engine == "tesseract" and pytesseract is None:
        if PaddleOCR is not None:
            print("Tesseract not available, falling back to PaddleOCR", file=sys.stderr)
            args.engine = "paddleocr"
        else:
            print(json.dumps({
                "error": "No OCR engine available. Install paddleocr or pytesseract.",
            }))
            sys.exit(2)

    start_time = time.time()

    if os.path.isdir(input_path):
        # Directory mode
        files = find_supported_files(input_path)
        if not files:
            print(json.dumps({
                "error": f"No supported files found in {input_path}",
                "supported": list(SUPPORTED_EXTENSIONS),
            }))
            sys.exit(1)

        print(f"Batch mode: found {len(files)} file(s)", file=sys.stderr)
        for f in files:
            print(f"  - {Path(f).name}", file=sys.stderr)

        results = []
        for filepath in files:
            result = process_file(filepath, args.engine, args.language, args.dpi)
            results.append(result)

    elif os.path.isfile(input_path):
        # Single file mode
        ext = Path(input_path).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            print(json.dumps({
                "error": f"Unsupported file type: {ext}",
                "supported": list(SUPPORTED_EXTENSIONS),
            }))
            sys.exit(1)

        result = process_file(input_path, args.engine, args.language, args.dpi)
        results = [result]

    else:
        print(json.dumps({"error": f"Path not found: {input_path}"}))
        sys.exit(1)

    elapsed = round(time.time() - start_time, 2)

    # Write outputs
    summary = write_outputs(results, output_dir)
    summary["processing_time_seconds"] = elapsed
    summary["output_dir"] = output_dir
    summary["engine"] = args.engine
    summary["language"] = args.language
    summary["dpi"] = args.dpi
    summary["status"] = "success"

    # Print JSON to stdout for Claude to parse
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
