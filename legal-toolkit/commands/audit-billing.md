---
description: Audit legal billing data for block billing, excessive hours, rate violations, and compliance issues
argument-hint: "<billing file or directory>"
---

# /audit-billing -- Legal Billing Auditor

Audit law firm billing data (LEDES files, Excel invoices, CSV time entries) for compliance issues, block billing, excessive hours, rate violations, duplicate entries, and billing anomalies.

@$1

## Workflow

- **Validate** the input path (file or directory) and check for supported formats (.txt, .ledes, .xlsx, .csv)
- **Configure** optional rate caps file (JSON) for rate violation detection
- **Audit** billing data using the `audit-billing` skill's Python script, applying compliance rules and anomaly detection
- **Present** findings: total entries reviewed, total spend, flags by severity (HIGH/MEDIUM/LOW), estimated potential savings, and detailed HIGH-severity flag explanations
- **Generate** output files: flagged_entries.xlsx, spend_dashboard.html (interactive charts), audit_report.json
- Refer to the `audit-billing` skill (SKILL.md) for audit rules, rate cap configuration, and formal audit report generation
