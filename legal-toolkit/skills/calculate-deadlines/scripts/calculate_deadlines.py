#!/usr/bin/env python3
"""
Court deadline calculator for the legal-deadlines skill.

Calculates litigation deadlines with FRCP Rule 6 compliance,
jurisdiction-aware holiday/business day handling, service method
adjustments, and cascading deadline chains.

Usage:
    python3 calculate_deadlines.py --input <input.json> --output-dir <dir>

Input JSON schema:
{
  "trigger_date": "2026-03-15",
  "jurisdiction": "federal",
  "state": "CA",
  "event_type": "complaint_served",
  "service_method": "personal",
  "case_caption": "Smith v. Jones",
  "custom_deadlines": [
    {"name": "Expert Report", "days": 90, "business_days": true}
  ]
}
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, date
from typing import Optional

# ---------------------------------------------------------------------------
# Dependency imports
# ---------------------------------------------------------------------------
try:
    import holidays
except ImportError:
    print("ERROR: 'holidays' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

try:
    from dateutil.parser import parse as parse_date
    from dateutil.relativedelta import relativedelta
except ImportError:
    print("ERROR: 'python-dateutil' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

try:
    from icalendar import Calendar, Event, vText
except ImportError:
    print("ERROR: 'icalendar' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

# ---------------------------------------------------------------------------
# Constants and configuration
# ---------------------------------------------------------------------------
SUPPORTED_JURISDICTIONS = {"federal", "CA", "NY", "TX", "FL", "IL"}

HOLIDAYS_STATE_MAP = {
    "federal": None,
    "CA": "CA",
    "NY": "NY",
    "TX": "TX",
    "FL": "FL",
    "IL": "IL",
}

# Service method day adjustments
SERVICE_ADJUSTMENTS = {
    "federal": {
        "mail": 3,
        "electronic": 0,
        "personal": 0,
    },
    "CA": {
        "mail": 5,
        "electronic": 2,
        "personal": 0,
    },
    "NY": {
        "mail": 5,
        "electronic": 1,
        "personal": 0,
    },
    "TX": {
        "mail": 3,
        "electronic": 1,
        "personal": 0,
    },
    "FL": {
        "mail": 5,
        "electronic": 0,
        "personal": 0,
    },
    "IL": {
        "mail": 5,
        "electronic": 0,
        "personal": 0,
    },
}

# ---------------------------------------------------------------------------
# Deadline chain definitions
# ---------------------------------------------------------------------------
# Each event type has a chain of deadlines. Each entry:
#   name: human-readable name
#   days: number of days from trigger
#   business_days: whether to count only business days
#   rule_citation: legal rule reference
#   from_previous: if True, days are counted from the previous deadline in chain
#                  if False, days are counted from the trigger date

FEDERAL_DEADLINE_CHAINS = {
    "complaint_served": [
        {
            "name": "Answer Due",
            "days": 21,
            "business_days": False,
            "rule_citation": "FRCP 12(a)(1)(A)(i)",
            "from_previous": False,
            "description": "Defendant must file answer within 21 days of service of summons and complaint.",
        },
        {
            "name": "Motion to Dismiss Deadline (in lieu of answer)",
            "days": 21,
            "business_days": False,
            "rule_citation": "FRCP 12(b)",
            "from_previous": False,
            "description": "Pre-answer motion to dismiss must be filed before the answer deadline.",
        },
        {
            "name": "Rule 26(f) Conference Deadline",
            "days": 99,
            "business_days": False,
            "rule_citation": "FRCP 26(f)",
            "from_previous": False,
            "description": "Parties must confer at least 21 days before a scheduling conference or scheduling order deadline.",
        },
        {
            "name": "Initial Disclosures Due",
            "days": 114,
            "business_days": False,
            "rule_citation": "FRCP 26(a)(1)(C)",
            "from_previous": False,
            "description": "Initial disclosures due within 14 days after the Rule 26(f) conference.",
        },
    ],
    "motion_filed": [
        {
            "name": "Opposition/Response Due",
            "days": 14,
            "business_days": False,
            "rule_citation": "FRCP 6(d); Local rules vary",
            "from_previous": False,
            "description": "Opposition to motion due 14 days after motion is served (21 days in some districts).",
        },
        {
            "name": "Reply Brief Due",
            "days": 7,
            "business_days": False,
            "rule_citation": "FRCP 6(d); Local rules vary",
            "from_previous": True,
            "description": "Reply brief due 7 days after opposition is served.",
        },
    ],
    "discovery_request": [
        {
            "name": "Discovery Response Due",
            "days": 30,
            "business_days": False,
            "rule_citation": "FRCP 33(b)(2), 34(b)(2)(A), 36(a)(3)",
            "from_previous": False,
            "description": "Responses to interrogatories, document requests, and requests for admission due within 30 days.",
        },
        {
            "name": "Motion to Compel Deadline",
            "days": 30,
            "business_days": False,
            "rule_citation": "FRCP 37(a)",
            "from_previous": True,
            "description": "Motion to compel should be filed within a reasonable time after discovery response deadline passes.",
        },
    ],
    "summary_judgment": [
        {
            "name": "Opposition to Summary Judgment Due",
            "days": 21,
            "business_days": False,
            "rule_citation": "FRCP 56; Local rules vary",
            "from_previous": False,
            "description": "Opposition to motion for summary judgment typically due 21 days after filing.",
        },
        {
            "name": "Reply in Support of Summary Judgment Due",
            "days": 14,
            "business_days": False,
            "rule_citation": "FRCP 56; Local rules vary",
            "from_previous": True,
            "description": "Reply in support of summary judgment typically due 14 days after opposition.",
        },
    ],
    "appeal_filed": [
        {
            "name": "Notice of Appeal Due",
            "days": 30,
            "business_days": False,
            "rule_citation": "FRAP 4(a)(1)(A)",
            "from_previous": False,
            "description": "Notice of appeal must be filed within 30 days of entry of judgment.",
        },
        {
            "name": "Transcript Order Due",
            "days": 14,
            "business_days": False,
            "rule_citation": "FRAP 10(b)(1)",
            "from_previous": True,
            "description": "Appellant must order transcript within 14 days of filing notice of appeal.",
        },
        {
            "name": "Appellant's Brief Due",
            "days": 40,
            "business_days": False,
            "rule_citation": "FRAP 31(a)(1)",
            "from_previous": True,
            "description": "Appellant's brief due 40 days after the record is filed.",
        },
        {
            "name": "Appellee's Brief Due",
            "days": 30,
            "business_days": False,
            "rule_citation": "FRAP 31(a)(1)",
            "from_previous": True,
            "description": "Appellee's brief due 30 days after appellant's brief is served.",
        },
        {
            "name": "Reply Brief Due",
            "days": 21,
            "business_days": False,
            "rule_citation": "FRAP 31(a)(1)",
            "from_previous": True,
            "description": "Reply brief due 21 days after appellee's brief is served.",
        },
    ],
}

# State-specific overrides for common deadlines
STATE_DEADLINE_OVERRIDES = {
    "CA": {
        "complaint_served": [
            {
                "name": "Answer Due",
                "days": 30,
                "business_days": False,
                "rule_citation": "CCP 412.20(a)(3)",
                "from_previous": False,
                "description": "Defendant must respond within 30 days of service of summons and complaint.",
            },
            {
                "name": "Demurrer Deadline",
                "days": 30,
                "business_days": False,
                "rule_citation": "CCP 430.40",
                "from_previous": False,
                "description": "Demurrer must be filed within 30 days of service.",
            },
            {
                "name": "Case Management Conference",
                "days": 180,
                "business_days": False,
                "rule_citation": "CRC 3.722",
                "from_previous": False,
                "description": "Case management conference typically set within 180 days of filing.",
            },
        ],
        "motion_filed": [
            {
                "name": "Opposition Due (estimate)",
                "days": 9,
                "business_days": True,
                "rule_citation": "CCP 1005(b)",
                "from_previous": False,
                "description": "ESTIMATE: Opposition papers due at least 9 court days before hearing. "
                               "Under CCP 1005(b), this deadline is properly calculated backwards from "
                               "the hearing date, not forward from filing. Verify against the actual "
                               "hearing date once set by the court.",
            },
            {
                "name": "Reply Due (estimate)",
                "days": 5,
                "business_days": True,
                "rule_citation": "CCP 1005(b)",
                "from_previous": True,
                "description": "ESTIMATE: Reply papers due at least 5 court days before hearing. "
                               "Under CCP 1005(b), this deadline is properly calculated backwards from "
                               "the hearing date, not forward from filing. Verify against the actual "
                               "hearing date once set by the court.",
            },
        ],
    },
    "NY": {
        "complaint_served": [
            {
                "name": "Answer Due",
                "days": 20,
                "business_days": False,
                "rule_citation": "CPLR 3012(a)",
                "from_previous": False,
                "description": "Defendant must answer within 20 days of personal service within the state.",
            },
            {
                "name": "Answer Due (out-of-state service)",
                "days": 30,
                "business_days": False,
                "rule_citation": "CPLR 3012(a)",
                "from_previous": False,
                "description": "Defendant must answer within 30 days if served outside the state.",
            },
        ],
    },
    "TX": {
        "complaint_served": [
            {
                "name": "Answer Due (Monday after 20 days)",
                "days": 20,
                "business_days": False,
                "rule_citation": "TRCP 99(b)",
                "from_previous": False,
                "description": "Answer due by 10:00 a.m. on the Monday next after expiration of 20 days from service.",
            },
        ],
    },
    "FL": {
        "complaint_served": [
            {
                "name": "Answer Due",
                "days": 20,
                "business_days": False,
                "rule_citation": "Fla. R. Civ. P. 1.140(a)(1)",
                "from_previous": False,
                "description": "Defendant must file responsive pleading within 20 days of service.",
            },
        ],
    },
    "IL": {
        "complaint_served": [
            {
                "name": "Answer Due",
                "days": 30,
                "business_days": False,
                "rule_citation": "735 ILCS 5/2-610",
                "from_previous": False,
                "description": "Defendant must file answer within 30 days of service.",
            },
        ],
    },
}

SUPPORTED_EVENT_TYPES = list(FEDERAL_DEADLINE_CHAINS.keys())


# ---------------------------------------------------------------------------
# Holiday and business day utilities
# ---------------------------------------------------------------------------
class DeadlineCalculator:
    """Calculates court deadlines with jurisdiction-aware rules."""

    def __init__(self, jurisdiction: str, state: Optional[str] = None):
        self.jurisdiction = jurisdiction
        self.state = state or jurisdiction

        # Set up holidays package for holiday lookups
        cal_key = jurisdiction if jurisdiction != "federal" else "federal"
        state_code = HOLIDAYS_STATE_MAP.get(cal_key)
        if state_code:
            self.us_holidays = holidays.US(state=state_code)
        else:
            self.us_holidays = holidays.US()

    def is_holiday(self, d: date) -> bool:
        """Check if a date is a federal or state holiday."""
        return d in self.us_holidays

    def is_business_day(self, d: date) -> bool:
        """Check if a date is a business day (not weekend, not holiday)."""
        if d.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        if self.is_holiday(d):
            return False
        return True

    def next_business_day(self, d: date) -> date:
        """If d is not a business day, advance to next business day."""
        while not self.is_business_day(d):
            d += timedelta(days=1)
        return d

    def add_calendar_days_frcp(self, start: date, days: int) -> date:
        """
        FRCP Rule 6(a)(1) calendar day counting (post-2009 amendments):
        - Exclude the trigger day
        - Count forward the specified number of days (all calendar days)
        - If the last day falls on a weekend or holiday, push to next business day

        The 2009 FRCP amendments eliminated the old distinction that excluded
        intermediate weekends for periods under 11 days. All day-stated periods
        now count every calendar day, with only the final day adjusted if it
        falls on a weekend or holiday.
        """
        # FRCP 6(a)(1): count calendar days, then adjust if final day is weekend/holiday
        result = start + timedelta(days=days)
        result = self.next_business_day(result)
        return result

    def add_business_days(self, start: date, days: int) -> date:
        """Add the specified number of business days to start date.
        Excludes the trigger day per FRCP Rule 6(a)."""
        current = start + timedelta(days=1)  # exclude trigger day
        counted = 0
        while counted < days:
            if self.is_business_day(current):
                counted += 1
                if counted == days:
                    return current
            current += timedelta(days=1)
        return current

    def add_days(self, start: date, days: int, business_days: bool) -> date:
        """Add days from a start date using jurisdiction-appropriate rules."""
        if business_days:
            return self.add_business_days(start, days)
        else:
            if self.jurisdiction == "federal":
                return self.add_calendar_days_frcp(start, days)
            else:
                # State courts: count calendar days, adjust if ends on non-business day
                result = start + timedelta(days=days)
                result = self.next_business_day(result)
                return result

    def get_service_adjustment(self, service_method: str) -> int:
        """Get service method day adjustment for the jurisdiction."""
        jur_key = self.jurisdiction
        adjustments = SERVICE_ADJUSTMENTS.get(jur_key, SERVICE_ADJUSTMENTS["federal"])
        return adjustments.get(service_method, 0)

    def get_holiday_name(self, d: date) -> Optional[str]:
        """Get the name of a holiday on a given date, if any."""
        if d in self.us_holidays:
            return self.us_holidays.get(d)
        return None


# ---------------------------------------------------------------------------
# Core deadline calculation
# ---------------------------------------------------------------------------
def get_deadline_chain(jurisdiction: str, event_type: str) -> list[dict]:
    """Get the appropriate deadline chain for jurisdiction and event type."""
    # Check for state-specific overrides first
    if jurisdiction in STATE_DEADLINE_OVERRIDES:
        state_chains = STATE_DEADLINE_OVERRIDES[jurisdiction]
        if event_type in state_chains:
            return state_chains[event_type]

    # Fall back to federal deadlines
    if event_type in FEDERAL_DEADLINE_CHAINS:
        return FEDERAL_DEADLINE_CHAINS[event_type]

    return []


def calculate_deadlines(input_data: dict) -> dict:
    """Calculate all deadlines from input specification."""
    trigger_date_str = input_data["trigger_date"]
    jurisdiction = input_data.get("jurisdiction", "federal")
    state = input_data.get("state", jurisdiction)
    event_type = input_data["event_type"]
    service_method = input_data.get("service_method", "personal")
    case_caption = input_data.get("case_caption", "Untitled Case")
    custom_deadlines = input_data.get("custom_deadlines", [])

    # Parse trigger date
    try:
        trigger_date = parse_date(trigger_date_str).date()
    except (ValueError, TypeError) as e:
        return {"error": f"Invalid trigger date '{trigger_date_str}': {e}"}

    # Validate jurisdiction
    jur_key = jurisdiction.upper() if jurisdiction != "federal" else "federal"
    if jur_key not in SUPPORTED_JURISDICTIONS:
        return {
            "error": f"Unsupported jurisdiction: {jurisdiction}",
            "supported": list(SUPPORTED_JURISDICTIONS),
        }

    # Validate event type
    if event_type not in SUPPORTED_EVENT_TYPES:
        return {
            "error": f"Unsupported event type: {event_type}",
            "supported": SUPPORTED_EVENT_TYPES,
        }

    # Initialize calculator
    calc = DeadlineCalculator(jur_key, state)

    # Get service adjustment
    service_adj = calc.get_service_adjustment(service_method)

    # Get deadline chain
    chain = get_deadline_chain(jur_key, event_type)

    # Calculate each deadline
    calculated = []
    previous_date = trigger_date

    for entry in chain:
        if entry.get("from_previous", False):
            base_date = previous_date
        else:
            base_date = trigger_date

        # Calculate the raw deadline
        raw_deadline = calc.add_days(base_date, entry["days"], entry["business_days"])

        # Apply service adjustment (only to deadlines counted from trigger date)
        adjusted_deadline = raw_deadline
        if not entry.get("from_previous", False) and service_adj > 0:
            adjusted_deadline = raw_deadline + timedelta(days=service_adj)
            adjusted_deadline = calc.next_business_day(adjusted_deadline)

        # Check if the deadline falls on a holiday
        holiday_name = calc.get_holiday_name(adjusted_deadline)

        days_from_trigger = (adjusted_deadline - trigger_date).days

        deadline_entry = {
            "name": entry["name"],
            "date": adjusted_deadline.isoformat(),
            "day_of_week": adjusted_deadline.strftime("%A"),
            "days_from_trigger": days_from_trigger,
            "calculation_basis": {
                "base_date": base_date.isoformat(),
                "days_added": entry["days"],
                "business_days": entry["business_days"],
                "service_adjustment_days": service_adj if not entry.get("from_previous", False) else 0,
                "from_previous": entry.get("from_previous", False),
            },
            "rule_citation": entry["rule_citation"],
            "description": entry["description"],
            "holiday_note": f"Adjusted past {holiday_name}" if holiday_name else None,
        }
        calculated.append(deadline_entry)
        previous_date = adjusted_deadline

    # Add custom deadlines
    for custom in custom_deadlines:
        custom_name = custom.get("name", "Custom Deadline")
        custom_days = custom.get("days", 30)
        custom_business = custom.get("business_days", False)

        custom_date = calc.add_days(trigger_date, custom_days, custom_business)
        if service_adj > 0:
            custom_date = custom_date + timedelta(days=service_adj)
            custom_date = calc.next_business_day(custom_date)

        holiday_name = calc.get_holiday_name(custom_date)

        calculated.append({
            "name": custom_name,
            "date": custom_date.isoformat(),
            "day_of_week": custom_date.strftime("%A"),
            "days_from_trigger": (custom_date - trigger_date).days,
            "calculation_basis": {
                "base_date": trigger_date.isoformat(),
                "days_added": custom_days,
                "business_days": custom_business,
                "service_adjustment_days": service_adj,
                "from_previous": False,
            },
            "rule_citation": "Custom deadline",
            "description": f"User-defined deadline: {custom_name}",
            "holiday_note": f"Adjusted past {holiday_name}" if holiday_name else None,
        })

    # Sort by date
    calculated.sort(key=lambda x: x["date"])

    result = {
        "status": "success",
        "case_caption": case_caption,
        "trigger_date": trigger_date.isoformat(),
        "trigger_day_of_week": trigger_date.strftime("%A"),
        "jurisdiction": jur_key,
        "state": state,
        "event_type": event_type,
        "service_method": service_method,
        "service_adjustment_days": service_adj,
        "total_deadlines": len(calculated),
        "deadlines": calculated,
    }

    return result


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------
def write_deadlines_json(result: dict, output_dir: str):
    """Write structured deadline data to JSON."""
    path = os.path.join(output_dir, "deadlines.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Written: {path}", file=sys.stderr)


def write_deadlines_ics(result: dict, output_dir: str):
    """Write iCalendar file for calendar import."""
    cal = Calendar()
    cal.add("prodid", "-//Legal Deadlines Calculator//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", f"Deadlines: {result['case_caption']}")

    for deadline in result["deadlines"]:
        event = Event()
        event.add("summary", f"[DEADLINE] {deadline['name']}")

        deadline_date = datetime.fromisoformat(deadline["date"]).date()
        event.add("dtstart", deadline_date)
        event.add("dtend", deadline_date + timedelta(days=1))

        description_parts = [
            f"Case: {result['case_caption']}",
            f"Rule: {deadline['rule_citation']}",
            f"",
            deadline["description"],
            f"",
            f"Trigger Date: {result['trigger_date']}",
            f"Days from trigger: {deadline['days_from_trigger']}",
            f"Jurisdiction: {result['jurisdiction']}",
            f"Service Method: {result['service_method']}",
        ]
        if deadline.get("holiday_note"):
            description_parts.append(f"Note: {deadline['holiday_note']}")

        event.add("description", "\n".join(description_parts))
        event["location"] = vText(f"{result['jurisdiction']} Court")

        # Set alarm for 2 days before
        from icalendar import Alarm
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", f"Deadline in 2 days: {deadline['name']}")
        alarm.add("trigger", timedelta(days=-2))
        event.add_component(alarm)

        cal.add_component(event)

    path = os.path.join(output_dir, "deadlines.ics")
    with open(path, "wb") as f:
        f.write(cal.to_ical())
    print(f"Written: {path}", file=sys.stderr)


def write_deadline_report(result: dict, output_dir: str):
    """Write human-readable deadline report."""
    lines = []
    lines.append("=" * 72)
    lines.append("COURT DEADLINE SCHEDULE")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Case:             {result['case_caption']}")
    lines.append(f"Trigger Date:     {result['trigger_date']} ({result['trigger_day_of_week']})")
    lines.append(f"Event Type:       {result['event_type'].replace('_', ' ').title()}")
    lines.append(f"Jurisdiction:     {result['jurisdiction']}")
    lines.append(f"Service Method:   {result['service_method'].title()}")
    if result["service_adjustment_days"] > 0:
        lines.append(f"Service Adj.:     +{result['service_adjustment_days']} days")
    lines.append(f"Total Deadlines:  {result['total_deadlines']}")
    lines.append("")
    lines.append("-" * 72)
    lines.append("DEADLINE SCHEDULE")
    lines.append("-" * 72)
    lines.append("")

    for i, deadline in enumerate(result["deadlines"], 1):
        lines.append(f"  {i}. {deadline['name']}")
        lines.append(f"     Date:  {deadline['date']} ({deadline['day_of_week']})")
        lines.append(f"     Rule:  {deadline['rule_citation']}")
        lines.append(f"     Days from trigger: {deadline['days_from_trigger']}")
        if deadline.get("holiday_note"):
            lines.append(f"     Note:  {deadline['holiday_note']}")
        lines.append(f"     {deadline['description']}")
        lines.append("")

    lines.append("-" * 72)
    lines.append("CALCULATION NOTES")
    lines.append("-" * 72)
    lines.append("")
    if result["jurisdiction"] == "federal":
        lines.append("  - Federal deadlines follow FRCP Rule 6(a)(1) counting (2009 amendments):")
        lines.append("    * Exclude the trigger day")
        lines.append("    * Count all calendar days for all day-stated periods")
        lines.append("    * If last day falls on weekend/holiday, extend to next business day")
    else:
        lines.append(f"  - {result['jurisdiction']} state court rules applied")
        lines.append("    * Calendar days counted from day after trigger")
        lines.append("    * If last day falls on weekend/holiday, extend to next business day")

    if result["service_adjustment_days"] > 0:
        lines.append(f"  - Service by {result['service_method']}: +{result['service_adjustment_days']} days added")

    lines.append("")
    lines.append("  DISCLAIMER: This calculator provides estimates based on general rules.")
    lines.append("  Always verify deadlines against current local rules and court orders.")
    lines.append("  Local rules may modify these deadlines. Consult with counsel.")
    lines.append("")
    lines.append("=" * 72)

    path = os.path.join(output_dir, "deadline_report.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Written: {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Calculate court litigation deadlines with FRCP Rule 6 compliance."
    )
    parser.add_argument("--input", required=True, help="Path to input JSON file")
    parser.add_argument("--output-dir", required=True, help="Directory for output files")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output_dir)

    # Validate input file
    if not os.path.isfile(input_path):
        print(json.dumps({"error": f"Input file not found: {input_path}"}))
        sys.exit(1)

    # Read input
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            input_data = json.load(f)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON in input file: {e}"}))
        sys.exit(1)

    # Validate required fields
    required_fields = ["trigger_date", "event_type"]
    missing = [f for f in required_fields if f not in input_data]
    if missing:
        print(json.dumps({"error": f"Missing required fields: {', '.join(missing)}"}))
        sys.exit(1)

    # Set defaults
    input_data.setdefault("jurisdiction", "federal")
    input_data.setdefault("service_method", "personal")
    input_data.setdefault("case_caption", "Untitled Case")
    input_data.setdefault("custom_deadlines", [])

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Calculate deadlines
    print("Calculating deadlines...", file=sys.stderr)
    result = calculate_deadlines(input_data)

    if "error" in result:
        print(json.dumps(result))
        sys.exit(1)

    # Write output files
    write_deadlines_json(result, output_dir)
    write_deadlines_ics(result, output_dir)
    write_deadline_report(result, output_dir)

    # Print summary JSON to stdout for Claude to parse
    print(json.dumps({
        "status": "success",
        "case_caption": result["case_caption"],
        "trigger_date": result["trigger_date"],
        "jurisdiction": result["jurisdiction"],
        "event_type": result["event_type"],
        "service_method": result["service_method"],
        "total_deadlines": result["total_deadlines"],
        "output_dir": output_dir,
        "files": [
            "deadlines.json",
            "deadlines.ics",
            "deadline_report.txt",
        ],
        "deadlines_preview": [
            {"name": d["name"], "date": d["date"], "rule": d["rule_citation"]}
            for d in result["deadlines"][:10]
        ],
    }))


if __name__ == "__main__":
    main()
