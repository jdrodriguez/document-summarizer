#!/usr/bin/env python3
"""
Case Chronology Builder — extract dated events from legal documents and build
a master chronology with interactive timeline, gap analysis, and conflict detection.

Usage:
    python3 build_chronology.py --input <dir_or_file> --output-dir <dir> \
        [--start-date 2020-01-01] [--end-date 2026-12-31] [--event-types all]

Outputs (all written to --output-dir):
    chronology.xlsx          Master spreadsheet
    timeline.html            Interactive Plotly timeline
    gap_analysis.json        Periods with no events
    date_conflicts.json      Conflicting dates for same events
    chronology_summary.txt   Human-readable overview
    chronology.json          Structured data for programmatic use

Prints JSON summary to stdout. Progress/errors go to stderr.
Exit codes: 0 = success, 1 = partial success, 2 = failure.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from difflib import SequenceMatcher

import pandas as pd
import plotly.graph_objects as go
from dateutil import parser as dateutil_parser

# ---------------------------------------------------------------------------
# Logging helpers — progress to stderr, results to stdout
# ---------------------------------------------------------------------------

def log(msg: str):
    print(msg, file=sys.stderr, flush=True)


def log_progress(stage: str, detail: str = ""):
    payload = {"stage": stage}
    if detail:
        payload["detail"] = detail
    print(json.dumps(payload), file=sys.stderr, flush=True)

# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def find_files(input_path: str) -> list[dict]:
    """Return list of {path, name, ext} for all supported files."""
    p = Path(input_path)
    if p.is_file():
        if p.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [{"path": str(p), "name": p.name, "ext": p.suffix.lower()}]
        else:
            log(f"WARNING: Unsupported file type: {p.suffix}")
            return []
    elif p.is_dir():
        files = []
        for fp in sorted(p.rglob("*")):
            if fp.is_file() and fp.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append({"path": str(fp), "name": fp.name, "ext": fp.suffix.lower()})
        return files
    else:
        log(f"ERROR: Path not found: {input_path}")
        return []


def extract_text_pdf(filepath: str) -> list[dict]:
    """Extract text from PDF, returning list of {page, text}."""
    import pdfplumber
    pages = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append({"page": i, "text": text})
    except Exception as e:
        log(f"WARNING: Failed to read PDF {filepath}: {e}")
    return pages


def extract_text_docx(filepath: str) -> list[dict]:
    """Extract text from DOCX, returning list of {paragraph, text}."""
    from docx import Document
    paragraphs = []
    try:
        doc = Document(filepath)
        for i, para in enumerate(doc.paragraphs, start=1):
            text = para.text.strip()
            if text:
                paragraphs.append({"paragraph": i, "text": text})
    except Exception as e:
        log(f"WARNING: Failed to read DOCX {filepath}: {e}")
    return paragraphs


def extract_text_plain(filepath: str) -> list[dict]:
    """Extract text from TXT/MD, returning list of {line, text}."""
    lines = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                text = line.strip()
                if text:
                    lines.append({"line": i, "text": text})
    except Exception as e:
        log(f"WARNING: Failed to read {filepath}: {e}")
    return lines


def extract_text(file_info: dict) -> list[dict]:
    """Extract text from a file based on its extension.

    Returns list of dicts with 'text' and a location key (page/paragraph/line).
    """
    ext = file_info["ext"]
    path = file_info["path"]
    if ext == ".pdf":
        return extract_text_pdf(path)
    elif ext == ".docx":
        return extract_text_docx(path)
    elif ext in (".txt", ".md"):
        return extract_text_plain(path)
    return []

# ---------------------------------------------------------------------------
# Date extraction — hybrid spaCy NER + regex
# ---------------------------------------------------------------------------

# Common date regex patterns
DATE_PATTERNS = [
    # MM/DD/YYYY or MM-DD-YYYY
    (r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b', 'MDY'),
    # YYYY-MM-DD (ISO)
    (r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', 'YMD'),
    # Month DD, YYYY
    (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b', 'MONTH_D_Y'),
    # DD Month YYYY
    (r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December),?\s+(\d{4})\b', 'D_MONTH_Y'),
    # Mon DD, YYYY (abbreviated)
    (r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})\b', 'MON_D_Y'),
    # DD Mon YYYY (abbreviated)
    (r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?,?\s+(\d{4})\b', 'D_MON_Y'),
    # Month YYYY (less specific)
    (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b', 'MONTH_Y'),
]

COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), fmt) for p, fmt in DATE_PATTERNS]

# Event type classification keywords
EVENT_TYPE_KEYWORDS = {
    "filing": ["filed", "filing", "complaint", "motion", "petition", "brief", "pleading", "summons", "subpoena", "appeal"],
    "hearing": ["hearing", "oral argument", "conference", "calendar call", "pretrial", "arraignment", "sentencing"],
    "incident": ["accident", "incident", "injury", "collision", "assault", "event occurred", "took place"],
    "communication": ["letter", "email", "correspondence", "notification", "notice", "sent", "received", "called", "contacted"],
    "medical": ["diagnosis", "treatment", "surgery", "examination", "medical", "hospital", "doctor", "physician", "injury report"],
    "payment": ["payment", "invoice", "bill", "paid", "settlement", "damages", "compensation", "reimbursement"],
    "deadline": ["deadline", "due date", "statute of limitations", "expiration", "must be filed by", "response due"],
    "meeting": ["meeting", "conference call", "mediation", "arbitration", "negotiation", "deposition scheduled"],
    "deposition": ["deposition", "deposed", "testimony", "sworn statement", "examination under oath"],
    "order": ["order", "ruling", "judgment", "decree", "injunction", "decision", "opinion"],
}


def parse_date_string(date_str: str) -> datetime | None:
    """Try to parse a date string into a datetime object."""
    try:
        parsed = dateutil_parser.parse(date_str, fuzzy=False)
        # Reject dates that are clearly out of range
        if parsed.year < 1900 or parsed.year > 2100:
            return None
        return parsed
    except (ValueError, OverflowError):
        return None


def extract_dates_regex(text: str) -> list[dict]:
    """Extract dates using regex patterns."""
    found = []
    for pattern, fmt in COMPILED_PATTERNS:
        for match in pattern.finditer(text):
            date_str = match.group(0)
            parsed = parse_date_string(date_str)
            if parsed:
                found.append({
                    "date": parsed,
                    "date_str": date_str,
                    "start": match.start(),
                    "end": match.end(),
                    "method": "regex",
                })
    return found


def extract_dates_spacy(text: str, nlp) -> list[dict]:
    """Extract dates using spaCy NER."""
    found = []
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "DATE":
            parsed = parse_date_string(ent.text)
            if parsed:
                found.append({
                    "date": parsed,
                    "date_str": ent.text,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "method": "spacy_ner",
                })
    return found


def extract_dates(text: str, nlp) -> list[dict]:
    """Extract dates using both regex and spaCy, deduplicated."""
    regex_dates = extract_dates_regex(text)
    spacy_dates = extract_dates_spacy(text, nlp)

    # Merge, preferring regex (more precise) and deduplicating by position overlap
    all_dates = list(regex_dates)
    for sd in spacy_dates:
        overlaps = False
        for rd in regex_dates:
            # Check if spans overlap
            if sd["start"] < rd["end"] and sd["end"] > rd["start"]:
                overlaps = True
                break
        if not overlaps:
            all_dates.append(sd)

    return all_dates


def get_sentence_context(text: str, start: int, end: int, context_chars: int = 200) -> str:
    """Extract the sentence containing the date match, with surrounding context."""
    # Find sentence boundaries
    sent_start = max(0, text.rfind(".", 0, start) + 1)
    sent_end = text.find(".", end)
    if sent_end == -1:
        sent_end = min(len(text), end + context_chars)
    else:
        sent_end = min(sent_end + 1, len(text))

    # Expand to context_chars if sentence is very short
    if sent_end - sent_start < 50:
        sent_start = max(0, start - context_chars)
        sent_end = min(len(text), end + context_chars)

    return text[sent_start:sent_end].strip()


def classify_event_type(context: str) -> str:
    """Classify event type based on keywords in context."""
    context_lower = context.lower()
    scores = {}
    for event_type, keywords in EVENT_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in context_lower)
        if score > 0:
            scores[event_type] = score

    if scores:
        return max(scores, key=scores.get)
    return "other"


# ---------------------------------------------------------------------------
# Event extraction pipeline
# ---------------------------------------------------------------------------

def extract_events_from_segments(segments: list[dict], filename: str, nlp) -> list[dict]:
    """Extract events from text segments of a single document."""
    events = []
    for seg in segments:
        text = seg["text"]
        # Determine reference (page, paragraph, or line)
        ref_key = None
        ref_val = None
        for k in ("page", "paragraph", "line"):
            if k in seg:
                ref_key = k
                ref_val = seg[k]
                break

        dates = extract_dates(text, nlp)
        for d in dates:
            context = get_sentence_context(text, d["start"], d["end"])
            event_type = classify_event_type(context)
            events.append({
                "date": d["date"].isoformat()[:10],
                "date_obj": d["date"],
                "date_str_original": d["date_str"],
                "event_description": context,
                "event_type": event_type,
                "source_document": filename,
                "reference_type": ref_key or "unknown",
                "reference_value": ref_val or 0,
                "extraction_method": d["method"],
            })
    return events


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def similarity(a: str, b: str) -> float:
    """Compute string similarity between two descriptions."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def deduplicate_events(events: list[dict], threshold: float = 0.75) -> list[dict]:
    """Remove duplicate events (same date + very similar description)."""
    if not events:
        return events

    # Sort by date
    events_sorted = sorted(events, key=lambda e: e["date"])
    unique = [events_sorted[0]]

    for event in events_sorted[1:]:
        is_dup = False
        for u in unique:
            if u["date"] == event["date"]:
                if similarity(u["event_description"], event["event_description"]) >= threshold:
                    is_dup = True
                    break
        if not is_dup:
            unique.append(event)

    return unique


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------

def analyze_gaps(events: list[dict], min_gap_days: int = 30) -> list[dict]:
    """Identify significant periods with no documented events."""
    if len(events) < 2:
        return []

    dates = sorted(set(e["date"] for e in events))
    gaps = []

    for i in range(len(dates) - 1):
        d1 = datetime.fromisoformat(dates[i])
        d2 = datetime.fromisoformat(dates[i + 1])
        delta = (d2 - d1).days

        if delta >= min_gap_days:
            # Find surrounding events
            before = [e for e in events if e["date"] == dates[i]]
            after = [e for e in events if e["date"] == dates[i + 1]]

            gaps.append({
                "start_date": dates[i],
                "end_date": dates[i + 1],
                "gap_days": delta,
                "event_before": before[0]["event_description"][:200] if before else "",
                "event_after": after[0]["event_description"][:200] if after else "",
                "severity": "high" if delta >= 90 else "medium" if delta >= 60 else "low",
            })

    return gaps


# ---------------------------------------------------------------------------
# Date conflict detection
# ---------------------------------------------------------------------------

def detect_conflicts(events: list[dict], threshold: float = 0.6) -> list[dict]:
    """Find events that appear to describe the same thing but with different dates."""
    conflicts = []
    seen_pairs = set()

    for i, e1 in enumerate(events):
        for j, e2 in enumerate(events):
            if i >= j:
                continue
            if e1["date"] == e2["date"]:
                continue
            if e1["source_document"] == e2["source_document"]:
                continue

            pair_key = (min(i, j), max(i, j))
            if pair_key in seen_pairs:
                continue

            sim = similarity(e1["event_description"], e2["event_description"])
            if sim >= threshold:
                seen_pairs.add(pair_key)
                conflicts.append({
                    "event_description_1": e1["event_description"][:300],
                    "event_description_2": e2["event_description"][:300],
                    "date_1": e1["date"],
                    "date_2": e2["date"],
                    "source_1": e1["source_document"],
                    "source_2": e2["source_document"],
                    "similarity": round(sim, 3),
                    "date_difference_days": abs(
                        (datetime.fromisoformat(e1["date"]) - datetime.fromisoformat(e2["date"])).days
                    ),
                })

    return conflicts


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def build_timeline_html(events: list[dict], output_path: str):
    """Create an interactive Plotly timeline HTML file."""
    if not events:
        log("No events to plot in timeline.")
        return

    # Color map for event types
    colors = {
        "filing": "#2196F3",
        "hearing": "#9C27B0",
        "incident": "#F44336",
        "communication": "#4CAF50",
        "medical": "#FF9800",
        "payment": "#795548",
        "deadline": "#E91E63",
        "meeting": "#00BCD4",
        "deposition": "#673AB7",
        "order": "#3F51B5",
        "other": "#9E9E9E",
    }

    fig = go.Figure()

    # Group events by type
    by_type = defaultdict(list)
    for e in events:
        by_type[e["event_type"]].append(e)

    for event_type, type_events in sorted(by_type.items()):
        dates = [e["date"] for e in type_events]
        descriptions = [
            f"<b>{e['date']}</b><br>"
            f"<b>Type:</b> {e['event_type']}<br>"
            f"<b>Source:</b> {e['source_document']}<br>"
            f"<b>Ref:</b> {e['reference_type']} {e['reference_value']}<br>"
            f"<br>{e['event_description'][:300]}"
            for e in type_events
        ]
        color = colors.get(event_type, "#9E9E9E")

        fig.add_trace(go.Scatter(
            x=dates,
            y=[event_type] * len(dates),
            mode="markers",
            name=event_type.title(),
            marker=dict(size=12, color=color, symbol="circle"),
            text=descriptions,
            hoverinfo="text",
            hoverlabel=dict(bgcolor=color, font_size=12),
        ))

    fig.update_layout(
        title="Case Chronology — Interactive Timeline",
        xaxis_title="Date",
        yaxis_title="Event Type",
        hovermode="closest",
        showlegend=True,
        height=600,
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(rangeslider=dict(visible=True), type="date"),
    )

    fig.write_html(output_path, include_plotlyjs="cdn")
    log(f"Timeline written to: {output_path}")


def write_xlsx(events: list[dict], output_path: str):
    """Write events to an Excel spreadsheet."""
    if not events:
        log("No events to write to XLSX.")
        return

    rows = []
    for e in events:
        rows.append({
            "Date": e["date"],
            "Event Description": e["event_description"][:1000],
            "Event Type": e["event_type"],
            "Source Document": e["source_document"],
            "Reference": f"{e['reference_type']} {e['reference_value']}",
            "Context": e["event_description"],
            "Extraction Method": e["extraction_method"],
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("Date")

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Chronology", index=False)

        workbook = writer.book
        worksheet = writer.sheets["Chronology"]

        # Format header
        header_fmt = workbook.add_format({
            "bold": True,
            "bg_color": "#1a237e",
            "font_color": "#ffffff",
            "border": 1,
        })
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)

        # Auto-fit column widths (approximate)
        worksheet.set_column("A:A", 12)  # Date
        worksheet.set_column("B:B", 60)  # Event Description
        worksheet.set_column("C:C", 15)  # Event Type
        worksheet.set_column("D:D", 30)  # Source Document
        worksheet.set_column("E:E", 15)  # Reference
        worksheet.set_column("F:F", 80)  # Context
        worksheet.set_column("G:G", 15)  # Method

        # Conditional formatting for event types
        type_colors = {
            "filing": "#BBDEFB",
            "hearing": "#E1BEE7",
            "incident": "#FFCDD2",
            "communication": "#C8E6C9",
            "medical": "#FFE0B2",
            "payment": "#D7CCC8",
            "deadline": "#F8BBD0",
            "meeting": "#B2EBF2",
            "deposition": "#D1C4E9",
            "order": "#C5CAE9",
        }
        for event_type, color in type_colors.items():
            fmt = workbook.add_format({"bg_color": color})
            worksheet.conditional_format(
                1, 2, len(df), 2,
                {"type": "text", "criteria": "containing", "value": event_type, "format": fmt}
            )

    log(f"XLSX written to: {output_path}")


def write_summary(events: list[dict], files: list[dict], gaps: list[dict],
                   conflicts: list[dict], output_path: str):
    """Write a human-readable summary file."""
    lines = []
    lines.append("=" * 60)
    lines.append("CASE CHRONOLOGY — SUMMARY")
    lines.append("=" * 60)
    lines.append("")

    # Date range
    if events:
        dates = sorted(set(e["date"] for e in events))
        lines.append(f"Date Range:        {dates[0]} to {dates[-1]}")
    lines.append(f"Total Events:      {len(events)}")
    lines.append(f"Documents Processed: {len(files)}")
    lines.append(f"Gaps Detected:     {len(gaps)}")
    lines.append(f"Date Conflicts:    {len(conflicts)}")
    lines.append("")

    # Events by type
    lines.append("Events by Type:")
    lines.append("-" * 30)
    type_counts = defaultdict(int)
    for e in events:
        type_counts[e["event_type"]] += 1
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {t:<20} {c:>5}")
    lines.append("")

    # Documents
    lines.append("Documents:")
    lines.append("-" * 30)
    doc_counts = defaultdict(int)
    for e in events:
        doc_counts[e["source_document"]] += 1
    for doc, c in sorted(doc_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {doc:<40} {c:>5} events")
    lines.append("")

    # Gaps
    if gaps:
        lines.append("Significant Gaps:")
        lines.append("-" * 30)
        for g in gaps:
            lines.append(f"  {g['start_date']} to {g['end_date']} ({g['gap_days']} days) [{g['severity']}]")
        lines.append("")

    # Conflicts
    if conflicts:
        lines.append("Date Conflicts:")
        lines.append("-" * 30)
        for c in conflicts:
            lines.append(f"  Date 1: {c['date_1']} (from {c['source_1']})")
            lines.append(f"  Date 2: {c['date_2']} (from {c['source_2']})")
            lines.append(f"  Similarity: {c['similarity']:.0%}, Difference: {c['date_difference_days']} days")
            lines.append("")

    text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    log(f"Summary written to: {output_path}")
    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Case Chronology Builder")
    parser.add_argument("--input", required=True, action="append",
                        help="Input file or directory (can be specified multiple times)")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--start-date", default=None, help="Filter: earliest date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="Filter: latest date (YYYY-MM-DD)")
    parser.add_argument("--event-types", default="all",
                        help="Comma-separated event types to include, or 'all'")
    parser.add_argument("--min-gap-days", type=int, default=30,
                        help="Minimum gap in days to flag (default: 30)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse date filters
    start_date = None
    end_date = None
    if args.start_date:
        try:
            start_date = datetime.fromisoformat(args.start_date)
        except ValueError:
            log(f"WARNING: Invalid start-date '{args.start_date}', ignoring filter.")
    if args.end_date:
        try:
            end_date = datetime.fromisoformat(args.end_date)
        except ValueError:
            log(f"WARNING: Invalid end-date '{args.end_date}', ignoring filter.")

    event_type_filter = None
    if args.event_types and args.event_types.lower() != "all":
        event_type_filter = set(t.strip().lower() for t in args.event_types.split(","))

    # --- Find files ---
    log_progress("finding_files", "Scanning for documents...")
    all_files = []
    for inp in args.input:
        all_files.extend(find_files(inp))

    if not all_files:
        log("ERROR: No supported files found.")
        result = {"status": "error", "error": "No supported files found in the provided path(s)."}
        print(json.dumps(result))
        sys.exit(2)

    log(f"Found {len(all_files)} document(s) to process.")

    # --- Load spaCy ---
    log_progress("loading_model", "Loading spaCy NLP model...")
    try:
        import spacy
    except ImportError:
        log("ERROR: spaCy is not installed. Run: pip install spacy")
        result = {"status": "error", "error": "spaCy is not installed. Run: pip install spacy"}
        print(json.dumps(result))
        sys.exit(2)
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        log("ERROR: spaCy model 'en_core_web_sm' not found. Run: python3 -m spacy download en_core_web_sm")
        result = {"status": "error", "error": "spaCy model not found."}
        print(json.dumps(result))
        sys.exit(2)

    # Increase max length for large documents
    nlp.max_length = 2_000_000

    # --- Extract events from each document ---
    all_events = []
    for idx, file_info in enumerate(all_files, start=1):
        log_progress("extracting", f"Processing document {idx}/{len(all_files)}: {file_info['name']}")

        segments = extract_text(file_info)
        if not segments:
            log(f"  WARNING: No text extracted from {file_info['name']}")
            continue

        events = extract_events_from_segments(segments, file_info["name"], nlp)
        log(f"  Extracted {len(events)} date references from {file_info['name']}")
        all_events.extend(events)

    log(f"\nTotal raw events: {len(all_events)}")

    # --- Apply date filters ---
    if start_date or end_date:
        log_progress("filtering", "Applying date filters...")
        filtered = []
        for e in all_events:
            try:
                d = datetime.fromisoformat(e["date"])
            except (ValueError, TypeError):
                continue
            if start_date and d < start_date:
                continue
            if end_date and d > end_date:
                continue
            filtered.append(e)
        log(f"Events after date filtering: {len(filtered)} (from {len(all_events)})")
        all_events = filtered

    # --- Apply event type filter ---
    if event_type_filter:
        all_events = [e for e in all_events if e["event_type"] in event_type_filter]
        log(f"Events after type filtering: {len(all_events)}")

    # --- Deduplicate ---
    log_progress("deduplicating", "Removing duplicate events...")
    all_events = deduplicate_events(all_events)
    log(f"Events after deduplication: {len(all_events)}")

    # Sort chronologically
    all_events.sort(key=lambda e: e["date"])

    # --- Gap analysis ---
    log_progress("gap_analysis", "Analyzing gaps in timeline...")
    gaps = analyze_gaps(all_events, min_gap_days=args.min_gap_days)
    log(f"Gaps detected: {len(gaps)}")

    # --- Conflict detection ---
    log_progress("conflict_detection", "Detecting date conflicts...")
    conflicts = detect_conflicts(all_events)
    log(f"Date conflicts detected: {len(conflicts)}")

    # --- Remove non-serializable date_obj before writing ---
    for e in all_events:
        if "date_obj" in e:
            del e["date_obj"]

    # --- Write outputs ---
    log_progress("writing_outputs", "Writing output files...")

    # chronology.json
    json_path = str(output_dir / "chronology.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_events, f, indent=2, ensure_ascii=False)
    log(f"JSON written to: {json_path}")

    # chronology.xlsx
    xlsx_path = str(output_dir / "chronology.xlsx")
    write_xlsx(all_events, xlsx_path)

    # timeline.html
    html_path = str(output_dir / "timeline.html")
    build_timeline_html(all_events, html_path)

    # gap_analysis.json
    gap_path = str(output_dir / "gap_analysis.json")
    with open(gap_path, "w", encoding="utf-8") as f:
        json.dump(gaps, f, indent=2, ensure_ascii=False)
    log(f"Gap analysis written to: {gap_path}")

    # date_conflicts.json
    conflict_path = str(output_dir / "date_conflicts.json")
    with open(conflict_path, "w", encoding="utf-8") as f:
        json.dump(conflicts, f, indent=2, ensure_ascii=False)
    log(f"Conflicts written to: {conflict_path}")

    # chronology_summary.txt
    summary_path = str(output_dir / "chronology_summary.txt")
    summary_text = write_summary(all_events, all_files, gaps, conflicts, summary_path)

    # --- JSON result to stdout ---
    result = {
        "status": "success",
        "total_events": len(all_events),
        "documents_processed": len(all_files),
        "date_range": {
            "start": all_events[0]["date"] if all_events else None,
            "end": all_events[-1]["date"] if all_events else None,
        },
        "events_by_type": dict(sorted(
            defaultdict(int, {e["event_type"]: 0 for e in all_events}).items()
        )),
        "gaps_detected": len(gaps),
        "date_conflicts": len(conflicts),
        "output_dir": str(output_dir),
        "files": {
            "chronology_xlsx": xlsx_path,
            "timeline_html": html_path,
            "gap_analysis_json": gap_path,
            "date_conflicts_json": conflict_path,
            "chronology_json": json_path,
            "chronology_summary_txt": summary_path,
        },
    }

    # Recount event types properly
    type_counts = defaultdict(int)
    for e in all_events:
        type_counts[e["event_type"]] += 1
    result["events_by_type"] = dict(sorted(type_counts.items(), key=lambda x: -x[1]))

    print(json.dumps(result, indent=2))
    log("\nChronology build complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
