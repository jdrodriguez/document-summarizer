#!/usr/bin/env python3
"""
Public records researcher for the legal-records skill.

Queries SEC EDGAR for public filings, extracts financial data, officer/director
information, and generates research reports with financial trend charts.

Usage:
    python3 research_records.py --company "<name>" --output-dir <dir> \
        [--cik <number>] [--filing-types 10-K,10-Q] [--years 5]
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Dependency imports
# ---------------------------------------------------------------------------
try:
    from edgar import Company, set_identity
except ImportError:
    print("ERROR: 'edgartools' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

try:
    import pandas as pd
except ImportError:
    print("ERROR: 'pandas' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    print("ERROR: 'plotly' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

try:
    import xlsxwriter
except ImportError:
    print("ERROR: 'XlsxWriter' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_FILING_TYPES = ["10-K", "10-Q", "8-K", "DEF 14A", "S-1"]
ALL_FILING_TYPES = [
    "10-K", "10-Q", "8-K", "DEF 14A", "S-1", "S-3", "S-4",
    "424B2", "424B4", "SC 13D", "SC 13G", "4", "3",
    "13F-HR", "20-F", "6-K", "N-CSR",
]

# Set a user agent identity for SEC EDGAR compliance.
# Users should set the EDGAR_EMAIL environment variable to their own email.
EDGAR_IDENTITY = "LegalRecordsResearcher " + os.environ.get("EDGAR_EMAIL", "set-EDGAR_EMAIL-env-var@example.com")


# ---------------------------------------------------------------------------
# Company lookup and data retrieval
# ---------------------------------------------------------------------------
def lookup_company(company_name: str, cik: Optional[int] = None) -> Optional[object]:
    """Look up a company on SEC EDGAR."""
    set_identity(EDGAR_IDENTITY)

    try:
        if cik:
            print(f"Looking up CIK {cik}...", file=sys.stderr)
            company = Company(cik)
        else:
            print(f"Searching for '{company_name}'...", file=sys.stderr)
            company = Company(company_name)

        if company:
            print(f"  Found: {company.name} (CIK: {company.cik})", file=sys.stderr)
            return company
    except Exception as e:
        print(f"  Company lookup failed: {e}", file=sys.stderr)

    return None


def get_company_profile(company: object) -> dict:
    """Extract company profile information."""
    profile = {
        "name": getattr(company, "name", "Unknown"),
        "cik": str(getattr(company, "cik", "")),
        "sic": getattr(company, "sic", None),
        "sic_description": getattr(company, "sic_description", None),
        "state_of_incorporation": getattr(company, "state_of_incorporation", None),
        "fiscal_year_end": getattr(company, "fiscal_year_end", None),
        "tickers": [],
        "exchanges": [],
    }

    # Try to get ticker information
    try:
        tickers = getattr(company, "tickers", [])
        if tickers:
            profile["tickers"] = list(tickers) if not isinstance(tickers, list) else tickers
    except Exception:
        pass

    try:
        exchanges = getattr(company, "exchanges", [])
        if exchanges:
            profile["exchanges"] = list(exchanges) if not isinstance(exchanges, list) else exchanges
    except Exception:
        pass

    return profile


def get_filings(company: object, filing_types: list[str], years: int) -> list[dict]:
    """Retrieve filings for a company."""
    filings_list = []
    cutoff_date = datetime.now() - timedelta(days=years * 365)

    try:
        filings = company.get_filings()
        if not filings:
            return filings_list

        print(f"  Processing filings...", file=sys.stderr)
        count = 0

        for filing in filings:
            # Check if we've gone past our date range
            try:
                filing_date_str = str(getattr(filing, "filing_date", ""))
                if filing_date_str:
                    filing_date = datetime.strptime(filing_date_str[:10], "%Y-%m-%d")
                    if filing_date < cutoff_date:
                        break
                else:
                    filing_date = None
                    filing_date_str = ""
            except (ValueError, TypeError):
                filing_date = None
                filing_date_str = str(getattr(filing, "filing_date", ""))

            # Check filing type
            form_type = str(getattr(filing, "form_type", ""))
            if filing_types and form_type not in filing_types:
                continue

            # Extract filing data
            accession_number = str(getattr(filing, "accession_number", ""))
            primary_document = str(getattr(filing, "primary_document", ""))

            filing_url = ""
            if accession_number:
                acc_clean = accession_number.replace("-", "")
                cik_str = str(getattr(company, "cik", "")).zfill(10)
                filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik_str}/{acc_clean}/{primary_document}"

            filing_entry = {
                "form_type": form_type,
                "filing_date": filing_date_str[:10] if filing_date_str else "",
                "accession_number": accession_number,
                "primary_document": primary_document,
                "url": filing_url,
                "description": str(getattr(filing, "description", "")),
            }
            filings_list.append(filing_entry)
            count += 1

            # Rate limiting
            if count % 50 == 0:
                print(f"  Processed {count} filings...", file=sys.stderr)
                time.sleep(0.2)

        print(f"  Total filings retrieved: {len(filings_list)}", file=sys.stderr)

    except Exception as e:
        print(f"  Error retrieving filings: {e}", file=sys.stderr)

    return filings_list


def extract_officers_directors(company: object) -> list[dict]:
    """Extract officer and director information."""
    officers = []

    # Try to get from company object directly
    try:
        # edgartools may provide officers via company data
        company_data = getattr(company, "company_data", None)
        if company_data and hasattr(company_data, "get"):
            former_names = company_data.get("formerNames", [])
            # This is just placeholder - actual officer data comes from filings
    except Exception:
        pass

    # Try to extract from recent DEF 14A or 10-K filings
    try:
        filings = company.get_filings(form="DEF 14A")
        if filings:
            for filing in filings:
                try:
                    # Try multiple approaches to get filing text
                    text = None
                    try:
                        text = filing.text()[:50000]
                    except (AttributeError, TypeError):
                        pass
                    if text is None:
                        try:
                            text = str(filing.obj())[:50000]
                        except Exception:
                            pass
                    if text:
                        extracted = extract_names_from_text(text)
                        for name_info in extracted:
                            if name_info not in officers:
                                officers.append(name_info)
                    else:
                        print(f"  Could not extract text from DEF 14A filing; skipping officer extraction.", file=sys.stderr)
                except Exception as e:
                    print(f"  Error extracting officers from filing: {e}", file=sys.stderr)
                break  # Only process most recent proxy
    except Exception as e:
        print(f"  Could not extract officers/directors: {e}", file=sys.stderr)

    return officers


def extract_names_from_text(text: str) -> list[dict]:
    """Extract officer/director names from filing text using pattern matching."""
    results = []

    # Common title patterns
    title_patterns = [
        r"(?:Chief Executive Officer|CEO)",
        r"(?:Chief Financial Officer|CFO)",
        r"(?:Chief Operating Officer|COO)",
        r"(?:Chief Technology Officer|CTO)",
        r"(?:President)",
        r"(?:Chairman|Chair of the Board)",
        r"(?:Vice President|VP)",
        r"(?:Secretary)",
        r"(?:Treasurer)",
        r"(?:Director)",
        r"(?:General Counsel)",
    ]

    for pattern in title_patterns:
        # Look for "Name, Title" or "Name - Title" patterns
        regex = re.compile(
            r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr\.|Sr\.|III|IV|II))?)"
            r"[\s,\-]+(?:" + pattern + r")",
            re.IGNORECASE
        )
        for match in regex.finditer(text):
            name = match.group(1).strip()
            title_match = re.search(pattern, match.group(0), re.IGNORECASE)
            title = title_match.group(0) if title_match else ""

            entry = {"name": name, "title": title}
            if entry not in results and len(name) > 3:
                results.append(entry)

    return results[:50]  # Limit to 50 entries


def extract_financial_data(company: object, years: int) -> list[dict]:
    """Extract financial data from annual reports."""
    financials = []

    try:
        filings = company.get_filings(form="10-K")
        if not filings:
            return financials

        count = 0
        for filing in filings:
            if count >= years:
                break

            try:
                filing_date = str(getattr(filing, "filing_date", ""))[:10]
                year = filing_date[:4] if filing_date else "Unknown"

                financial_entry = {
                    "year": year,
                    "filing_date": filing_date,
                    "revenue": None,
                    "net_income": None,
                    "total_assets": None,
                    "total_liabilities": None,
                    "stockholders_equity": None,
                }

                # Try to extract financial data from XBRL
                # Note: edgartools returns DataFrames, not objects with attribute access.
                # This extraction requires a specific edgartools version and may not work
                # with all versions.
                try:
                    filing_obj = filing.obj()
                    if hasattr(filing_obj, "financials"):
                        fin = filing_obj.financials
                        if hasattr(fin, "income_statement"):
                            is_data = fin.income_statement
                            financial_entry["revenue"] = getattr(is_data, "revenue", None)
                            financial_entry["net_income"] = getattr(is_data, "net_income", None)
                        if hasattr(fin, "balance_sheet"):
                            bs_data = fin.balance_sheet
                            financial_entry["total_assets"] = getattr(bs_data, "total_assets", None)
                            financial_entry["total_liabilities"] = getattr(bs_data, "total_liabilities", None)
                            financial_entry["stockholders_equity"] = getattr(bs_data, "stockholders_equity", None)
                except Exception as e:
                    print(f"  Financial data extraction failed for {year}: {e}. "
                          f"Financial extraction requires specific edgartools version.", file=sys.stderr)

                financials.append(financial_entry)
                count += 1
                time.sleep(0.3)  # Rate limiting

            except Exception as e:
                print(f"  Error processing 10-K filing: {e}", file=sys.stderr)
                count += 1

    except Exception as e:
        print(f"  Error extracting financial data: {e}", file=sys.stderr)

    return financials


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------
def write_company_profile(profile: dict, filings_count: int, output_dir: str):
    """Write company profile JSON."""
    profile["total_filings_retrieved"] = filings_count
    path = os.path.join(output_dir, "company_profile.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    print(f"Written: {path}", file=sys.stderr)


def write_filings_list(filings: list[dict], output_dir: str):
    """Write filings list to Excel spreadsheet."""
    path = os.path.join(output_dir, "filings_list.xlsx")
    workbook = xlsxwriter.Workbook(path)
    worksheet = workbook.add_worksheet("Filings")

    # Formats
    header_fmt = workbook.add_format({
        "bold": True, "bg_color": "#1B4F72", "font_color": "#FFFFFF",
        "border": 1, "text_wrap": True,
    })
    cell_fmt = workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"})
    url_fmt = workbook.add_format({
        "border": 1, "text_wrap": True, "valign": "top",
        "font_color": "#2980B9", "underline": True,
    })

    headers = ["#", "Form Type", "Filing Date", "Description", "Accession Number", "URL"]
    widths = [5, 12, 12, 50, 25, 60]

    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_fmt)
        worksheet.set_column(col, col, widths[col])

    for row_idx, filing in enumerate(filings, 1):
        worksheet.write(row_idx, 0, row_idx, cell_fmt)
        worksheet.write(row_idx, 1, filing.get("form_type", ""), cell_fmt)
        worksheet.write(row_idx, 2, filing.get("filing_date", ""), cell_fmt)
        worksheet.write(row_idx, 3, filing.get("description", ""), cell_fmt)
        worksheet.write(row_idx, 4, filing.get("accession_number", ""), cell_fmt)
        url = filing.get("url", "")
        if url:
            worksheet.write_url(row_idx, 5, url, url_fmt, string=url[:60])
        else:
            worksheet.write(row_idx, 5, "", cell_fmt)

    worksheet.autofilter(0, 0, len(filings), len(headers) - 1)
    workbook.close()
    print(f"Written: {path}", file=sys.stderr)


def write_officers_directors(officers: list[dict], output_dir: str):
    """Write officers and directors to Excel spreadsheet."""
    path = os.path.join(output_dir, "officers_directors.xlsx")
    workbook = xlsxwriter.Workbook(path)
    worksheet = workbook.add_worksheet("Officers & Directors")

    header_fmt = workbook.add_format({
        "bold": True, "bg_color": "#1B4F72", "font_color": "#FFFFFF",
        "border": 1, "text_wrap": True,
    })
    cell_fmt = workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"})

    headers = ["#", "Name", "Title"]
    widths = [5, 30, 40]

    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_fmt)
        worksheet.set_column(col, col, widths[col])

    for row_idx, officer in enumerate(officers, 1):
        worksheet.write(row_idx, 0, row_idx, cell_fmt)
        worksheet.write(row_idx, 1, officer.get("name", ""), cell_fmt)
        worksheet.write(row_idx, 2, officer.get("title", ""), cell_fmt)

    workbook.close()
    print(f"Written: {path}", file=sys.stderr)


def write_financial_trends(financials: list[dict], company_name: str, output_dir: str):
    """Write interactive Plotly financial trend charts."""
    if not financials:
        print("  No financial data available; skipping chart generation.", file=sys.stderr)
        return

    # Filter to entries with some data
    valid = [f for f in financials if any(
        f.get(k) is not None for k in ["revenue", "net_income", "total_assets"]
    )]

    if not valid:
        print("  No parseable financial data; skipping chart generation.", file=sys.stderr)
        return

    valid.sort(key=lambda x: x.get("year", "0"))

    years = [f["year"] for f in valid]

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Revenue", "Net Income", "Total Assets", "Stockholders' Equity"),
        vertical_spacing=0.12,
        horizontal_spacing=0.1,
    )

    metrics = [
        ("revenue", 1, 1, "#2ECC71"),
        ("net_income", 1, 2, "#3498DB"),
        ("total_assets", 2, 1, "#E74C3C"),
        ("stockholders_equity", 2, 2, "#F39C12"),
    ]

    for metric, row, col, color in metrics:
        values = [f.get(metric) for f in valid]
        # Convert to float, handling None
        float_values = []
        for v in values:
            if v is not None:
                try:
                    float_values.append(float(v))
                except (ValueError, TypeError):
                    float_values.append(None)
            else:
                float_values.append(None)

        fig.add_trace(
            go.Bar(
                x=years,
                y=float_values,
                name=metric.replace("_", " ").title(),
                marker_color=color,
            ),
            row=row, col=col,
        )

    fig.update_layout(
        title_text=f"Financial Trends: {company_name}",
        showlegend=False,
        height=700,
        template="plotly_white",
    )

    path = os.path.join(output_dir, "financial_trends.html")
    fig.write_html(path, include_plotlyjs=True)
    print(f"Written: {path}", file=sys.stderr)


def write_research_summary(
    profile: dict,
    filings: list[dict],
    officers: list[dict],
    financials: list[dict],
    output_dir: str,
):
    """Write human-readable research summary."""
    lines = []
    lines.append("=" * 72)
    lines.append("SEC EDGAR PUBLIC RECORDS RESEARCH REPORT")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Company:               {profile.get('name', 'Unknown')}")
    lines.append(f"CIK:                   {profile.get('cik', 'N/A')}")
    lines.append(f"SIC Code:              {profile.get('sic', 'N/A')} - {profile.get('sic_description', '')}")
    lines.append(f"State of Incorporation: {profile.get('state_of_incorporation', 'N/A')}")
    lines.append(f"Fiscal Year End:       {profile.get('fiscal_year_end', 'N/A')}")

    tickers = profile.get("tickers", [])
    if tickers:
        lines.append(f"Ticker(s):             {', '.join(str(t) for t in tickers)}")

    exchanges = profile.get("exchanges", [])
    if exchanges:
        lines.append(f"Exchange(s):           {', '.join(str(e) for e in exchanges)}")

    lines.append(f"Total Filings Found:   {len(filings)}")
    lines.append(f"Report Generated:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Filing type breakdown
    if filings:
        lines.append("-" * 72)
        lines.append("FILING BREAKDOWN")
        lines.append("-" * 72)
        type_counts = {}
        for f in filings:
            ft = f.get("form_type", "Unknown")
            type_counts[ft] = type_counts.get(ft, 0) + 1
        for ft, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {ft:20s} {count:5d}")
        lines.append("")

    # Recent filings
    if filings:
        lines.append("-" * 72)
        lines.append("RECENT FILINGS (Last 10)")
        lines.append("-" * 72)
        for filing in filings[:10]:
            lines.append(f"  {filing.get('filing_date', ''):12s} {filing.get('form_type', ''):12s} {filing.get('description', '')[:50]}")
        lines.append("")

    # Officers and Directors
    if officers:
        lines.append("-" * 72)
        lines.append("OFFICERS AND DIRECTORS")
        lines.append("-" * 72)
        for officer in officers:
            lines.append(f"  {officer.get('name', ''):30s} {officer.get('title', '')}")
        lines.append("")

    # Financial highlights
    if financials:
        valid_fin = [f for f in financials if f.get("revenue") is not None]
        if valid_fin:
            lines.append("-" * 72)
            lines.append("FINANCIAL HIGHLIGHTS")
            lines.append("-" * 72)
            for f in valid_fin:
                lines.append(f"  Year {f.get('year', '?')}:")
                if f.get("revenue") is not None:
                    lines.append(f"    Revenue:             ${format_number(f['revenue'])}")
                if f.get("net_income") is not None:
                    lines.append(f"    Net Income:          ${format_number(f['net_income'])}")
                if f.get("total_assets") is not None:
                    lines.append(f"    Total Assets:        ${format_number(f['total_assets'])}")
                if f.get("stockholders_equity") is not None:
                    lines.append(f"    Stockholders Equity: ${format_number(f['stockholders_equity'])}")
                lines.append("")

    lines.append("-" * 72)
    lines.append("OUTPUT FILES")
    lines.append("-" * 72)
    lines.append("  company_profile.json     - Structured company data")
    lines.append("  filings_list.xlsx        - Chronological filing list")
    lines.append("  officers_directors.xlsx   - Officer and director information")
    lines.append("  financial_trends.html     - Interactive financial charts")
    lines.append("  research_summary.txt      - This summary")
    lines.append("")
    lines.append("  DISCLAIMER: This report is based on publicly available SEC EDGAR data.")
    lines.append("  Verify all information against original filings before use in legal proceedings.")
    lines.append("  Financial data may be approximate due to XBRL parsing limitations.")
    lines.append("")
    lines.append("=" * 72)

    path = os.path.join(output_dir, "research_summary.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Written: {path}", file=sys.stderr)


def format_number(value) -> str:
    """Format a number with commas and handle large values."""
    if value is None:
        return "N/A"
    try:
        num = float(value)
        if abs(num) >= 1_000_000_000:
            return f"{num / 1_000_000_000:,.2f}B"
        elif abs(num) >= 1_000_000:
            return f"{num / 1_000_000:,.2f}M"
        elif abs(num) >= 1_000:
            return f"{num / 1_000:,.2f}K"
        else:
            return f"{num:,.2f}"
    except (ValueError, TypeError):
        return str(value)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Research SEC EDGAR public filings for a company."
    )
    parser.add_argument("--company", required=True, help="Company name to search")
    parser.add_argument("--output-dir", required=True, help="Directory for output files")
    parser.add_argument("--cik", type=int, default=None, help="SEC CIK number (optional)")
    parser.add_argument("--filing-types", default=None,
                        help="Comma-separated filing types (default: 10-K,10-Q,8-K,DEF 14A,S-1)")
    parser.add_argument("--years", type=int, default=5, help="Number of years to look back (default: 5)")
    args = parser.parse_args()

    output_dir = os.path.abspath(args.output_dir)
    company_name = args.company
    cik = args.cik
    years = args.years

    filing_types = DEFAULT_FILING_TYPES
    if args.filing_types:
        filing_types = [ft.strip() for ft in args.filing_types.split(",")]

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Look up company
    company = lookup_company(company_name, cik)
    if not company:
        print(json.dumps({
            "error": f"Company not found: {company_name}",
            "suggestion": "Try using the exact company name or provide a CIK number with --cik",
        }))
        sys.exit(1)

    # Get company profile
    print("Extracting company profile...", file=sys.stderr)
    profile = get_company_profile(company)

    # Get filings
    print(f"Retrieving filings (last {years} years)...", file=sys.stderr)
    filings = get_filings(company, filing_types, years)

    # Extract officers/directors
    print("Extracting officers and directors...", file=sys.stderr)
    officers = extract_officers_directors(company)

    # Extract financial data
    print("Extracting financial data from annual reports...", file=sys.stderr)
    financials = extract_financial_data(company, years)

    # Write outputs
    print("Generating output files...", file=sys.stderr)
    write_company_profile(profile, len(filings), output_dir)
    write_filings_list(filings, output_dir)
    write_officers_directors(officers, output_dir)
    write_financial_trends(financials, profile.get("name", company_name), output_dir)
    write_research_summary(profile, filings, officers, financials, output_dir)

    # Filing type breakdown for summary
    type_counts = {}
    for f in filings:
        ft = f.get("form_type", "Unknown")
        type_counts[ft] = type_counts.get(ft, 0) + 1

    # Print summary JSON to stdout for Claude to parse
    print(json.dumps({
        "status": "success",
        "company_name": profile.get("name", company_name),
        "cik": profile.get("cik"),
        "total_filings": len(filings),
        "filing_type_breakdown": type_counts,
        "officers_directors_found": len(officers),
        "financial_years_available": len(financials),
        "output_dir": output_dir,
        "files": [
            "company_profile.json",
            "filings_list.xlsx",
            "officers_directors.xlsx",
            "financial_trends.html",
            "research_summary.txt",
        ],
    }))


if __name__ == "__main__":
    main()
