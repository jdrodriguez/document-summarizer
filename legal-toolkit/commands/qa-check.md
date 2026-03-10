---
description: QA review and anti-hallucination check for legal-toolkit outputs
argument-hint: "<work directory or output directory path>"
---

# /qa-check -- QA Review & Anti-Hallucination Check

Run a QA review on legal-toolkit skill output before presenting to the user. Reads all output files and source materials, verifies factual claims, checks for hallucinated citations and unsourced facts, and produces a severity-rated review.

@$1

Examples:
- `/legal-toolkit:qa-check ~/cases/johnson-dui/johnson_trial_prep_work/`
- `/legal-toolkit:qa-check ~/cases/discovery_work/`
- `/legal-toolkit:qa-check ./output_dir`

## Workflow

- **Read source materials**: case_materials.md or original input files
- **Read all output files**: section files, analysis files, reports
- **Run 6 checks**: source grounding, citation integrity, spot-check 10+ factual claims, consistency, completeness, formatting
- **Write qa_review.md**: severity-rated issues with fixes for CRITICAL/MAJOR
- **Report**: PASS, PASS WITH FIXES, or FAIL
- Refer to the `qa-review` skill (SKILL.md) for the full QA protocol
