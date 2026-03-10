---
name: analyze-financials
description: "Forensic financial analysis of bank statements and transaction records. Traces money flows between entities, detects anomalies (structuring, rapid in-out, unusual timing), and generates interactive visualizations. Use when: (1) a user provides bank statements or transaction data and asks for analysis, (2) a user says 'analyze these transactions', 'trace the money', 'follow the money flow', 'check for suspicious transactions', or 'forensic financial analysis', (3) any task involving bank statement review, transaction tracing, money flow mapping, or financial anomaly detection, (4) a user wants to understand where money went, identify suspicious patterns, or map entity relationships from financial data."
---

# Financial Forensics Toolkit

Ingest bank statements and transaction records, trace money flows, detect anomalies, and generate forensic analysis.

**Supported formats**: CSV (`.csv`), Excel (`.xlsx`), OFX/QFX (`.ofx`, `.qfx`)
**Input modes**: single file OR a directory containing multiple statement files

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path to financial data. If not, ask: "Please provide the path to the bank statement or transaction file(s) you want analyzed."
2. Determine if the path is a file or directory:
   - **File**: verify it exists and has a supported extension (`.csv`, `.xlsx`, `.ofx`, `.qfx`)
   - **Directory**: verify it exists; the script will find all supported files inside it
3. If a directory, tell the user which files were found before proceeding.
4. Ask if they want to set a reporting threshold (default: $10,000) or date range filter.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).

### Step 3: Run Financial Analysis

Determine the output directory:
- **Single file**: `OUTPUT_DIR="{parent_dir}/{filename_without_ext}_analysis"`
- **Directory**: `OUTPUT_DIR="{directory_path}/_forensic_analysis"`

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/analyze_financials.py" \
  --input "<file_or_directory_path>" \
  --output-dir "$OUTPUT_DIR" \
  [--threshold 10000] \
  [--date-range "2025-01-01:2025-12-31"]
```

The script prints a JSON summary to stdout. Capture and parse it.

### Step 4: Present Analysis Summary

Read the output files and present findings to the user:

1. **Start with the overview**: Read `$OUTPUT_DIR/analysis_summary.txt` and present:
   - Total accounts analyzed
   - Date range covered
   - Total transaction volume (inflows + outflows)
   - Number of unique entities identified
   - Number of anomalies flagged

2. **Highlight key anomalies**: For each flagged anomaly, explain:
   - What was detected and why it is noteworthy
   - The specific transactions involved
   - The risk indicator or pattern matched

3. **Entity summary**: Top entities by transaction volume with net flows.

### Step 5: Direct to Interactive Visualizations

Tell the user about the generated files:
- `money_flow.html` - Interactive Sankey diagram showing money flows between entities (open in browser)
- `transaction_timeline.html` - Scatter plot of transactions over time with anomaly markers
- `entity_summary.xlsx` - All entities with inflows, outflows, net, and transaction counts
- `financial_analysis.json` - Structured data for further processing

### Step 6: Offer Formal Report

Ask: "Would you like me to generate a formal forensic analysis report as a Word document (.docx)?"

If yes, use the npm `docx` package to generate a professional report containing:
1. **Title page**: "Forensic Financial Analysis Report", date, case information
2. **Executive Summary**: Key findings and risk indicators
3. **Methodology**: Analysis techniques applied
4. **Account Overview**: Accounts analyzed, date ranges, volumes
5. **Money Flow Analysis**: Entity relationships and major flows
6. **Anomaly Report**: All flagged transactions grouped by type
7. **Entity Profiles**: Top entities with transaction summaries
8. **Appendix**: Full transaction listing and data sources

## Error Handling

- **Path not found**: Ask user to verify the path
- **Unsupported format**: Supported types are `.csv`, `.xlsx`, `.ofx`, `.qfx`
- **Empty directory**: No supported files found -- ask user to check the folder
- **Parse errors**: Some files may have non-standard formats; report which files failed and continue with others
- **No anomalies found**: Report clean analysis -- no suspicious patterns detected
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
