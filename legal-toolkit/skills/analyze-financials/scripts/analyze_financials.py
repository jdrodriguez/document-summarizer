#!/usr/bin/env python3
"""
Financial Forensics Toolkit -- ingest bank statements, trace money flows,
detect anomalies, and generate forensic analysis.

Supports: CSV, Excel (.xlsx), OFX/QFX
Outputs: financial_analysis.json, entity_summary.xlsx, money_flow.html,
         transaction_timeline.html, anomaly_report.txt, analysis_summary.txt

Usage:
    python3 analyze_financials.py --input <file_or_dir> --output-dir <dir> \
        [--threshold 10000] [--date-range "2025-01-01:2025-12-31"]
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Column normalization mappings
# ---------------------------------------------------------------------------
COLUMN_MAP = {
    # date
    "date": "date", "transaction_date": "date", "trans_date": "date",
    "posting_date": "date", "post_date": "date", "value_date": "date",
    "effective_date": "date", "posted_date": "date", "txn_date": "date",
    # description
    "description": "description", "memo": "description", "narrative": "description",
    "details": "description", "payee": "description", "name": "description",
    "transaction_description": "description", "reference": "description",
    "particulars": "description",
    # amount (single column, +/-)
    "amount": "amount", "transaction_amount": "amount", "value": "amount",
    "sum": "amount",
    # debit / credit separate columns
    "debit": "debit", "debit_amount": "debit", "withdrawal": "debit",
    "withdrawals": "debit", "money_out": "debit", "outflow": "debit",
    "credit": "credit", "credit_amount": "credit", "deposit": "credit",
    "deposits": "credit", "money_in": "credit", "inflow": "credit",
    # balance
    "balance": "balance", "running_balance": "balance", "closing_balance": "balance",
    "available_balance": "balance", "ledger_balance": "balance",
    # account
    "account": "account", "account_number": "account", "account_name": "account",
    "acct": "account", "account_id": "account",
    # category
    "category": "category", "type": "category", "transaction_type": "category",
    "tran_type": "category",
}


def log(msg):
    """Print progress to stderr."""
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# File Parsing
# ---------------------------------------------------------------------------

def parse_ofx(filepath):
    """Parse OFX/QFX files using regex (no heavy dependency)."""
    log(f"  Parsing OFX: {filepath}")
    with open(filepath, "r", errors="replace") as f:
        content = f.read()

    rows = []
    # Extract account ID
    acct_match = re.search(r'<ACCTID>([^<\n]+)', content)
    account_id = acct_match.group(1).strip() if acct_match else os.path.basename(filepath)

    # Extract transactions
    txn_blocks = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', content, re.DOTALL)
    for block in txn_blocks:
        row = {"account": account_id}
        # Date
        dt_match = re.search(r'<DTPOSTED>(\d{8})', block)
        if dt_match:
            ds = dt_match.group(1)
            row["date"] = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
        # Amount
        amt_match = re.search(r'<TRNAMT>([^<\n]+)', block)
        if amt_match:
            row["amount"] = amt_match.group(1).strip()
        # Description
        name_match = re.search(r'<NAME>([^<\n]+)', block)
        memo_match = re.search(r'<MEMO>([^<\n]+)', block)
        desc_parts = []
        if name_match:
            desc_parts.append(name_match.group(1).strip())
        if memo_match:
            desc_parts.append(memo_match.group(1).strip())
        row["description"] = " - ".join(desc_parts) if desc_parts else ""
        # Type
        type_match = re.search(r'<TRNTYPE>([^<\n]+)', block)
        if type_match:
            row["category"] = type_match.group(1).strip()
        rows.append(row)

    if not rows:
        log(f"  WARNING: No transactions found in OFX file: {filepath}")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["_source_file"] = os.path.basename(filepath)
    return df


def parse_excel(filepath):
    """Parse Excel bank statement."""
    log(f"  Parsing Excel: {filepath}")
    try:
        df = pd.read_excel(filepath, engine="openpyxl")
    except Exception as e:
        log(f"  ERROR parsing Excel {filepath}: {e}")
        return pd.DataFrame()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    df["_source_file"] = os.path.basename(filepath)
    return df


def parse_csv(filepath):
    """Parse CSV bank statement."""
    log(f"  Parsing CSV: {filepath}")
    try:
        df = pd.read_csv(filepath, encoding="utf-8", on_bad_lines="skip")
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(filepath, encoding="latin-1", on_bad_lines="skip")
        except Exception as e:
            log(f"  ERROR parsing CSV {filepath}: {e}")
            return pd.DataFrame()
    except Exception as e:
        log(f"  ERROR parsing CSV {filepath}: {e}")
        return pd.DataFrame()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    df["_source_file"] = os.path.basename(filepath)
    return df


def parse_file(filepath):
    """Parse a single file, auto-detecting format."""
    ext = Path(filepath).suffix.lower()
    if ext in (".ofx", ".qfx"):
        return parse_ofx(filepath)
    elif ext in (".xlsx", ".xls"):
        return parse_excel(filepath)
    elif ext == ".csv":
        return parse_csv(filepath)
    else:
        log(f"  Skipping unsupported file: {filepath}")
        return pd.DataFrame()


def normalize_columns(df):
    """Map various column names to standard fields."""
    rename = {}
    for col in df.columns:
        col_lower = col.lower().strip().replace(" ", "_")
        if col_lower in COLUMN_MAP:
            rename[col] = COLUMN_MAP[col_lower]
    df = df.rename(columns=rename)

    # Handle debit/credit separate columns -> single amount
    if "amount" not in df.columns:
        if "debit" in df.columns and "credit" in df.columns:
            df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0)
            df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0)
            # Debits are negative (outflows), credits are positive (inflows)
            df["amount"] = df["credit"] - df["debit"]
        elif "debit" in df.columns:
            df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0)
            df["amount"] = -df["debit"].abs()
        elif "credit" in df.columns:
            df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0)
            df["amount"] = df["credit"]
        else:
            df["amount"] = None

    # Ensure required columns exist
    for required in ["date", "description", "amount"]:
        if required not in df.columns:
            df[required] = None
    for optional in ["balance", "account", "category"]:
        if optional not in df.columns:
            df[optional] = ""

    # Coerce types
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce") if "balance" in df.columns else None
    df["description"] = df["description"].fillna("").astype(str)
    df["account"] = df["account"].fillna("Unknown").astype(str)
    df["category"] = df["category"].fillna("").astype(str)

    return df


# ---------------------------------------------------------------------------
# Entity Extraction
# ---------------------------------------------------------------------------

def extract_entity(description):
    """Parse payee/entity name from transaction description."""
    desc = str(description).strip()
    if not desc:
        return "Unknown"

    # Remove common bank formatting prefixes
    prefixes = [
        r'^(POS|ACH|WIRE|CHK|DEP|ATM|DBT|CRD|PMT|TFR|XFER|EFT|DD|SO)\s+',
        r'^(PURCHASE|PAYMENT|DEPOSIT|TRANSFER|WITHDRAWAL|CHECK)\s+',
        r'^(DEBIT CARD|CREDIT CARD|ONLINE|MOBILE)\s+',
    ]
    cleaned = desc
    for pattern in prefixes:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    # Remove reference numbers, dates, trailing codes
    cleaned = re.sub(r'\b\d{6,}\b', '', cleaned)  # long numbers
    cleaned = re.sub(r'\b\d{1,2}/\d{1,2}(/\d{2,4})?\b', '', cleaned)  # dates
    cleaned = re.sub(r'#\w+', '', cleaned)  # reference codes
    cleaned = re.sub(r'\bREF\s*:?\s*\w+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bCONF\s*:?\s*\w+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()

    # Take first meaningful chunk (usually the entity name)
    parts = re.split(r'\s{2,}|(?<=\w)\s*-\s*(?=\w{5,})', cleaned, maxsplit=1)
    entity = parts[0].strip() if parts else cleaned

    # Title case if all upper
    if entity.isupper() and len(entity) > 3:
        entity = entity.title()

    return entity if entity else "Unknown"


# ---------------------------------------------------------------------------
# Money Flow Analysis (NetworkX)
# ---------------------------------------------------------------------------

def build_flow_graph(df):
    """Build directed graph of money flows between entities."""
    G = nx.DiGraph()

    for _, row in df.iterrows():
        entity = row.get("_entity", "Unknown")
        account = str(row.get("account", "Unknown"))
        amount = row.get("amount")

        if pd.isna(amount) or amount == 0:
            continue

        if amount > 0:
            # Inflow: entity -> account
            source, target = entity, f"Account: {account}"
        else:
            # Outflow: account -> entity
            source, target = f"Account: {account}", entity
            amount = abs(amount)

        if G.has_edge(source, target):
            G[source][target]["weight"] += amount
            G[source][target]["count"] += 1
        else:
            G.add_edge(source, target, weight=amount, count=1)

    return G


def analyze_flows(G):
    """Analyze money flow graph for patterns."""
    analysis = {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "circular_flows": [],
        "largest_flows": [],
        "net_flows": {},
    }

    # Find circular flows (cycles)
    try:
        cycles = list(nx.simple_cycles(G))
        for cycle in cycles[:20]:  # Limit to 20
            cycle_amount = min(
                G[cycle[i]][cycle[(i + 1) % len(cycle)]]["weight"]
                for i in range(len(cycle))
                if G.has_edge(cycle[i], cycle[(i + 1) % len(cycle)])
            )
            analysis["circular_flows"].append({
                "path": cycle,
                "min_amount": cycle_amount,
            })
    except Exception:
        pass

    # Largest flows
    edges = [(u, v, d["weight"], d["count"]) for u, v, d in G.edges(data=True)]
    edges.sort(key=lambda x: -x[2])
    analysis["largest_flows"] = [
        {"from": u, "to": v, "amount": w, "transactions": c}
        for u, v, w, c in edges[:20]
    ]

    # Net flows per entity
    for node in G.nodes():
        inflow = sum(d["weight"] for _, _, d in G.in_edges(node, data=True))
        outflow = sum(d["weight"] for _, _, d in G.out_edges(node, data=True))
        analysis["net_flows"][node] = {
            "inflow": inflow,
            "outflow": outflow,
            "net": inflow - outflow,
        }

    return analysis


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------

def detect_anomalies(df, threshold=10000):
    """Detect suspicious transaction patterns."""
    anomalies = []
    valid = df[df["amount"].notna()].copy()

    if valid.empty:
        return anomalies

    # 1. Large round numbers / structuring (just below $10K)
    for idx, row in valid.iterrows():
        amt = abs(row["amount"])
        # Amounts between $9,000 and $10,000 (structuring indicator)
        if 9000 <= amt < 10000:
            anomalies.append({
                "index": int(idx),
                "type": "structuring_indicator",
                "severity": "HIGH",
                "amount": float(row["amount"]),
                "date": str(row["date"])[:10] if pd.notna(row["date"]) else "",
                "description": str(row["description"])[:200],
                "explanation": f"Transaction of ${amt:,.2f} is just below the $10,000 reporting threshold",
            })
        # Exact round amounts > threshold
        elif amt >= threshold and amt == round(amt, -2):
            anomalies.append({
                "index": int(idx),
                "type": "large_round_amount",
                "severity": "MEDIUM",
                "amount": float(row["amount"]),
                "date": str(row["date"])[:10] if pd.notna(row["date"]) else "",
                "description": str(row["description"])[:200],
                "explanation": f"Large round transaction of ${amt:,.2f}",
            })

    # 2. Unusual timing (late night / holidays)
    dated = valid[valid["date"].notna()].copy()
    for idx, row in dated.iterrows():
        dt = row["date"]
        if dt.weekday() >= 5:
            day_name = "Saturday" if dt.weekday() == 5 else "Sunday"
            anomalies.append({
                "index": int(idx),
                "type": "unusual_timing",
                "severity": "LOW",
                "amount": float(row["amount"]),
                "date": str(dt)[:10],
                "description": str(row["description"])[:200],
                "explanation": f"Transaction on {day_name}",
            })

    # 3. Rapid in-out patterns (money received then quickly disbursed)
    if not dated.empty:
        for account, acct_group in dated.groupby("account"):
            sorted_txns = acct_group.sort_values("date")
            for i in range(len(sorted_txns) - 1):
                curr = sorted_txns.iloc[i]
                next_txn = sorted_txns.iloc[i + 1]
                if pd.isna(curr["amount"]) or pd.isna(next_txn["amount"]):
                    continue
                # Large inflow followed by large outflow within 2 days
                if (curr["amount"] > threshold and next_txn["amount"] < -threshold * 0.5):
                    days_diff = (next_txn["date"] - curr["date"]).days
                    if 0 <= days_diff <= 2:
                        anomalies.append({
                            "index": int(next_txn.name),
                            "type": "rapid_in_out",
                            "severity": "HIGH",
                            "amount": float(next_txn["amount"]),
                            "date": str(next_txn["date"])[:10],
                            "description": str(next_txn["description"])[:200],
                            "explanation": f"Large outflow of ${abs(next_txn['amount']):,.2f} within {days_diff} day(s) of inflow of ${curr['amount']:,.2f}",
                        })

    # 4. Escalating amounts (to same entity, amounts growing over time)
    entity_txns = defaultdict(list)
    for idx, row in dated.iterrows():
        entity = row.get("_entity", "Unknown")
        if pd.notna(row["amount"]) and abs(row["amount"]) > 100:
            entity_txns[entity].append({
                "date": row["date"],
                "amount": abs(row["amount"]),
                "index": int(idx),
            })

    for entity, txns in entity_txns.items():
        if len(txns) < 4:
            continue
        txns.sort(key=lambda x: x["date"])
        amounts = [t["amount"] for t in txns]
        # Check if amounts are consistently increasing
        increases = sum(1 for i in range(1, len(amounts)) if amounts[i] > amounts[i - 1])
        if increases >= len(amounts) * 0.7:
            anomalies.append({
                "index": txns[-1]["index"],
                "type": "escalating_amounts",
                "severity": "MEDIUM",
                "amount": amounts[-1],
                "date": str(txns[-1]["date"])[:10],
                "description": f"Entity: {entity}",
                "explanation": f"Amounts to {entity} are escalating: {', '.join(f'${a:,.0f}' for a in amounts[-4:])}",
            })

    # 5. New payees with large amounts
    if not dated.empty:
        first_seen = {}
        for idx, row in dated.sort_values("date").iterrows():
            entity = row.get("_entity", "Unknown")
            if entity not in first_seen:
                first_seen[entity] = {
                    "date": row["date"],
                    "amount": abs(row["amount"]) if pd.notna(row["amount"]) else 0,
                    "index": int(idx),
                }
        # Flag entities whose first transaction is large
        for entity, info in first_seen.items():
            if info["amount"] > threshold:
                anomalies.append({
                    "index": info["index"],
                    "type": "new_large_payee",
                    "severity": "MEDIUM",
                    "amount": info["amount"],
                    "date": str(info["date"])[:10],
                    "description": f"Entity: {entity}",
                    "explanation": f"First transaction with {entity} is ${info['amount']:,.2f} (above ${threshold:,.0f} threshold)",
                })

    # 6. Transactions just below reporting thresholds
    for idx, row in valid.iterrows():
        amt = abs(row["amount"])
        # Just below $3,000 (CTR aggregation threshold)
        if 2800 <= amt < 3000:
            anomalies.append({
                "index": int(idx),
                "type": "below_threshold",
                "severity": "LOW",
                "amount": float(row["amount"]),
                "date": str(row["date"])[:10] if pd.notna(row["date"]) else "",
                "description": str(row["description"])[:200],
                "explanation": f"Transaction of ${amt:,.2f} is just below the $3,000 aggregation threshold",
            })

    # Deduplicate
    seen = set()
    unique = []
    for a in anomalies:
        key = (a["index"], a["type"])
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique


# ---------------------------------------------------------------------------
# Visualizations (Plotly)
# ---------------------------------------------------------------------------

def create_sankey(G, output_dir):
    """Create interactive Sankey diagram of money flows."""
    # Get top flows for readability
    edges = [(u, v, d["weight"]) for u, v, d in G.edges(data=True)]
    edges.sort(key=lambda x: -x[2])
    top_edges = edges[:30]  # Top 30 flows

    if not top_edges:
        log("  No flows for Sankey diagram")
        return

    # Build node list
    nodes = list(set(
        [e[0] for e in top_edges] + [e[1] for e in top_edges]
    ))
    node_idx = {n: i for i, n in enumerate(nodes)}

    # Truncate long labels
    labels = [n[:30] for n in nodes]

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=labels,
            color="#2563EB",
        ),
        link=dict(
            source=[node_idx[e[0]] for e in top_edges],
            target=[node_idx[e[1]] for e in top_edges],
            value=[e[2] for e in top_edges],
            color="rgba(37, 99, 235, 0.3)",
        ),
    )])

    fig.update_layout(
        title_text="Money Flow Diagram",
        font_size=11,
        height=700,
        template="plotly_white",
    )

    output_path = os.path.join(output_dir, "money_flow.html")
    fig.write_html(output_path, include_plotlyjs="cdn")
    log(f"  Sankey diagram saved: {output_path}")


def create_timeline(df, anomalies, output_dir):
    """Create transaction timeline scatter plot."""
    dated = df[df["date"].notna() & df["amount"].notna()].copy()
    if dated.empty:
        log("  No dated transactions for timeline")
        return

    # Mark anomalies
    anomaly_indices = set(a["index"] for a in anomalies)
    dated["is_anomaly"] = dated.index.isin(anomaly_indices)
    dated["abs_amount"] = dated["amount"].abs()
    dated["color"] = dated["is_anomaly"].map({True: "Flagged", False: "Normal"})

    fig = px.scatter(
        dated,
        x="date",
        y="amount",
        color="color",
        color_discrete_map={"Normal": "#2563EB", "Flagged": "#EF4444"},
        hover_data=["description", "account"],
        title="Transaction Timeline",
        labels={"amount": "Amount ($)", "date": "Date"},
    )

    fig.update_layout(
        height=500,
        template="plotly_white",
        legend_title="Status",
    )
    fig.update_traces(marker=dict(size=6, opacity=0.7))

    output_path = os.path.join(output_dir, "transaction_timeline.html")
    fig.write_html(output_path, include_plotlyjs="cdn")
    log(f"  Timeline saved: {output_path}")


def create_balance_chart(df, output_dir):
    """Create balance over time line chart."""
    dated = df[df["date"].notna() & df["balance"].notna()].copy()
    if dated.empty:
        log("  No balance data for chart")
        return

    dated = dated.sort_values("date")

    fig = px.line(
        dated,
        x="date",
        y="balance",
        color="account",
        title="Account Balance Over Time",
        labels={"balance": "Balance ($)", "date": "Date"},
    )

    fig.update_layout(
        height=400,
        template="plotly_white",
    )

    output_path = os.path.join(output_dir, "balance_timeline.html")
    fig.write_html(output_path, include_plotlyjs="cdn")
    log(f"  Balance chart saved: {output_path}")


# ---------------------------------------------------------------------------
# Output Generation
# ---------------------------------------------------------------------------

def write_entity_summary(df, output_dir):
    """Write entity summary to Excel."""
    entity_stats = defaultdict(lambda: {"inflow": 0, "outflow": 0, "count": 0, "first_date": None, "last_date": None})

    for _, row in df.iterrows():
        entity = row.get("_entity", "Unknown")
        amount = row.get("amount")
        dt = row.get("date")

        if pd.isna(amount):
            continue

        stats = entity_stats[entity]
        if amount > 0:
            stats["inflow"] += amount
        else:
            stats["outflow"] += abs(amount)
        stats["count"] += 1

        if pd.notna(dt):
            if stats["first_date"] is None or dt < stats["first_date"]:
                stats["first_date"] = dt
            if stats["last_date"] is None or dt > stats["last_date"]:
                stats["last_date"] = dt

    rows = []
    for entity, stats in entity_stats.items():
        rows.append({
            "entity": entity,
            "total_inflow": stats["inflow"],
            "total_outflow": stats["outflow"],
            "net": stats["inflow"] - stats["outflow"],
            "transaction_count": stats["count"],
            "first_seen": str(stats["first_date"])[:10] if stats["first_date"] else "",
            "last_seen": str(stats["last_date"])[:10] if stats["last_date"] else "",
        })

    summary_df = pd.DataFrame(rows)
    summary_df = summary_df.sort_values("transaction_count", ascending=False)

    output_path = os.path.join(output_dir, "entity_summary.xlsx")
    summary_df.to_excel(output_path, index=False, engine="openpyxl")
    log(f"  Entity summary saved: {output_path}")
    return summary_df


def write_anomaly_report(anomalies, output_dir):
    """Write human-readable anomaly report."""
    lines = [
        "=" * 60,
        "ANOMALY REPORT",
        "=" * 60,
        "",
    ]

    if not anomalies:
        lines.append("No anomalies detected.")
    else:
        # Group by type
        by_type = defaultdict(list)
        for a in anomalies:
            by_type[a["type"]].append(a)

        for atype, items in sorted(by_type.items()):
            lines.append(f"--- {atype.upper().replace('_', ' ')} ({len(items)} found) ---")
            lines.append("")
            for item in items[:10]:  # Show top 10 per type
                lines.append(f"  Date: {item.get('date', 'N/A')}")
                lines.append(f"  Amount: ${abs(item.get('amount', 0)):,.2f}")
                lines.append(f"  Severity: {item.get('severity', 'N/A')}")
                lines.append(f"  {item.get('explanation', '')}")
                lines.append(f"  Description: {item.get('description', '')[:100]}")
                lines.append("")
            if len(items) > 10:
                lines.append(f"  ... and {len(items) - 10} more")
                lines.append("")

    output_path = os.path.join(output_dir, "anomaly_report.txt")
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    log(f"  Anomaly report saved: {output_path}")


def write_analysis_summary(df, anomalies, flow_analysis, output_dir):
    """Write overview summary."""
    total_txns = len(df)
    total_volume_in = df[df["amount"] > 0]["amount"].sum() if "amount" in df.columns else 0
    total_volume_out = abs(df[df["amount"] < 0]["amount"].sum()) if "amount" in df.columns else 0
    accounts = df["account"].nunique() if "account" in df.columns else 0
    entities = df["_entity"].nunique() if "_entity" in df.columns else 0

    date_range = ""
    dated = df[df["date"].notna()]
    if not dated.empty:
        date_range = f"{dated['date'].min().strftime('%Y-%m-%d')} to {dated['date'].max().strftime('%Y-%m-%d')}"

    severity_counts = defaultdict(int)
    for a in anomalies:
        severity_counts[a["severity"]] += 1

    lines = [
        "=" * 60,
        "FORENSIC FINANCIAL ANALYSIS SUMMARY",
        "=" * 60,
        "",
        f"Total transactions:    {total_txns:,}",
        f"Accounts analyzed:     {accounts}",
        f"Date range:            {date_range}",
        f"Total inflows:         ${total_volume_in:,.2f}",
        f"Total outflows:        ${total_volume_out:,.2f}",
        f"Unique entities:       {entities:,}",
        "",
        "ANOMALIES FLAGGED:",
        f"  HIGH:   {severity_counts.get('HIGH', 0):,}",
        f"  MEDIUM: {severity_counts.get('MEDIUM', 0):,}",
        f"  LOW:    {severity_counts.get('LOW', 0):,}",
        f"  TOTAL:  {len(anomalies):,}",
        "",
        "FLOW ANALYSIS:",
        f"  Entities in graph:   {flow_analysis.get('total_nodes', 0)}",
        f"  Flow connections:    {flow_analysis.get('total_edges', 0)}",
        f"  Circular flows:      {len(flow_analysis.get('circular_flows', []))}",
        "",
        "TOP FLOWS:",
    ]

    for flow in flow_analysis.get("largest_flows", [])[:5]:
        lines.append(f"  {flow['from'][:25]} -> {flow['to'][:25]}: ${flow['amount']:,.2f} ({flow['transactions']} txns)")

    lines.extend([
        "",
        "OUTPUT FILES:",
        "  entity_summary.xlsx          - Entity inflows/outflows/net",
        "  money_flow.html              - Interactive Sankey diagram",
        "  transaction_timeline.html    - Transaction scatter plot",
        "  anomaly_report.txt           - Detailed anomaly descriptions",
        "  financial_analysis.json      - Structured analysis data",
        "",
        "=" * 60,
    ])

    summary_text = "\n".join(lines)
    output_path = os.path.join(output_dir, "analysis_summary.txt")
    with open(output_path, "w") as f:
        f.write(summary_text)
    log(f"  Summary saved: {output_path}")
    return summary_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Financial Forensics Toolkit")
    parser.add_argument("--input", required=True, help="Bank statement file or directory")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--threshold", type=float, default=10000, help="Reporting threshold amount (default: 10000)")
    parser.add_argument("--date-range", help="Date range filter as 'YYYY-MM-DD:YYYY-MM-DD'")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Parse date range
    date_start, date_end = None, None
    if args.date_range:
        try:
            parts = args.date_range.split(":")
            date_start = pd.to_datetime(parts[0])
            date_end = pd.to_datetime(parts[1])
            log(f"Date range filter: {date_start.date()} to {date_end.date()}")
        except Exception as e:
            log(f"WARNING: Could not parse date range '{args.date_range}': {e}")

    # Discover and parse files
    log("Discovering financial files...")
    files_to_parse = []
    if os.path.isfile(input_path):
        files_to_parse = [input_path]
    elif os.path.isdir(input_path):
        for root, dirs, filenames in os.walk(input_path):
            for fn in filenames:
                ext = Path(fn).suffix.lower()
                if ext in (".csv", ".xlsx", ".xls", ".ofx", ".qfx"):
                    files_to_parse.append(os.path.join(root, fn))
    else:
        log(f"ERROR: Input path does not exist: {input_path}")
        sys.exit(1)

    if not files_to_parse:
        log("ERROR: No supported financial files found.")
        sys.exit(1)

    log(f"Found {len(files_to_parse)} file(s) to process")

    # Parse all files
    all_dfs = []
    parse_errors = []
    for fp in files_to_parse:
        try:
            df = parse_file(fp)
            if not df.empty:
                all_dfs.append(df)
            else:
                parse_errors.append(fp)
        except Exception as e:
            log(f"  ERROR parsing {fp}: {e}")
            parse_errors.append(fp)

    if not all_dfs:
        log("ERROR: No data could be parsed from any file.")
        sys.exit(1)

    # Combine and normalize
    log("Normalizing columns...")
    combined = pd.concat(all_dfs, ignore_index=True)
    df = normalize_columns(combined)
    log(f"Total transactions: {len(df)}")

    # Apply date range filter
    if date_start is not None or date_end is not None:
        before = len(df)
        if date_start is not None:
            df = df[(df["date"].isna()) | (df["date"] >= date_start)]
        if date_end is not None:
            df = df[(df["date"].isna()) | (df["date"] <= date_end)]
        log(f"Date filter: {before} -> {len(df)} transactions")

    # Extract entities
    log("Extracting entities...")
    df["_entity"] = df["description"].apply(extract_entity)

    # Build money flow graph
    log("Building money flow graph...")
    G = build_flow_graph(df)
    flow_analysis = analyze_flows(G)

    # Detect anomalies
    log("Detecting anomalies...")
    anomalies = detect_anomalies(df, threshold=args.threshold)
    log(f"Anomalies found: {len(anomalies)}")

    # Generate outputs
    log("Generating outputs...")
    entity_df = write_entity_summary(df, output_dir)
    create_sankey(G, output_dir)
    create_timeline(df, anomalies, output_dir)
    create_balance_chart(df, output_dir)
    write_anomaly_report(anomalies, output_dir)
    summary_text = write_analysis_summary(df, anomalies, flow_analysis, output_dir)

    # Write full analysis JSON
    report = {
        "total_transactions": len(df),
        "accounts": df["account"].unique().tolist(),
        "entities": df["_entity"].nunique(),
        "files_processed": len(all_dfs),
        "files_failed": parse_errors,
        "flow_analysis": {
            "total_nodes": flow_analysis["total_nodes"],
            "total_edges": flow_analysis["total_edges"],
            "circular_flows": flow_analysis["circular_flows"][:10],
            "largest_flows": flow_analysis["largest_flows"],
        },
        "anomalies": anomalies,
        "anomaly_counts": {
            "HIGH": sum(1 for a in anomalies if a["severity"] == "HIGH"),
            "MEDIUM": sum(1 for a in anomalies if a["severity"] == "MEDIUM"),
            "LOW": sum(1 for a in anomalies if a["severity"] == "LOW"),
            "total": len(anomalies),
        },
    }
    report_path = os.path.join(output_dir, "financial_analysis.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"  Analysis saved: {report_path}")

    # Print JSON summary to stdout for Claude to parse
    summary_json = {
        "status": "success",
        "total_transactions": len(df),
        "accounts": df["account"].unique().tolist(),
        "entities_found": df["_entity"].nunique(),
        "files_processed": len(all_dfs),
        "files_failed": parse_errors,
        "anomaly_counts": report["anomaly_counts"],
        "output_dir": output_dir,
        "outputs": {
            "financial_analysis": report_path,
            "entity_summary": os.path.join(output_dir, "entity_summary.xlsx"),
            "money_flow": os.path.join(output_dir, "money_flow.html"),
            "transaction_timeline": os.path.join(output_dir, "transaction_timeline.html"),
            "anomaly_report": os.path.join(output_dir, "anomaly_report.txt"),
            "analysis_summary": os.path.join(output_dir, "analysis_summary.txt"),
        },
    }
    print(json.dumps(summary_json, indent=2, default=str))


if __name__ == "__main__":
    main()
