---
name: search-records
description: "Research SEC EDGAR public filings for companies, extracting financial data, officer/director information, risk factors, and filing histories. Generates research reports with financial trend charts. Use when: (1) a user needs to research a company's public filings or SEC records, (2) a user says 'research this company', 'find SEC filings', 'look up EDGAR records', 'company financials', 'who are the officers', or 'public records search', (3) any corporate due diligence or litigation research task involving SEC data, (4) a user needs financial trends, officer lists, or risk factor analysis from public filings."
---

# Public Records Researcher

Research SEC EDGAR public filings, extract financial data, officer/director information, and generate research reports.

**Data source**: SEC EDGAR (Electronic Data Gathering, Analysis, and Retrieval)
**Filing types**: 10-K, 10-Q, 8-K, DEF 14A, S-1, and others

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a company name or CIK number. If not, ask: "Please provide the company name or SEC CIK number you want to research."
2. Optionally collect:
   - **Filing types** to search (default: all major types)
   - **Number of years** to look back (default: 5)
3. Validate CIK is numeric if provided.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).

### Step 3: Run Records Researcher

```bash
WORK_DIR="$(pwd)/legal-records-$(date +%s)"
mkdir -p "$WORK_DIR"
```

```bash
python3 "$SKILL_DIR/scripts/research_records.py" \
  --company "<company_name>" \
  --output-dir "$WORK_DIR" \
  [--cik <number>] \
  [--filing-types 10-K,10-Q] \
  [--years 5]
```

The script outputs JSON to stdout with the research results.

### Step 4: Present Results

1. Read `$WORK_DIR/research_summary.txt` and present the research findings to the user.
2. Highlight key findings:
   - Company identification (name, CIK, SIC code, state of incorporation)
   - Number and types of filings found
   - Key officers and directors
   - Financial highlights (revenue, net income trends)
   - Notable risk factors
3. Inform the user that the following files were generated:
   - `company_profile.json` - structured company data
   - `filings_list.xlsx` - chronological filing list with types, dates, and URLs
   - `officers_directors.xlsx` - officer and director information
   - `financial_trends.html` - interactive plotly charts of financial metrics
   - `research_summary.txt` - human-readable research report

### Step 5: Offer Additional Actions

- **View financial charts**: Point user to `$WORK_DIR/financial_trends.html` to open in browser
- **DOCX report**: Offer to generate a formal research report (.docx) using the npm `docx` package
- **Deep dive**: If user wants details on a specific filing, offer to retrieve and analyze it
- **Refine search**: If user wants different filing types or time period, loop back to Step 3


## Accuracy and QA (Required)

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, invoke `/legal-toolkit:qa-check` on the work/output directory. Do not skip this step.

## Error Handling

- **Company not found**: Suggest checking the spelling or using the CIK number directly
- **No filings found**: The company may not have SEC filings (private company); inform the user
- **Network error**: SEC EDGAR requires internet access; ask user to check connectivity
- **Rate limiting**: SEC EDGAR has rate limits; the script handles retries automatically
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
