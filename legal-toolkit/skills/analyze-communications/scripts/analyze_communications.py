#!/usr/bin/env python3
"""
Communication Pattern Analyzer -- analyze communication datasets to build
relationship networks, detect communities, identify key players, and find
temporal anomalies.

Supports: CSV, Excel (.xlsx), common exports (Google Takeout, iMessage, WhatsApp, CDR)
Outputs: network_analysis.json, relationship_graph.html, communication_timeline.html,
         communication_heatmap.html, key_players.xlsx, gap_analysis.xlsx, analysis_summary.txt

Usage:
    python3 analyze_communications.py --input <file_or_dir> --output-dir <dir> \
        [--date-range "2025-01-01:2025-12-31"] [--key-dates "2025-06-15,2025-09-01"]
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False

# ---------------------------------------------------------------------------
# Column normalization mappings
# ---------------------------------------------------------------------------
COLUMN_MAP = {
    # sender
    "from": "sender", "sender": "sender", "from_address": "sender",
    "from_email": "sender", "sent_from": "sender", "author": "sender",
    "caller": "sender", "calling_number": "sender", "originator": "sender",
    "source": "sender", "sent_by": "sender",
    # recipient
    "to": "recipient", "recipient": "recipient", "to_address": "recipient",
    "to_email": "recipient", "sent_to": "recipient", "receiver": "recipient",
    "callee": "recipient", "called_number": "recipient", "destination": "recipient",
    "target": "recipient",
    # datetime
    "date": "datetime", "datetime": "datetime", "timestamp": "datetime",
    "sent_date": "datetime", "sent_time": "datetime", "time": "datetime",
    "date_time": "datetime", "call_date": "datetime", "call_time": "datetime",
    "message_date": "datetime",
    # content/subject
    "subject": "content_preview", "content": "content_preview",
    "message": "content_preview", "body": "content_preview",
    "text": "content_preview", "snippet": "content_preview",
    "preview": "content_preview",
    # type
    "type": "type", "message_type": "type", "communication_type": "type",
    "channel": "type", "medium": "type", "call_type": "type",
    # duration (for phone records)
    "duration": "duration", "call_duration": "duration", "length": "duration",
    "duration_seconds": "duration",
}


def log(msg):
    """Print progress to stderr."""
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# File Parsing
# ---------------------------------------------------------------------------

def detect_format(filepath):
    """Try to detect the communication data format."""
    ext = Path(filepath).suffix.lower()
    if ext in (".xlsx", ".xls"):
        return "excel"
    if ext == ".csv":
        # Peek at headers to detect specific formats
        try:
            with open(filepath, "r", errors="replace") as f:
                first_line = f.readline().strip().lower()
            # WhatsApp export detection
            if re.match(r'\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}', first_line):
                return "whatsapp"
            return "csv"
        except Exception:
            return "csv"
    if ext == ".txt":
        # Could be WhatsApp or iMessage export
        try:
            with open(filepath, "r", errors="replace") as f:
                first_line = f.readline().strip()
            if re.match(r'\[\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}', first_line):
                return "whatsapp"
            if re.match(r'\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}', first_line):
                return "whatsapp"
            return "csv"
        except Exception:
            return "csv"
    return None


def parse_whatsapp(filepath):
    """Parse WhatsApp chat export format."""
    log(f"  Parsing WhatsApp export: {filepath}")
    rows = []
    # Common WhatsApp patterns:
    # [MM/DD/YY, HH:MM:SS] Sender: Message
    # MM/DD/YY, HH:MM - Sender: Message
    patterns = [
        r'\[(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]\s+([^:]+):\s+(.*)',
        r'(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s+-\s+([^:]+):\s+(.*)',
    ]

    with open(filepath, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    date_str, time_str, sender, message = match.groups()
                    rows.append({
                        "datetime": f"{date_str} {time_str}",
                        "sender": sender.strip(),
                        "recipient": "Group",  # WhatsApp exports don't clearly show recipients
                        "content_preview": message.strip()[:500],
                        "type": "whatsapp",
                    })
                    break

    if not rows:
        log(f"  WARNING: No messages parsed from WhatsApp export: {filepath}")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["_source_file"] = os.path.basename(filepath)
    return df


def parse_excel(filepath):
    """Parse Excel communication data."""
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
    """Parse CSV communication data."""
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
    fmt = detect_format(filepath)
    if fmt == "whatsapp":
        return parse_whatsapp(filepath)
    elif fmt == "excel":
        return parse_excel(filepath)
    elif fmt == "csv":
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

    # Ensure required columns exist
    for required in ["sender", "recipient", "datetime"]:
        if required not in df.columns:
            df[required] = None
    for optional in ["content_preview", "type", "duration"]:
        if optional not in df.columns:
            df[optional] = ""

    # Coerce types
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["sender"] = df["sender"].fillna("Unknown").astype(str).str.strip()
    df["recipient"] = df["recipient"].fillna("Unknown").astype(str).str.strip()
    df["content_preview"] = df["content_preview"].fillna("").astype(str)
    df["type"] = df["type"].fillna("unknown").astype(str)

    # Duration handling
    if "duration" in df.columns:
        df["duration"] = pd.to_numeric(df["duration"], errors="coerce")

    return df


# ---------------------------------------------------------------------------
# Network Analysis (NetworkX)
# ---------------------------------------------------------------------------

def build_communication_graph(df):
    """Build undirected communication graph."""
    G = nx.Graph()

    for _, row in df.iterrows():
        sender = row.get("sender", "Unknown")
        recipient = row.get("recipient", "Unknown")
        if sender == recipient or sender == "Unknown" or recipient == "Unknown":
            continue

        if G.has_edge(sender, recipient):
            G[sender][recipient]["weight"] += 1
        else:
            G.add_edge(sender, recipient, weight=1)

    # Also track per-node stats
    for node in G.nodes():
        sent = len(df[df["sender"] == node])
        received = len(df[df["recipient"] == node])
        G.nodes[node]["sent"] = sent
        G.nodes[node]["received"] = received
        G.nodes[node]["total"] = sent + received

    return G


def compute_centrality(G):
    """Compute centrality metrics for all nodes."""
    metrics = {}

    if G.number_of_nodes() == 0:
        return metrics

    degree = nx.degree_centrality(G)
    betweenness = nx.betweenness_centrality(G, weight="weight")
    closeness = nx.closeness_centrality(G)

    try:
        pagerank = nx.pagerank(G, weight="weight")
    except Exception:
        pagerank = {n: 0 for n in G.nodes()}

    for node in G.nodes():
        metrics[node] = {
            "degree_centrality": degree.get(node, 0),
            "betweenness_centrality": betweenness.get(node, 0),
            "closeness_centrality": closeness.get(node, 0),
            "pagerank": pagerank.get(node, 0),
            "sent": G.nodes[node].get("sent", 0),
            "received": G.nodes[node].get("received", 0),
            "total_communications": G.nodes[node].get("total", 0),
            "unique_contacts": G.degree(node),
        }

    return metrics


def detect_communities(G):
    """Detect communities using Louvain algorithm."""
    communities = {}

    if G.number_of_nodes() < 2:
        return communities

    if HAS_LOUVAIN:
        try:
            partition = community_louvain.best_partition(G, weight="weight")
            # Group by community
            comm_groups = defaultdict(list)
            for node, comm_id in partition.items():
                comm_groups[comm_id].append(node)

            for comm_id, members in comm_groups.items():
                # Find most active member as label
                most_active = max(members, key=lambda n: G.nodes[n].get("total", 0))
                communities[comm_id] = {
                    "members": members,
                    "size": len(members),
                    "label": f"Community {comm_id} ({most_active})",
                    "most_active": most_active,
                }

            # Store partition for visualization
            communities["_partition"] = partition
        except Exception as e:
            log(f"  WARNING: Community detection failed: {e}")
    else:
        log("  WARNING: python-louvain not available, skipping community detection")
        # Fallback: use connected components
        for i, component in enumerate(nx.connected_components(G)):
            members = list(component)
            most_active = max(members, key=lambda n: G.nodes[n].get("total", 0))
            communities[i] = {
                "members": members,
                "size": len(members),
                "label": f"Group {i} ({most_active})",
                "most_active": most_active,
            }

    return communities


# ---------------------------------------------------------------------------
# Temporal Analysis
# ---------------------------------------------------------------------------

def analyze_temporal(df, key_dates=None):
    """Analyze communication volume over time."""
    temporal = {
        "daily_volume": [],
        "spikes": [],
        "drops": [],
        "gaps": [],
        "key_date_analysis": [],
    }

    dated = df[df["datetime"].notna()].copy()
    if dated.empty:
        return temporal

    dated["date_only"] = dated["datetime"].dt.date

    # Daily volume
    daily = dated.groupby("date_only").size().reset_index(name="count")
    daily.columns = ["date", "count"]
    temporal["daily_volume"] = [
        {"date": str(d), "count": int(c)}
        for d, c in zip(daily["date"], daily["count"])
    ]

    if len(daily) < 3:
        return temporal

    # Detect spikes and drops (Z-score based)
    mean_vol = daily["count"].mean()
    std_vol = daily["count"].std()
    if std_vol > 0:
        daily["zscore"] = (daily["count"] - mean_vol) / std_vol
        spikes = daily[daily["zscore"] > 2]
        drops = daily[daily["zscore"] < -1.5]

        temporal["spikes"] = [
            {"date": str(row["date"]), "count": int(row["count"]),
             "zscore": round(float(row["zscore"]), 2)}
            for _, row in spikes.iterrows()
        ]
        temporal["drops"] = [
            {"date": str(row["date"]), "count": int(row["count"]),
             "zscore": round(float(row["zscore"]), 2)}
            for _, row in drops.iterrows()
        ]

    # Gap analysis: find periods with no communication
    all_dates = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    active_dates = set(daily["date"].values)
    gap_start = None
    for d in all_dates:
        d_date = d.date()
        if d_date not in active_dates:
            if gap_start is None:
                gap_start = d_date
        else:
            if gap_start is not None:
                gap_days = (d_date - gap_start).days
                if gap_days >= 3:  # Only flag gaps of 3+ days
                    temporal["gaps"].append({
                        "start": str(gap_start),
                        "end": str(d_date - timedelta(days=1)),
                        "days": gap_days,
                    })
                gap_start = None
    # Handle trailing gap
    if gap_start is not None:
        gap_days = (all_dates[-1].date() - gap_start).days + 1
        if gap_days >= 3:
            temporal["gaps"].append({
                "start": str(gap_start),
                "end": str(all_dates[-1].date()),
                "days": gap_days,
            })

    # Key date analysis
    if key_dates:
        for key_date_str in key_dates:
            try:
                key_date = pd.to_datetime(key_date_str).date()
            except Exception:
                continue

            # 30 days before and after
            before_start = key_date - timedelta(days=30)
            after_end = key_date + timedelta(days=30)

            before_mask = (daily["date"] >= before_start) & (daily["date"] < key_date)
            after_mask = (daily["date"] > key_date) & (daily["date"] <= after_end)

            before_vol = daily[before_mask]["count"].mean() if before_mask.any() else 0
            after_vol = daily[after_mask]["count"].mean() if after_mask.any() else 0

            # Count unique participants before/after
            before_comms = dated[(dated["date_only"] >= before_start) & (dated["date_only"] < key_date)]
            after_comms = dated[(dated["date_only"] > key_date) & (dated["date_only"] <= after_end)]

            before_participants = set(before_comms["sender"].unique()) | set(before_comms["recipient"].unique())
            after_participants = set(after_comms["sender"].unique()) | set(after_comms["recipient"].unique())

            new_participants = after_participants - before_participants
            lost_participants = before_participants - after_participants

            temporal["key_date_analysis"].append({
                "key_date": str(key_date),
                "avg_daily_before": round(float(before_vol), 1),
                "avg_daily_after": round(float(after_vol), 1),
                "change_pct": round(((after_vol - before_vol) / max(before_vol, 1)) * 100, 1),
                "new_participants": list(new_participants)[:20],
                "lost_participants": list(lost_participants)[:20],
            })

    return temporal


# ---------------------------------------------------------------------------
# Visualizations (Plotly)
# ---------------------------------------------------------------------------

def create_network_graph(G, communities, output_dir):
    """Create interactive network visualization."""
    if G.number_of_nodes() == 0:
        log("  No nodes for network graph")
        return

    # Get positions using spring layout
    pos = nx.spring_layout(G, k=2 / max(G.number_of_nodes() ** 0.5, 1), iterations=50, seed=42)

    # Get community colors
    partition = communities.get("_partition", {})
    comm_colors = {}
    color_palette = px.colors.qualitative.Set3
    for node in G.nodes():
        comm_id = partition.get(node, 0)
        if comm_id not in comm_colors:
            comm_colors[comm_id] = color_palette[len(comm_colors) % len(color_palette)]

    # Build edge traces
    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    # Build node traces
    node_x = [pos[n][0] for n in G.nodes()]
    node_y = [pos[n][1] for n in G.nodes()]
    node_sizes = [max(5, min(30, G.nodes[n].get("total", 1) ** 0.5 * 3)) for n in G.nodes()]
    node_colors = [comm_colors.get(partition.get(n, 0), "#2563EB") for n in G.nodes()]
    node_text = [
        f"{n}<br>Sent: {G.nodes[n].get('sent', 0)}<br>"
        f"Received: {G.nodes[n].get('received', 0)}<br>"
        f"Contacts: {G.degree(n)}"
        for n in G.nodes()
    ]

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        hoverinfo="text",
        text=[n[:15] for n in G.nodes()],
        textposition="top center",
        textfont=dict(size=8),
        hovertext=node_text,
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=1, color="white"),
        ),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title="Communication Network",
        showlegend=False,
        hovermode="closest",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=700,
        template="plotly_white",
    )

    output_path = os.path.join(output_dir, "relationship_graph.html")
    fig.write_html(output_path, include_plotlyjs="cdn")
    log(f"  Network graph saved: {output_path}")


def create_timeline(df, temporal, output_dir):
    """Create communication volume timeline."""
    daily_vol = temporal.get("daily_volume", [])
    if not daily_vol:
        log("  No daily volume for timeline")
        return

    vol_df = pd.DataFrame(daily_vol)
    vol_df["date"] = pd.to_datetime(vol_df["date"])

    fig = go.Figure()

    # Volume line
    fig.add_trace(go.Scatter(
        x=vol_df["date"],
        y=vol_df["count"],
        mode="lines",
        name="Daily Volume",
        line=dict(color="#2563EB", width=2),
    ))

    # Mark spikes
    spikes = temporal.get("spikes", [])
    if spikes:
        spike_df = pd.DataFrame(spikes)
        spike_df["date"] = pd.to_datetime(spike_df["date"])
        fig.add_trace(go.Scatter(
            x=spike_df["date"],
            y=spike_df["count"],
            mode="markers",
            name="Spikes",
            marker=dict(color="#EF4444", size=10, symbol="triangle-up"),
        ))

    # Mark gaps
    gaps = temporal.get("gaps", [])
    for gap in gaps:
        fig.add_vrect(
            x0=gap["start"], x1=gap["end"],
            fillcolor="rgba(239, 68, 68, 0.1)",
            layer="below",
            line_width=0,
            annotation_text=f"{gap['days']}d gap",
            annotation_position="top left",
        )

    # Mark key dates
    key_date_analysis = temporal.get("key_date_analysis", [])
    for kd in key_date_analysis:
        fig.add_vline(
            x=kd["key_date"],
            line_dash="dash",
            line_color="#F59E0B",
            annotation_text=f"Key: {kd['key_date']}",
            annotation_position="top right",
        )

    fig.update_layout(
        title="Communication Volume Over Time",
        xaxis_title="Date",
        yaxis_title="Number of Communications",
        height=400,
        template="plotly_white",
    )

    output_path = os.path.join(output_dir, "communication_timeline.html")
    fig.write_html(output_path, include_plotlyjs="cdn")
    log(f"  Timeline saved: {output_path}")


def create_heatmap(df, output_dir, max_participants=30):
    """Create who-to-whom communication heatmap."""
    # Get top participants
    all_participants = pd.concat([df["sender"], df["recipient"]]).value_counts()
    top = all_participants.head(max_participants).index.tolist()

    if len(top) < 2:
        log("  Not enough participants for heatmap")
        return

    # Build matrix
    matrix = pd.DataFrame(0, index=top, columns=top)
    for _, row in df.iterrows():
        s = row["sender"]
        r = row["recipient"]
        if s in top and r in top:
            matrix.loc[s, r] += 1

    fig = px.imshow(
        matrix.values,
        x=[str(c)[:20] for c in matrix.columns],
        y=[str(r)[:20] for r in matrix.index],
        color_continuous_scale="Blues",
        labels=dict(color="Communications"),
        title="Communication Heatmap (Who-to-Whom)",
    )

    fig.update_layout(
        height=max(400, len(top) * 25),
        template="plotly_white",
    )

    output_path = os.path.join(output_dir, "communication_heatmap.html")
    fig.write_html(output_path, include_plotlyjs="cdn")
    log(f"  Heatmap saved: {output_path}")


# ---------------------------------------------------------------------------
# Output Generation
# ---------------------------------------------------------------------------

def write_key_players(centrality, output_dir):
    """Write ranked list of key players to Excel."""
    if not centrality:
        log("  No centrality data for key players")
        return

    rows = []
    for node, metrics in centrality.items():
        rows.append({
            "participant": node,
            "total_communications": metrics["total_communications"],
            "unique_contacts": metrics["unique_contacts"],
            "sent": metrics["sent"],
            "received": metrics["received"],
            "degree_centrality": round(metrics["degree_centrality"], 4),
            "betweenness_centrality": round(metrics["betweenness_centrality"], 4),
            "closeness_centrality": round(metrics["closeness_centrality"], 4),
            "pagerank": round(metrics["pagerank"], 6),
        })

    players_df = pd.DataFrame(rows)
    players_df = players_df.sort_values("pagerank", ascending=False)

    output_path = os.path.join(output_dir, "key_players.xlsx")
    players_df.to_excel(output_path, index=False, engine="xlsxwriter")
    log(f"  Key players saved: {output_path}")


def write_gap_analysis(temporal, output_dir):
    """Write gap analysis to Excel."""
    gaps = temporal.get("gaps", [])
    if not gaps:
        # Write empty report
        empty_df = pd.DataFrame(columns=["start", "end", "days"])
        empty_df.to_excel(os.path.join(output_dir, "gap_analysis.xlsx"), index=False, engine="xlsxwriter")
        return

    gaps_df = pd.DataFrame(gaps)
    gaps_df = gaps_df.sort_values("days", ascending=False)

    output_path = os.path.join(output_dir, "gap_analysis.xlsx")
    gaps_df.to_excel(output_path, index=False, engine="xlsxwriter")
    log(f"  Gap analysis saved: {output_path}")


def write_analysis_summary(df, centrality, communities, temporal, output_dir):
    """Write overview summary."""
    total_comms = len(df)
    participants = set(df["sender"].unique()) | set(df["recipient"].unique())
    participants.discard("Unknown")
    participants.discard("Group")

    date_range = ""
    dated = df[df["datetime"].notna()]
    if not dated.empty:
        date_range = f"{dated['datetime'].min().strftime('%Y-%m-%d')} to {dated['datetime'].max().strftime('%Y-%m-%d')}"

    # Count real communities (excluding _partition key)
    num_communities = sum(1 for k in communities if k != "_partition")

    gaps = temporal.get("gaps", [])
    spikes = temporal.get("spikes", [])

    # Top players by PageRank
    top_players = sorted(centrality.items(), key=lambda x: -x[1]["pagerank"])[:10]

    lines = [
        "=" * 60,
        "COMMUNICATION PATTERN ANALYSIS SUMMARY",
        "=" * 60,
        "",
        f"Total communications:   {total_comms:,}",
        f"Date range:             {date_range}",
        f"Unique participants:    {len(participants):,}",
        f"Communities detected:   {num_communities}",
        f"Communication gaps:     {len(gaps)}",
        f"Spikes detected:        {len(spikes)}",
        "",
        "KEY PLAYERS (by PageRank):",
    ]

    for player, metrics in top_players:
        lines.append(
            f"  {player[:30]:30s}  PageRank: {metrics['pagerank']:.4f}  "
            f"Comms: {metrics['total_communications']}  "
            f"Contacts: {metrics['unique_contacts']}"
        )

    lines.extend(["", "COMMUNITIES:"])
    for comm_id, comm_info in communities.items():
        if comm_id == "_partition":
            continue
        members_preview = ", ".join(comm_info["members"][:5])
        if len(comm_info["members"]) > 5:
            members_preview += f", ... (+{len(comm_info['members']) - 5} more)"
        lines.append(f"  {comm_info['label']}: {members_preview}")

    if gaps:
        lines.extend(["", "COMMUNICATION GAPS (3+ days):"])
        for gap in gaps[:10]:
            lines.append(f"  {gap['start']} to {gap['end']} ({gap['days']} days)")

    key_date_analysis = temporal.get("key_date_analysis", [])
    if key_date_analysis:
        lines.extend(["", "KEY DATE ANALYSIS:"])
        for kd in key_date_analysis:
            lines.append(f"  Date: {kd['key_date']}")
            lines.append(f"    Avg daily before: {kd['avg_daily_before']}")
            lines.append(f"    Avg daily after:  {kd['avg_daily_after']}")
            lines.append(f"    Change: {kd['change_pct']:+.1f}%")
            if kd["new_participants"]:
                lines.append(f"    New participants: {', '.join(kd['new_participants'][:5])}")
            if kd["lost_participants"]:
                lines.append(f"    Lost participants: {', '.join(kd['lost_participants'][:5])}")

    lines.extend([
        "",
        "OUTPUT FILES:",
        "  relationship_graph.html       - Interactive network graph",
        "  communication_timeline.html   - Volume over time chart",
        "  communication_heatmap.html    - Who-to-whom matrix",
        "  key_players.xlsx              - Ranked participant list",
        "  gap_analysis.xlsx             - Communication gaps",
        "  network_analysis.json         - Structured analysis data",
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
    parser = argparse.ArgumentParser(description="Communication Pattern Analyzer")
    parser.add_argument("--input", required=True, help="Communication data file or directory")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--date-range", help="Date range filter as 'YYYY-MM-DD:YYYY-MM-DD'")
    parser.add_argument("--key-dates", help="Comma-separated key dates for before/after analysis")
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

    # Parse key dates
    key_dates = []
    if args.key_dates:
        key_dates = [d.strip() for d in args.key_dates.split(",") if d.strip()]
        log(f"Key dates: {key_dates}")

    # Discover and parse files
    log("Discovering communication files...")
    files_to_parse = []
    if os.path.isfile(input_path):
        files_to_parse = [input_path]
    elif os.path.isdir(input_path):
        for root, dirs, filenames in os.walk(input_path):
            for fn in filenames:
                ext = Path(fn).suffix.lower()
                if ext in (".csv", ".xlsx", ".xls", ".txt"):
                    files_to_parse.append(os.path.join(root, fn))
    else:
        log(f"ERROR: Input path does not exist: {input_path}")
        sys.exit(1)

    if not files_to_parse:
        log("ERROR: No supported communication files found.")
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
    log(f"Total communications: {len(df)}")

    # Apply date range filter
    if date_start is not None or date_end is not None:
        before = len(df)
        if date_start is not None:
            df = df[(df["datetime"].isna()) | (df["datetime"] >= date_start)]
        if date_end is not None:
            df = df[(df["datetime"].isna()) | (df["datetime"] <= date_end)]
        log(f"Date filter: {before} -> {len(df)} communications")

    # Build communication graph
    log("Building communication graph...")
    G = build_communication_graph(df)
    log(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Compute centrality
    log("Computing centrality metrics...")
    centrality = compute_centrality(G)

    # Detect communities
    log("Detecting communities...")
    communities = detect_communities(G)
    num_communities = sum(1 for k in communities if k != "_partition")
    log(f"Communities found: {num_communities}")

    # Temporal analysis
    log("Analyzing temporal patterns...")
    temporal = analyze_temporal(df, key_dates=key_dates if key_dates else None)

    # Generate outputs
    log("Generating outputs...")
    create_network_graph(G, communities, output_dir)
    create_timeline(df, temporal, output_dir)
    create_heatmap(df, output_dir)
    write_key_players(centrality, output_dir)
    write_gap_analysis(temporal, output_dir)
    summary_text = write_analysis_summary(df, centrality, communities, temporal, output_dir)

    # Build serializable communities (exclude _partition)
    serializable_communities = {}
    for k, v in communities.items():
        if k == "_partition":
            continue
        serializable_communities[str(k)] = v

    # Write full analysis JSON
    # Convert centrality to top 50 for reasonable JSON size
    top_centrality = dict(sorted(centrality.items(), key=lambda x: -x[1]["pagerank"])[:50])

    report = {
        "total_communications": len(df),
        "participants": list(set(df["sender"].unique()) | set(df["recipient"].unique())),
        "files_processed": len(all_dfs),
        "files_failed": parse_errors,
        "graph": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
        },
        "centrality": top_centrality,
        "communities": serializable_communities,
        "temporal": {
            "spikes": temporal.get("spikes", []),
            "gaps": temporal.get("gaps", []),
            "key_date_analysis": temporal.get("key_date_analysis", []),
        },
    }
    report_path = os.path.join(output_dir, "network_analysis.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"  Analysis saved: {report_path}")

    # Print JSON summary to stdout for Claude to parse
    summary_json = {
        "status": "success",
        "total_communications": len(df),
        "participants": len(set(df["sender"].unique()) | set(df["recipient"].unique())),
        "communities": num_communities,
        "gaps": len(temporal.get("gaps", [])),
        "spikes": len(temporal.get("spikes", [])),
        "files_processed": len(all_dfs),
        "files_failed": parse_errors,
        "output_dir": output_dir,
        "outputs": {
            "network_analysis": report_path,
            "relationship_graph": os.path.join(output_dir, "relationship_graph.html"),
            "communication_timeline": os.path.join(output_dir, "communication_timeline.html"),
            "communication_heatmap": os.path.join(output_dir, "communication_heatmap.html"),
            "key_players": os.path.join(output_dir, "key_players.xlsx"),
            "gap_analysis": os.path.join(output_dir, "gap_analysis.xlsx"),
            "analysis_summary": os.path.join(output_dir, "analysis_summary.txt"),
        },
    }
    print(json.dumps(summary_json, indent=2, default=str))


if __name__ == "__main__":
    main()
