---
description: Analyze attorney caseloads with complexity weighting, overload flags, and redistribution recommendations
argument-hint: "<attorney roster, caseload data, or staffing details>"
---

# /attorney-workload -- Attorney Workload Analyzer

Analyze attorney workloads across the firm using case data and complexity weighting. Produces a capacity report per attorney with overload flags, redistribution recommendations, and hiring trigger analysis so firm leadership can balance work before burnout hits.

@$1

## Workflow

- **Detect input format** -- if the user provides a spreadsheet or data file (.xlsx, .csv, .json), read and parse it; if they paste text or describe their caseload, extract structured data directly
- **Classify** each case by assigned attorney, case type, current stage, and complexity indicators
- **Calculate** complexity-weighted loads using case type weights and stage multipliers
- **Produce** the full capacity report: firm-wide summary, per-attorney capacity table with Green/Yellow/Red status, stage distribution analysis, overload flags, redistribution recommendations, and hiring trigger analysis
- Refer to the `analyze-workload` skill (SKILL.md) for capacity formulas, complexity weighting tables, and stage multipliers
