---
description: Search SEC EDGAR public filings for company financials, officers, risk factors, and filing histories
argument-hint: "<company name or CIK number>"
---

# /edgar-search -- Public Records Researcher

Research SEC EDGAR public filings for companies, extracting financial data, officer/director information, risk factors, and filing histories. Generates research reports with interactive financial trend charts.

@$1

## Workflow

- **Validate** the company name or CIK number, and optionally collect filing types and lookback period
- **Search** SEC EDGAR using the `search-records` skill's Python script to retrieve company profile, filings, and financial data
- **Present** findings: company identification, filing summary, key officers/directors, financial highlights, and notable risk factors
- **Generate** output files: company_profile.json, filings_list.xlsx, officers_directors.xlsx, financial_trends.html (interactive charts)
- Refer to the `search-records` skill (SKILL.md) for supported filing types, search parameters, and deep-dive options
