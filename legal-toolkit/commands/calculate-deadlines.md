---
description: Calculate court litigation deadlines with FRCP Rule 6 compliance, holiday handling, and calendar export
argument-hint: "<case details: trigger date, jurisdiction, event type>"
---

# /calculate-deadlines -- Court Deadline Calculator

Calculate litigation deadlines with FRCP Rule 6 compliance, jurisdiction-aware holiday and business day handling, service method adjustments, and cascading deadline chains. Exports to .ics calendar files.

@$1

## Workflow

- **Collect** case details: trigger date (YYYY-MM-DD), jurisdiction (federal, CA, NY, TX, FL, IL), event type (complaint_served, motion_filed, discovery_request, summary_judgment, appeal_filed), and service method
- **Calculate** all applicable deadlines using the `calculate-deadlines` skill's Python script with FRCP Rule 6 compliance
- **Present** the deadline schedule with rule citations and generate output files (deadlines.json, deadlines.ics, deadline_report.txt)
- **Offer** calendar import via .ics file and optional formal .docx report generation
- Refer to the `calculate-deadlines` skill (SKILL.md) for input JSON format, supported jurisdictions, and custom deadline options
