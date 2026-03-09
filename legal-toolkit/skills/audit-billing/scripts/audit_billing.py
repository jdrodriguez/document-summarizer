#!/usr/bin/env python3
"""
Legal Billing Auditor -- parse law firm billing data and perform automated audit analysis.

Supports: LEDES 1998B, Excel (.xlsx), CSV
Outputs: audit_report.json, flagged_entries.xlsx, spend_dashboard.html, audit_summary.txt

Usage:
    python3 audit_billing.py --input <file_or_dir> --output-dir <dir> \
        [--rate-caps <file.json>] [--max-daily-hours 10]
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    import holidays as holidays_lib
    US_HOLIDAYS = holidays_lib.US()
except ImportError:
    US_HOLIDAYS = None

# ---------------------------------------------------------------------------
# Column normalization mappings
# ---------------------------------------------------------------------------
COLUMN_MAP = {
    # date
    "date": "date", "invoice_date": "date", "work_date": "date",
    "inv_date": "date", "line_item_date": "date", "billing_date": "date",
    "service_date": "date", "entry_date": "date",
    # timekeeper
    "timekeeper": "timekeeper", "timekeeper_name": "timekeeper",
    "attorney": "timekeeper", "lawyer": "timekeeper", "tk_name": "timekeeper",
    "biller": "timekeeper", "professional": "timekeeper", "name": "timekeeper",
    # hours
    "hours": "hours", "line_item_hours": "hours", "qty": "hours",
    "quantity": "hours", "units": "hours", "time": "hours",
    "hours_worked": "hours", "billable_hours": "hours",
    # rate
    "rate": "rate", "line_item_rate": "rate", "hourly_rate": "rate",
    "billing_rate": "rate", "tk_rate": "rate", "unit_price": "rate",
    # amount
    "amount": "amount", "line_item_total": "amount", "total": "amount",
    "line_amount": "amount", "fee_amount": "amount", "extended_amount": "amount",
    "line_item_amount": "amount", "billed_amount": "amount",
    # description
    "description": "description", "line_item_description": "description",
    "narrative": "description", "details": "description", "task_description": "description",
    "work_description": "description", "activity_description": "description",
    "line_item_narrative": "description",
    # task code
    "task_code": "task_code", "utbms_task": "task_code", "task": "task_code",
    # activity code
    "activity_code": "activity_code", "utbms_activity": "activity_code",
    "activity": "activity_code",
    # matter
    "matter": "matter", "matter_id": "matter", "matter_name": "matter",
    "client_matter": "matter", "case": "matter", "case_name": "matter",
    "matter_number": "matter",
}


def log(msg):
    """Print progress to stderr."""
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# File Parsing
# ---------------------------------------------------------------------------

def detect_format(filepath):
    """Auto-detect file format based on extension and content."""
    ext = Path(filepath).suffix.lower()
    if ext in (".xlsx", ".xls"):
        return "excel"
    if ext in (".csv",):
        # Check if it's actually LEDES
        with open(filepath, "r", errors="replace") as f:
            first_line = f.readline().strip()
            if first_line.startswith("LEDES1998B"):
                return "ledes"
        return "csv"
    if ext in (".txt", ".ledes"):
        with open(filepath, "r", errors="replace") as f:
            first_line = f.readline().strip()
            if first_line.startswith("LEDES1998B"):
                return "ledes"
        return "csv"  # Fall back to CSV-style parsing
    return None


def parse_ledes(filepath):
    """Parse LEDES 1998B format (pipe-delimited legal billing standard)."""
    log(f"  Parsing LEDES: {filepath}")
    rows = []
    headers = None
    with open(filepath, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("LEDES1998B"):
                continue
            # LEDES uses pipe delimiters with trailing pipe
            parts = [p.strip() for p in line.split("|")]
            # Remove empty trailing element from trailing pipe
            if parts and parts[-1] == "":
                parts = parts[:-1]
            if headers is None:
                headers = [h.lower().replace(" ", "_") for h in parts]
                continue
            if len(parts) == len(headers):
                rows.append(dict(zip(headers, parts)))
            elif len(parts) > 0:
                # Pad or truncate to match headers
                padded = parts + [""] * (len(headers) - len(parts))
                rows.append(dict(zip(headers, padded[:len(headers)])))
    if not rows:
        log(f"  WARNING: No data rows found in LEDES file: {filepath}")
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["_source_file"] = os.path.basename(filepath)
    return df


def parse_excel(filepath):
    """Parse Excel billing file."""
    log(f"  Parsing Excel: {filepath}")
    try:
        df = pd.read_excel(filepath, engine="openpyxl")
    except Exception as e:
        log(f"  ERROR parsing Excel {filepath}: {e}")
        return pd.DataFrame()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    df["_source_file"] = os.path.basename(filepath)
    return df


def parse_csv(filepath):
    """Parse CSV billing file."""
    log(f"  Parsing CSV: {filepath}")
    try:
        df = pd.read_csv(filepath, encoding="utf-8", on_bad_lines="skip")
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(filepath, encoding="latin-1", on_bad_lines="skip")
        except Exception as e:
            log(f"  ERROR parsing CSV {filepath}: {e}")
            return pd.DataFrame()
    except Exception as e:
        log(f"  ERROR parsing CSV {filepath}: {e}")
        return pd.DataFrame()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    df["_source_file"] = os.path.basename(filepath)
    return df


def parse_file(filepath):
    """Parse a single billing file, auto-detecting format."""
    fmt = detect_format(filepath)
    if fmt == "ledes":
        return parse_ledes(filepath)
    elif fmt == "excel":
        return parse_excel(filepath)
    elif fmt == "csv":
        return parse_csv(filepath)
    else:
        log(f"  Skipping unsupported file: {filepath}")
        return pd.DataFrame()


def normalize_columns(df):
    """Map various column names to standard fields."""
    rename = {}
    for col in df.columns:
        col_lower = col.lower().strip().replace(" ", "_")
        if col_lower in COLUMN_MAP:
            rename[col] = COLUMN_MAP[col_lower]
    df = df.rename(columns=rename)

    # Ensure required columns exist (fill with None if missing)
    for required in ["date", "timekeeper", "hours", "rate", "amount", "description"]:
        if required not in df.columns:
            df[required] = None

    # Coerce types
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Compute amount if missing but hours and rate present
    mask = df["amount"].isna() & df["hours"].notna() & df["rate"].notna()
    df.loc[mask, "amount"] = df.loc[mask, "hours"] * df.loc[mask, "rate"]

    # Fill description with empty string
    df["description"] = df["description"].fillna("").astype(str)
    df["timekeeper"] = df["timekeeper"].fillna("Unknown").astype(str)

    # Optional columns
    for opt in ["task_code", "activity_code", "matter"]:
        if opt not in df.columns:
            df[opt] = ""
        df[opt] = df[opt].fillna("").astype(str)

    return df


# ---------------------------------------------------------------------------
# Audit Rules Engine
# ---------------------------------------------------------------------------

def rule_block_billing(df):
    """Detect block billing: multiple tasks in one entry without time breakdown."""
    flags = []
    block_patterns = [
        r'\band\b.*\band\b',           # multiple "and"
        r';\s*\w',                       # semicolons separating tasks
        r'(?:review|draft|prepare|attend|research|analyze|confer|discuss|telephone|email)\w*.*(?:review|draft|prepare|attend|research|analyze|confer|discuss|telephone|email)',
    ]
    for idx, row in df.iterrows():
        desc = str(row.get("description", "")).lower()
        if not desc or len(desc) < 10:
            continue
        for pattern in block_patterns:
            if re.search(pattern, desc, re.IGNORECASE):
                flags.append({
                    "index": int(idx),
                    "rule": "block_billing",
                    "severity": "HIGH",
                    "explanation": "Multiple tasks described in a single time entry without individual time breakdown",
                    "detail": desc[:200],
                })
                break
    return flags


def rule_vague_description(df):
    """Detect vague or generic billing descriptions."""
    vague_phrases = [
        r'^review\s*$', r'^research\s*$', r'^review documents?\s*$',
        r'^attention to matter\s*$', r'^conference\s*$', r'^work on matter\s*$',
        r'^legal research\s*$', r'^document review\s*$', r'^file review\s*$',
        r'^correspondence\s*$', r'^telephone call\s*$', r'^email\s*$',
        r'^meeting\s*$', r'^preparation\s*$', r'^analysis\s*$',
        r'^review and analysis\s*$', r'^attention to file\s*$',
        r'^various matters\s*$', r'^administrative\s*$',
    ]
    flags = []
    combined = re.compile("|".join(vague_phrases), re.IGNORECASE)
    for idx, row in df.iterrows():
        desc = str(row.get("description", "")).strip()
        if not desc:
            flags.append({
                "index": int(idx),
                "rule": "vague_description",
                "severity": "MEDIUM",
                "explanation": "Empty billing description",
                "detail": "(empty)",
            })
            continue
        if len(desc) < 15 or combined.search(desc):
            flags.append({
                "index": int(idx),
                "rule": "vague_description",
                "severity": "MEDIUM",
                "explanation": "Billing description is too vague or generic to evaluate work performed",
                "detail": desc[:200],
            })
    return flags


def rule_excessive_hours(df, max_daily=10, max_single_task=3.0):
    """Flag excessive hours: >max_daily per day per timekeeper, >max_single_task for one entry."""
    flags = []
    # Single-entry check
    for idx, row in df.iterrows():
        hours = row.get("hours")
        if pd.notna(hours) and hours > max_single_task:
            flags.append({
                "index": int(idx),
                "rule": "excessive_hours_single",
                "severity": "MEDIUM",
                "explanation": f"Single entry exceeds {max_single_task} hours ({hours:.1f}h)",
                "detail": str(row.get("description", ""))[:200],
            })

    # Daily aggregate check
    valid = df[df["date"].notna() & df["hours"].notna()].copy()
    if not valid.empty:
        daily = valid.groupby([valid["date"].dt.date, "timekeeper"])["hours"].sum().reset_index()
        daily.columns = ["date", "timekeeper", "total_hours"]
        excessive_days = daily[daily["total_hours"] > max_daily]
        for _, day_row in excessive_days.iterrows():
            # Find the entries for that day/timekeeper
            mask = (
                (df["date"].dt.date == day_row["date"]) &
                (df["timekeeper"] == day_row["timekeeper"])
            )
            matching = df[mask]
            for idx in matching.index:
                flags.append({
                    "index": int(idx),
                    "rule": "excessive_hours_daily",
                    "severity": "HIGH",
                    "explanation": f"Timekeeper {day_row['timekeeper']} billed {day_row['total_hours']:.1f}h on {day_row['date']} (max: {max_daily}h)",
                    "detail": str(df.loc[idx, "description"])[:200],
                })
    return flags


def rule_rate_violations(df, rate_caps):
    """Compare rates against provided rate caps."""
    if not rate_caps:
        return []
    flags = []
    for idx, row in df.iterrows():
        rate = row.get("rate")
        tk = str(row.get("timekeeper", "")).strip()
        if pd.isna(rate) or not tk:
            continue
        # Check exact match or partial match in rate caps
        cap = None
        for cap_name, cap_rate in rate_caps.items():
            if cap_name.lower() in tk.lower() or tk.lower() in cap_name.lower():
                cap = cap_rate
                break
        # Also check for level-based caps (e.g., "partner", "associate")
        if cap is None:
            desc_lower = tk.lower()
            for cap_name, cap_rate in rate_caps.items():
                if cap_name.lower() in desc_lower:
                    cap = cap_rate
                    break
        if cap is not None and rate > cap:
            flags.append({
                "index": int(idx),
                "rule": "rate_violation",
                "severity": "HIGH",
                "explanation": f"Rate ${rate:.2f}/hr exceeds cap ${cap:.2f}/hr for {tk}",
                "detail": str(row.get("description", ""))[:200],
            })
    return flags


def rule_duplicate_entries(df):
    """Find duplicate entries: same date + timekeeper + similar description."""
    flags = []
    valid = df[df["date"].notna()].copy()
    if valid.empty:
        return flags
    grouped = valid.groupby([valid["date"].dt.date, "timekeeper"])
    for (date, tk), group in grouped:
        if len(group) < 2:
            continue
        descs = group["description"].tolist()
        indices = group.index.tolist()
        for i in range(len(descs)):
            for j in range(i + 1, len(descs)):
                d1 = str(descs[i]).lower().strip()
                d2 = str(descs[j]).lower().strip()
                if not d1 or not d2:
                    continue
                # Simple similarity: check if one is substring of other or high overlap
                if d1 == d2 or d1 in d2 or d2 in d1:
                    flags.append({
                        "index": int(indices[j]),
                        "rule": "duplicate_entry",
                        "severity": "HIGH",
                        "explanation": f"Possible duplicate: same date ({date}), timekeeper ({tk}), similar description",
                        "detail": f"Entry A: {d1[:100]} | Entry B: {d2[:100]}",
                    })
                else:
                    # Word overlap check
                    words1 = set(d1.split())
                    words2 = set(d2.split())
                    if len(words1) > 2 and len(words2) > 2:
                        overlap = len(words1 & words2) / max(len(words1 | words2), 1)
                        if overlap > 0.7:
                            flags.append({
                                "index": int(indices[j]),
                                "rule": "duplicate_entry",
                                "severity": "MEDIUM",
                                "explanation": f"Possible duplicate: same date ({date}), timekeeper ({tk}), {overlap:.0%} word overlap",
                                "detail": f"Entry A: {d1[:100]} | Entry B: {d2[:100]}",
                            })
    return flags


def rule_weekend_holiday(df):
    """Flag entries on weekends or federal holidays."""
    flags = []
    for idx, row in df.iterrows():
        dt = row.get("date")
        if pd.isna(dt):
            continue
        day_of_week = dt.weekday()
        if day_of_week >= 5:  # Saturday=5, Sunday=6
            day_name = "Saturday" if day_of_week == 5 else "Sunday"
            flags.append({
                "index": int(idx),
                "rule": "weekend_billing",
                "severity": "LOW",
                "explanation": f"Work billed on {day_name} ({dt.strftime('%Y-%m-%d')})",
                "detail": str(row.get("description", ""))[:200],
            })
        elif US_HOLIDAYS is not None and dt.date() in US_HOLIDAYS:
            holiday_name = US_HOLIDAYS.get(dt.date())
            flags.append({
                "index": int(idx),
                "rule": "holiday_billing",
                "severity": "LOW",
                "explanation": f"Work billed on federal holiday: {holiday_name} ({dt.strftime('%Y-%m-%d')})",
                "detail": str(row.get("description", ""))[:200],
            })
    return flags


def rule_staffing_level(df):
    """Flag senior partner hours on tasks typically done by associates/paralegals."""
    associate_tasks = [
        r'document\s+review', r'cite\s+check', r'proofread',
        r'bluebook', r'shepardiz', r'filing', r'bates\s+(stamp|label|number)',
        r'index\s+(document|exhibit)', r'organize\s+(file|document|exhibit)',
        r'prepare\s+index', r'copy', r'scan',
    ]
    partner_indicators = [
        r'partner', r'senior\s+counsel', r'of\s+counsel',
        r'shareholder', r'member', r'principal',
    ]
    combined_tasks = re.compile("|".join(associate_tasks), re.IGNORECASE)
    combined_partner = re.compile("|".join(partner_indicators), re.IGNORECASE)
    flags = []
    for idx, row in df.iterrows():
        tk = str(row.get("timekeeper", ""))
        desc = str(row.get("description", ""))
        rate = row.get("rate")
        # Detect senior-level timekeeper by name pattern or high rate
        is_senior = bool(combined_partner.search(tk))
        if not is_senior and pd.notna(rate) and rate > 500:
            is_senior = True
        if is_senior and combined_tasks.search(desc):
            flags.append({
                "index": int(idx),
                "rule": "staffing_level",
                "severity": "MEDIUM",
                "explanation": f"Senior timekeeper ({tk}) performing task typically done by junior staff",
                "detail": desc[:200],
            })
    return flags


def rule_rounding_patterns(df):
    """Detect entries consistently at round increments (0.5 or 1.0 hours)."""
    flags = []
    # Check per-timekeeper rounding patterns
    valid = df[df["hours"].notna()].copy()
    if valid.empty:
        return flags
    for tk, group in valid.groupby("timekeeper"):
        if len(group) < 5:
            continue
        hours_vals = group["hours"].values
        round_count = sum(1 for h in hours_vals if h == round(h) or abs(h % 0.5) < 1e-9)
        ratio = round_count / len(hours_vals)
        if ratio > 0.8 and len(hours_vals) >= 5:
            for idx in group.index:
                h = group.loc[idx, "hours"]
                if h == round(h) or abs(h % 0.5) < 1e-9:
                    flags.append({
                        "index": int(idx),
                        "rule": "rounding_pattern",
                        "severity": "LOW",
                        "explanation": f"Timekeeper {tk} shows rounding pattern ({ratio:.0%} of entries at 0.5/1.0h increments)",
                        "detail": f"{h}h - {str(group.loc[idx, 'description'])[:150]}",
                    })
    return flags


def rule_late_entries(df):
    """Flag entries dated significantly after the billing period."""
    flags = []
    valid = df[df["date"].notna()].copy()
    if valid.empty:
        return flags
    # Determine billing period: assume most entries cluster together
    median_date = valid["date"].median()
    std_days = (valid["date"] - median_date).dt.days.std()
    if pd.isna(std_days):
        return flags
    threshold = max(std_days * 2, 30)  # At least 30 days
    for idx, row in valid.iterrows():
        days_from_median = abs((row["date"] - median_date).days)
        if days_from_median > threshold:
            flags.append({
                "index": int(idx),
                "rule": "late_entry",
                "severity": "LOW",
                "explanation": f"Entry date {row['date'].strftime('%Y-%m-%d')} is {days_from_median} days from billing period center",
                "detail": str(row.get("description", ""))[:200],
            })
    return flags


# ---------------------------------------------------------------------------
# Analytics (DuckDB)
# ---------------------------------------------------------------------------

def run_analytics(df):
    """Run spend analytics using DuckDB."""
    analytics = {}
    con = duckdb.connect()
    con.register("billing", df)

    # Total spend
    result = con.execute("SELECT COALESCE(SUM(amount), 0) as total FROM billing WHERE amount IS NOT NULL").fetchone()
    analytics["total_spend"] = float(result[0])

    # Spend by matter
    try:
        result = con.execute("""
            SELECT matter, SUM(amount) as total, COUNT(*) as entries
            FROM billing
            WHERE amount IS NOT NULL AND matter != ''
            GROUP BY matter
            ORDER BY total DESC
            LIMIT 20
        """).fetchdf()
        analytics["spend_by_matter"] = result.to_dict(orient="records")
    except Exception:
        analytics["spend_by_matter"] = []

    # Spend by timekeeper
    try:
        result = con.execute("""
            SELECT timekeeper, SUM(amount) as total, SUM(hours) as total_hours,
                   AVG(rate) as avg_rate, COUNT(*) as entries
            FROM billing
            WHERE amount IS NOT NULL
            GROUP BY timekeeper
            ORDER BY total DESC
            LIMIT 20
        """).fetchdf()
        analytics["spend_by_timekeeper"] = result.to_dict(orient="records")
    except Exception:
        analytics["spend_by_timekeeper"] = []

    # Spend by month
    try:
        result = con.execute("""
            SELECT DATE_TRUNC('month', date) as month, SUM(amount) as total,
                   SUM(hours) as total_hours, COUNT(*) as entries
            FROM billing
            WHERE amount IS NOT NULL AND date IS NOT NULL
            GROUP BY DATE_TRUNC('month', date)
            ORDER BY month
        """).fetchdf()
        result["month"] = result["month"].astype(str)
        analytics["spend_by_month"] = result.to_dict(orient="records")
    except Exception:
        analytics["spend_by_month"] = []

    # Average rate by estimated level (based on rate ranges)
    try:
        result = con.execute("""
            SELECT
                CASE
                    WHEN rate > 500 THEN 'Senior Partner'
                    WHEN rate > 350 THEN 'Partner/Of Counsel'
                    WHEN rate > 250 THEN 'Senior Associate'
                    WHEN rate > 150 THEN 'Associate'
                    ELSE 'Paralegal/Other'
                END as level,
                AVG(rate) as avg_rate,
                COUNT(DISTINCT timekeeper) as timekeepers,
                SUM(hours) as total_hours,
                SUM(amount) as total_spend
            FROM billing
            WHERE rate IS NOT NULL
            GROUP BY 1
            ORDER BY avg_rate DESC
        """).fetchdf()
        analytics["rate_by_level"] = result.to_dict(orient="records")
    except Exception:
        analytics["rate_by_level"] = []

    # Hours distribution
    try:
        result = con.execute("""
            SELECT hours, COUNT(*) as count
            FROM billing
            WHERE hours IS NOT NULL
            GROUP BY hours
            ORDER BY hours
        """).fetchdf()
        analytics["hours_distribution"] = result.to_dict(orient="records")
    except Exception:
        analytics["hours_distribution"] = []

    # Top 10 most expensive entries
    try:
        result = con.execute("""
            SELECT date, timekeeper, hours, rate, amount, description
            FROM billing
            WHERE amount IS NOT NULL
            ORDER BY amount DESC
            LIMIT 10
        """).fetchdf()
        result["date"] = result["date"].astype(str)
        analytics["top_entries"] = result.to_dict(orient="records")
    except Exception:
        analytics["top_entries"] = []

    con.close()
    return analytics


# ---------------------------------------------------------------------------
# Visualizations (Plotly)
# ---------------------------------------------------------------------------

def create_dashboard(df, flags_df, analytics, output_dir):
    """Create interactive plotly dashboard."""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Spend Over Time",
            "Spend by Timekeeper (Top 10)",
            "Flagged Entries by Severity",
            "Hours Distribution",
        ),
        specs=[
            [{"type": "scatter"}, {"type": "bar"}],
            [{"type": "pie"}, {"type": "histogram"}],
        ],
    )

    # 1. Spend over time
    monthly = analytics.get("spend_by_month", [])
    if monthly:
        months = [m["month"][:10] for m in monthly]
        totals = [m["total"] for m in monthly]
        fig.add_trace(
            go.Scatter(x=months, y=totals, mode="lines+markers", name="Monthly Spend",
                       line=dict(color="#2563EB", width=2)),
            row=1, col=1
        )

    # 2. Spend by timekeeper
    by_tk = analytics.get("spend_by_timekeeper", [])[:10]
    if by_tk:
        names = [t["timekeeper"][:20] for t in by_tk]
        amounts = [t["total"] for t in by_tk]
        fig.add_trace(
            go.Bar(x=names, y=amounts, name="Spend by Timekeeper",
                   marker_color="#10B981"),
            row=1, col=2
        )

    # 3. Flagged entries by severity
    if not flags_df.empty and "severity" in flags_df.columns:
        severity_counts = flags_df["severity"].value_counts()
        colors = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#6B7280"}
        fig.add_trace(
            go.Pie(
                labels=severity_counts.index.tolist(),
                values=severity_counts.values.tolist(),
                marker_colors=[colors.get(s, "#999") for s in severity_counts.index],
                name="Severity",
            ),
            row=2, col=1
        )

    # 4. Hours distribution
    valid_hours = df[df["hours"].notna()]["hours"]
    if not valid_hours.empty:
        fig.add_trace(
            go.Histogram(x=valid_hours, nbinsx=30, name="Hours Distribution",
                         marker_color="#8B5CF6"),
            row=2, col=2
        )

    fig.update_layout(
        title_text="Legal Billing Audit Dashboard",
        height=800,
        showlegend=False,
        template="plotly_white",
    )
    fig.update_yaxes(title_text="Amount ($)", row=1, col=1)
    fig.update_yaxes(title_text="Amount ($)", row=1, col=2)
    fig.update_xaxes(title_text="Hours", row=2, col=2)

    output_path = os.path.join(output_dir, "spend_dashboard.html")
    fig.write_html(output_path, include_plotlyjs="cdn")
    log(f"  Dashboard saved: {output_path}")


# ---------------------------------------------------------------------------
# Output Generation
# ---------------------------------------------------------------------------

def write_flagged_xlsx(df, all_flags, output_dir):
    """Write flagged entries to Excel spreadsheet."""
    if not all_flags:
        # Write empty report
        empty_df = pd.DataFrame(columns=["severity", "rule", "explanation", "date", "timekeeper", "hours", "rate", "amount", "description"])
        empty_df.to_excel(os.path.join(output_dir, "flagged_entries.xlsx"), index=False, engine="xlsxwriter")
        return pd.DataFrame()

    # Build flagged dataframe
    rows = []
    for flag in all_flags:
        idx = flag["index"]
        entry = {}
        if idx < len(df):
            row = df.iloc[idx]
            entry["date"] = str(row.get("date", ""))[:10] if pd.notna(row.get("date")) else ""
            entry["timekeeper"] = str(row.get("timekeeper", ""))
            entry["hours"] = row.get("hours") if pd.notna(row.get("hours")) else ""
            entry["rate"] = row.get("rate") if pd.notna(row.get("rate")) else ""
            entry["amount"] = row.get("amount") if pd.notna(row.get("amount")) else ""
            entry["description"] = str(row.get("description", ""))[:300]
            entry["matter"] = str(row.get("matter", ""))
        entry["severity"] = flag["severity"]
        entry["rule"] = flag["rule"]
        entry["explanation"] = flag["explanation"]
        entry["detail"] = flag.get("detail", "")
        rows.append(entry)

    flags_df = pd.DataFrame(rows)
    # Sort by severity
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    flags_df["_sort"] = flags_df["severity"].map(severity_order)
    flags_df = flags_df.sort_values("_sort").drop(columns=["_sort"])

    output_path = os.path.join(output_dir, "flagged_entries.xlsx")
    flags_df.to_excel(output_path, index=False, engine="xlsxwriter")
    log(f"  Flagged entries saved: {output_path}")
    return flags_df


def write_audit_summary(df, all_flags, analytics, output_dir):
    """Write human-readable audit summary."""
    total_entries = len(df)
    total_spend = analytics.get("total_spend", 0)

    severity_counts = defaultdict(int)
    for f in all_flags:
        severity_counts[f["severity"]] += 1

    # Estimate savings: sum of amounts for HIGH severity flags
    high_amount = 0
    for f in all_flags:
        if f["severity"] == "HIGH":
            idx = f["index"]
            if idx < len(df):
                amt = df.iloc[idx].get("amount")
                if pd.notna(amt):
                    high_amount += float(amt)

    lines = [
        "=" * 60,
        "LEGAL BILLING AUDIT SUMMARY",
        "=" * 60,
        "",
        f"Total entries reviewed:    {total_entries:,}",
        f"Total spend analyzed:      ${total_spend:,.2f}",
        "",
        "FLAGS BY SEVERITY:",
        f"  HIGH:   {severity_counts.get('HIGH', 0):,}",
        f"  MEDIUM: {severity_counts.get('MEDIUM', 0):,}",
        f"  LOW:    {severity_counts.get('LOW', 0):,}",
        f"  TOTAL:  {len(all_flags):,}",
        "",
        f"Estimated savings (HIGH flags): ${high_amount:,.2f}",
        "",
        "FLAGS BY RULE:",
    ]

    rule_counts = defaultdict(int)
    for f in all_flags:
        rule_counts[f["rule"]] += 1
    for rule, count in sorted(rule_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {rule}: {count:,}")

    lines.extend([
        "",
        "TOP TIMEKEEPERS BY SPEND:",
    ])
    for tk in analytics.get("spend_by_timekeeper", [])[:5]:
        lines.append(f"  {tk['timekeeper']}: ${tk['total']:,.2f} ({tk.get('total_hours', 0):.1f}h)")

    lines.extend([
        "",
        "OUTPUT FILES:",
        "  flagged_entries.xlsx  - Detailed flagged entries spreadsheet",
        "  spend_dashboard.html  - Interactive spend dashboard (open in browser)",
        "  audit_report.json     - Structured audit data",
        "",
        "=" * 60,
    ])

    summary_text = "\n".join(lines)
    output_path = os.path.join(output_dir, "audit_summary.txt")
    with open(output_path, "w") as f:
        f.write(summary_text)
    log(f"  Summary saved: {output_path}")
    return summary_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Legal Billing Auditor")
    parser.add_argument("--input", required=True, help="Billing file or directory")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--rate-caps", help="JSON file with rate caps by timekeeper/level")
    parser.add_argument("--max-daily-hours", type=float, default=10.0, help="Max daily hours per timekeeper (default: 10)")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Load rate caps if provided
    rate_caps = {}
    if args.rate_caps:
        try:
            with open(args.rate_caps) as f:
                rate_caps = json.load(f)
            log(f"Loaded rate caps: {len(rate_caps)} entries")
        except Exception as e:
            log(f"WARNING: Could not load rate caps: {e}")

    # Discover and parse files
    log("Discovering billing files...")
    files_to_parse = []
    if os.path.isfile(input_path):
        files_to_parse = [input_path]
    elif os.path.isdir(input_path):
        for root, dirs, filenames in os.walk(input_path):
            for fn in filenames:
                ext = Path(fn).suffix.lower()
                if ext in (".xlsx", ".xls", ".csv", ".txt", ".ledes"):
                    fp = os.path.join(root, fn)
                    files_to_parse.append(fp)
    else:
        log(f"ERROR: Input path does not exist: {input_path}")
        sys.exit(1)

    if not files_to_parse:
        log("ERROR: No supported billing files found.")
        sys.exit(1)

    log(f"Found {len(files_to_parse)} file(s) to process")

    # Parse all files
    all_dfs = []
    parse_errors = []
    for fp in files_to_parse:
        try:
            df = parse_file(fp)
            if not df.empty:
                all_dfs.append(df)
            else:
                parse_errors.append(fp)
        except Exception as e:
            log(f"  ERROR parsing {fp}: {e}")
            parse_errors.append(fp)

    if not all_dfs:
        log("ERROR: No data could be parsed from any file.")
        sys.exit(1)

    # Combine and normalize
    log("Normalizing columns...")
    combined = pd.concat(all_dfs, ignore_index=True)
    df = normalize_columns(combined)
    log(f"Total entries: {len(df)}")

    # Run audit rules
    log("Running audit rules...")
    all_flags = []

    log("  Checking block billing...")
    all_flags.extend(rule_block_billing(df))

    log("  Checking vague descriptions...")
    all_flags.extend(rule_vague_description(df))

    log("  Checking excessive hours...")
    all_flags.extend(rule_excessive_hours(df, max_daily=args.max_daily_hours))

    log("  Checking rate violations...")
    all_flags.extend(rule_rate_violations(df, rate_caps))

    log("  Checking duplicate entries...")
    all_flags.extend(rule_duplicate_entries(df))

    log("  Checking weekend/holiday billing...")
    all_flags.extend(rule_weekend_holiday(df))

    log("  Checking staffing levels...")
    all_flags.extend(rule_staffing_level(df))

    log("  Checking rounding patterns...")
    all_flags.extend(rule_rounding_patterns(df))

    log("  Checking late entries...")
    all_flags.extend(rule_late_entries(df))

    # Deduplicate flags (same index + same rule)
    seen = set()
    unique_flags = []
    for f in all_flags:
        key = (f["index"], f["rule"])
        if key not in seen:
            seen.add(key)
            unique_flags.append(f)
    all_flags = unique_flags

    log(f"Total flags: {len(all_flags)}")

    # Run analytics
    log("Running spend analytics...")
    analytics = run_analytics(df)

    # Generate outputs
    log("Generating outputs...")
    flags_df = write_flagged_xlsx(df, all_flags, output_dir)
    create_dashboard(df, flags_df, analytics, output_dir)
    summary_text = write_audit_summary(df, all_flags, analytics, output_dir)

    # Write full audit report JSON
    report = {
        "total_entries": len(df),
        "total_spend": analytics.get("total_spend", 0),
        "files_processed": len(all_dfs),
        "files_failed": parse_errors,
        "flags": all_flags,
        "flag_counts": {
            "HIGH": sum(1 for f in all_flags if f["severity"] == "HIGH"),
            "MEDIUM": sum(1 for f in all_flags if f["severity"] == "MEDIUM"),
            "LOW": sum(1 for f in all_flags if f["severity"] == "LOW"),
            "total": len(all_flags),
        },
        "analytics": analytics,
    }
    report_path = os.path.join(output_dir, "audit_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"  Report saved: {report_path}")

    # Print JSON summary to stdout for Claude to parse
    summary_json = {
        "status": "success",
        "total_entries": len(df),
        "total_spend": analytics.get("total_spend", 0),
        "files_processed": len(all_dfs),
        "files_failed": parse_errors,
        "flag_counts": report["flag_counts"],
        "output_dir": output_dir,
        "outputs": {
            "audit_report": report_path,
            "flagged_entries": os.path.join(output_dir, "flagged_entries.xlsx"),
            "dashboard": os.path.join(output_dir, "spend_dashboard.html"),
            "summary": os.path.join(output_dir, "audit_summary.txt"),
        },
    }
    print(json.dumps(summary_json, indent=2, default=str))


if __name__ == "__main__":
    main()
