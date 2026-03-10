---
description: Surface firm performance KPIs, trends, and anomaly flags from case data exports
argument-hint: "<case data spreadsheet, CRM export, or case details>"
---

# /firm-kpis -- Performance Data Surfacer

Transform raw case data into a structured performance dashboard with KPIs, period-over-period comparisons, and anomaly flags. Works with CSV, XLSX, PDF exports, or pasted data from any practice management system.

@$1

## Workflow

- **Detect input format** -- if the user provided a spreadsheet (CSV, XLSX), PDF, or text, parse and extract the case data accordingly
- **Validate data** -- identify available fields (dates, case types, dispositions, revenue, attorneys, referral sources) and flag what is missing
- **Analyze** -- produce a structured performance report covering case volume, resolution time, dispositions, revenue, intake conversion, source ROI, and anomaly flags
- **Present** -- format with executive summary first, then detailed tables; bold significant changes; skip sections where data is unavailable
- Refer to the `surface-performance` skill (SKILL.md) for KPI definitions, dashboard templates, and analysis rules
