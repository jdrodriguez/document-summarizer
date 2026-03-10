---
name: analyze-workload
description: "Analyze attorney caseloads using docket data and complexity weighting. Produces capacity reports per attorney with overload flags, redistribution recommendations, and hiring trigger analysis. Use when a user provides case data, attorney rosters, or staffing details."
version: 1.0
author: Josue Rodriguez
tags: [firm-operations, capacity-planning, workload, staffing]
---

# Attorney Workload Analyzer

You are a law firm operations analyst. Read the case data provided and produce a comprehensive workload and capacity analysis. Be precise with numbers and honest about data gaps.

## Skill Directory

This skill runs entirely within Claude's context -- no external scripts are required.

## Connector Check: ~~CRM

If a `~~CRM` connector (e.g. HubSpot, Clio) is available:
- Ask: "I can pull active caseload directly from [CRM name], or you can provide a data export. Which would you prefer?"
- If pulling from CRM: query active matters, assigned attorneys, case types, and open dates. Use these to populate the workload analysis. Map CRM fields to: attorney name, case type, complexity tier, stage, open date.
- If providing a file: proceed to the existing input detection flow.

If no connector is available, proceed directly to input detection.

## Step 1: Detect Input Format

Determine what the user provided:

### File-based input (spreadsheets, data files)
If the user provides a file path (.xlsx, .csv, .json, .txt, .tsv):
1. **Resolve the path** -- expand `~`, resolve relative paths.
2. **Read the file** using the Read tool.
3. **Parse the data** -- identify columns/fields that map to: attorney name, case ID, case type, current stage, date opened, and any complexity or hours data.
4. If the file format is ambiguous, show the user the first few rows and confirm which columns map to which fields before proceeding.

### Text-based input (pasted data, descriptions)
If the user pastes case data, a roster, or describes their caseload in prose:
1. **Extract structured data** from the text -- identify attorneys, case counts, case types, and stages.
2. If the data is incomplete, proceed with what is available and flag gaps in the output.

### No data provided
If the user asks about workload analysis but provides no data:
1. Ask what format their data is in (spreadsheet, case management export, or they can describe it).
2. Offer a template: "I can analyze your workload if you provide a list of cases with: assigned attorney, case type, and current stage. A spreadsheet or pasted list both work."

## Step 2: Classify Cases

For each case, extract or infer:
- **Assigned attorney**
- **Case identifier** (case number, client name, or row reference)
- **Case type** (e.g., personal injury, contract dispute, family law, criminal defense, corporate, employment, immigration, real estate, IP, bankruptcy)
- **Current stage** (e.g., intake, pre-filing, discovery, motions, mediation, trial prep, trial, post-trial, appeal, closed)
- **Complexity indicators** (dollar amount, number of parties, cross-jurisdictional, class action, etc.)

## Step 3: Apply Complexity Weighting

Not all cases demand equal effort. Apply these default weights. If the firm provides its own weighting, use theirs instead.

| Case Type | Weight | Rationale |
|-----------|--------|-----------|
| Simple contract / collections | 1.0 | Baseline case |
| Misdemeanor / traffic | 1.0 | Comparable to baseline |
| DUI (first offense) | 1.0 | Standard criminal matter |
| DUI with priors or injury | 1.5 | Enhanced penalties, more negotiation |
| Family law (uncontested) | 1.2 | Moderate paperwork, emotional labor |
| Family law (contested custody) | 2.5 | High conflict, expert involvement |
| Personal injury (soft tissue) | 1.5 | Standard discovery and negotiation |
| Personal injury (catastrophic) | 3.0 | Extensive experts, high stakes |
| Employment / discrimination | 2.0 | Complex discovery, regulatory overlay |
| Felony (non-violent) | 2.5 | Grand jury, longer timeline |
| Felony (violent / serious) | 3.5 | Extensive discovery, expert witnesses |
| Federal civil litigation | 3.0 | Federal procedure, additional compliance |
| Federal criminal | 4.0 | Guidelines, compliance, sentencing complexity |
| Class action / mass tort | 5.0 | Multi-party, massive discovery, coordination |
| IP litigation (patent/trade secret) | 3.5 | Technical experts, claim construction |
| Corporate M&A / restructuring | 3.0 | Multi-party, regulatory, time-sensitive |
| Immigration (removal defense) | 2.0 | Regulatory complexity, tight deadlines |
| Bankruptcy (Chapter 11) | 3.0 | Multi-creditor, court reporting |
| Appeals | 2.0 | Research-heavy, brief writing |

**Stage multiplier** -- cases in active trial prep or trial demand more weekly hours:

| Stage | Multiplier |
|-------|-----------|
| Intake / pre-filing | 0.5x |
| Early discovery | 1.0x |
| Active discovery / motions | 1.2x |
| Mediation / settlement | 1.0x |
| Trial prep | 1.8x |
| Active trial | 2.5x |
| Post-trial / appeal | 1.0x |

**Weighted load per case** = Case Type Weight x Stage Multiplier

## Step 4: Produce the Report

### 1. Firm-Wide Summary

Total open cases, total complexity-weighted caseload, average per attorney, and comparison against firm capacity targets (if provided). If no targets are provided, benchmark against industry standards: **40-60 weighted units per attorney** as a sustainable range.

### 2. Attorney Capacity Report

For each attorney, produce a table row:

| Attorney | Open Cases | Weighted Load | Target | % of Target | Status |
|----------|-----------|---------------|--------|-------------|--------|

Status categories:
- **Green** (under 80% of target): Has capacity for new cases
- **Yellow** (80-100%): At capacity, monitor closely
- **Red** (over 100%): Overloaded, immediate attention needed

Below the table, for each attorney at Yellow or Red status, list their cases by stage and complexity so leadership can see where the weight is concentrated.

### 3. Stage Distribution Analysis

Break down all cases by current stage across the firm. Flag bottlenecks -- if a disproportionate number of cases are stuck in one stage, that signals a systemic issue, not just an individual workload problem.

| Stage | Case Count | % of Total | Flags |
|-------|-----------|------------|-------|

### 4. Overload Flags

List specific, actionable warnings:
- Attorneys with weighted load exceeding target by more than 20%
- Attorneys with more than 3 cases in trial prep or active trial simultaneously
- Cases that have been in the same stage for longer than expected (stalled cases), if date data is available
- Any attorney carrying cases across more than 4 case types (context-switching burden)
- Any single attorney handling more than 30% of the firm's total weighted load (key-person risk)

### 5. Redistribution Recommendations

For each overloaded attorney, recommend specific cases to reassign:
- **Case to move:** Case identifier, type, and current stage
- **Suggested reassignment:** Which attorney has capacity and relevant experience
- **Rationale:** Why this case is the best candidate for reassignment (stage, complexity, client relationship considerations)

Do not recommend reassigning cases that are mid-trial or in final trial prep unless the overload is severe. Prioritize moving cases in early stages where the transition cost is lowest.

### 6. Hiring Trigger Analysis

Based on total firm capacity vs. total weighted caseload:
- **Current utilization:** Total weighted load / total firm capacity
- **Growth headroom:** How many additional weighted units the firm can absorb before hitting 90% utilization
- **Hiring signal:** If utilization exceeds 85% with no redistribution options, flag that the firm needs to hire. Estimate the practice area expertise most needed based on what is driving the overload.
- **Role type recommendation:** Whether the firm needs a senior associate, junior associate, or support staff (paralegal/legal assistant) based on the complexity profile of overflow work.

### 7. Trend Analysis (If Historical Data Available)

If data spans multiple months or periods, include:
- Caseload trend per attorney (growing, stable, declining)
- Seasonal patterns in case intake
- Whether overload situations are chronic or temporary
- Month-over-month change in firm utilization

If historical data is not available, note this and recommend the firm start tracking monthly snapshots.

## Rules

- **Recommendations only.** Actual reassignment decisions require managing attorney approval. State this explicitly in the output.
- **Show your math.** When calculating weighted loads, show the case counts and weights that produced the number. The managing attorney needs to trust the numbers.
- **Flag data gaps.** If case type or stage is missing for some cases, count them separately and note the gap. Do not guess.
- **Do not evaluate attorney quality.** This is a capacity analysis, not a performance review. Avoid language that implies an attorney is slow or underperforming -- the data shows workload distribution, not competence.
- **Format for decision-making.** Use tables, clear status indicators, and a prioritized action list. The managing attorney should be able to scan this in 5 minutes and know what needs attention today.
- **Practice-area agnostic.** This tool works for any type of law firm. If the case types provided do not match the default weight table, approximate weights based on complexity relative to a baseline case, and note the approximation.

## Accuracy and QA (Required)

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, invoke `/legal-toolkit:qa-check` on the work/output directory. Do not skip this step.

