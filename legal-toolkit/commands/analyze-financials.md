---
description: Forensic financial analysis of bank statements and transaction records with money flow tracing and anomaly detection
argument-hint: "<bank statement file or directory>"
---

# /analyze-financials -- Financial Forensics Toolkit

Ingest bank statements and transaction records, trace money flows between entities, detect anomalies (structuring, rapid in-out, unusual timing), and generate interactive Sankey diagrams and transaction timelines.

@$1

## Workflow

- **Validate** the input path (file or directory) and check for supported formats (.csv, .xlsx, .ofx, .qfx)
- **Configure** optional reporting threshold (default $10,000) and date range filter
- **Analyze** financial data using the `analyze-financials` skill's Python script for entity identification, flow tracing, and anomaly detection
- **Present** findings: accounts analyzed, transaction volume, unique entities, flagged anomalies with risk indicators and specific transactions involved
- **Generate** output files: money_flow.html (interactive Sankey diagram), transaction_timeline.html, entity_summary.xlsx, financial_analysis.json
- Refer to the `analyze-financials` skill (SKILL.md) for threshold configuration, anomaly types, and formal forensic report generation
