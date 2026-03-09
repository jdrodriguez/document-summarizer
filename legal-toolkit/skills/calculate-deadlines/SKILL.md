---
name: calculate-deadlines
description: "Calculate court litigation deadlines with FRCP Rule 6 compliance, jurisdiction-aware holiday and business day handling, service method adjustments, and cascading deadline chains. Use when: (1) a user needs to calculate court filing deadlines, response deadlines, or discovery deadlines, (2) a user says 'calculate deadlines', 'when is the response due', 'what are the deadlines for this case', 'FRCP deadlines', or 'court calendar', (3) any litigation scheduling task involving federal or state court rules, (4) a user needs to export deadlines to a calendar (.ics) or generate a deadline report."
---

# Court Deadline Calculator

Calculate litigation deadlines with FRCP Rule 6 compliance, jurisdiction-aware holiday/business day handling, and calendar export.

**Supported jurisdictions**: Federal (FRCP), CA, NY, TX, FL, IL
**Service methods**: electronic, mail, personal
**Event types**: complaint_served, motion_filed, discovery_request, summary_judgment, appeal_filed

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided case details. If not, ask for:
   - **Trigger date**: the date of the triggering event (e.g., date of service, date motion was filed)
   - **Jurisdiction**: "federal" or a state code (CA, NY, TX, FL, IL)
   - **Event type**: what happened (complaint_served, motion_filed, discovery_request, summary_judgment, appeal_filed)
   - **Service method**: how service was made (electronic, mail, personal)
   - **Case caption** (optional): e.g., "Smith v. Jones"
2. Validate the trigger date is a valid date string (YYYY-MM-DD format).
3. Validate jurisdiction is one of: federal, CA, NY, TX, FL, IL.
4. Validate event type is recognized.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).

### Step 3: Create Input JSON

Build an input JSON file from the user's details:

```bash
WORK_DIR="/tmp/legal-deadlines-$(date +%s)"
mkdir -p "$WORK_DIR"
```

Write the input file to `$WORK_DIR/input.json`:

```json
{
  "trigger_date": "2026-03-15",
  "jurisdiction": "federal",
  "state": "CA",
  "event_type": "complaint_served",
  "service_method": "personal",
  "case_caption": "Smith v. Jones",
  "custom_deadlines": []
}
```

If the user specifies custom deadlines, add them to the `custom_deadlines` array:
```json
{"name": "Expert Report", "days": 90, "business_days": true}
```

### Step 4: Run Deadline Calculator

```bash
python3 "$SKILL_DIR/scripts/calculate_deadlines.py" \
  --input "$WORK_DIR/input.json" \
  --output-dir "$WORK_DIR"
```

The script outputs JSON to stdout with the calculation results.

### Step 5: Present Results

1. Read `$WORK_DIR/deadline_report.txt` and present the deadline schedule to the user.
2. Read `$WORK_DIR/deadlines.json` for structured data.
3. Inform the user that the following files were generated:
   - `deadlines.json` - structured deadline data with rule citations
   - `deadlines.ics` - iCalendar file for import into calendar apps (Google Calendar, Outlook, Apple Calendar)
   - `deadline_report.txt` - human-readable deadline schedule

### Step 6: Offer Additional Actions

- **Calendar import**: Point user to `$WORK_DIR/deadlines.ics` for calendar import
- **DOCX report**: Offer to generate a formal .docx deadline report via `/docx` skill
- **Recalculate**: If user wants to adjust dates or add custom deadlines, loop back to Step 3

## Error Handling

- **Invalid date format**: Ask user to provide date in YYYY-MM-DD format
- **Unknown jurisdiction**: List supported jurisdictions and ask user to choose
- **Unknown event type**: List supported event types and ask user to choose
- **Holiday data unavailable**: Fall back to weekend-only calculations and warn user
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
