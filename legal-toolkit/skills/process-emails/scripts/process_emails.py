#!/usr/bin/env python3
"""
E-Discovery Email Processor

Ingests email archives (.eml, .msg, .mbox, or directories) and extracts
structured data for legal review: metadata, threads, duplicates, privilege
flags, communication network, and timeline visualizations.

Outputs JSON to stdout for Claude to parse. Progress/errors go to stderr.
"""
import argparse
import email
import email.utils
import email.policy
import hashlib
import json
import mailbox
import mimetypes
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

import pandas as pd
import networkx as nx
import plotly.graph_objects as go
from dateutil import parser as dateutil_parser

# Optional: extract-msg for .msg files
try:
    import extract_msg
    HAS_EXTRACT_MSG = True
except ImportError:
    HAS_EXTRACT_MSG = False


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def log(msg):
    """Print progress to stderr."""
    print(msg, file=sys.stderr)


def safe_decode(value):
    """Decode email header value safely."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return str(value)
    return str(value)


def parse_address_list(raw):
    """Parse a comma-separated address string into a list of (name, email) tuples."""
    if not raw:
        return []
    addresses = email.utils.getaddresses([raw])
    return [(safe_decode(name).strip(), addr.strip().lower()) for name, addr in addresses if addr]


def normalize_address(addr_tuple):
    """Return a clean email address string."""
    _, addr = addr_tuple
    return addr.lower().strip()


def extract_text_from_email_message(msg):
    """Extract plain text body from an email.message.Message object."""
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body_parts.append(payload.decode(charset, errors="replace"))
                    except Exception:
                        body_parts.append(payload.decode("utf-8", errors="replace"))
            elif ct == "text/html" and "attachment" not in cd and not body_parts:
                # Fallback: strip HTML tags if no plain text part
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        html = payload.decode(charset, errors="replace")
                    except Exception:
                        html = payload.decode("utf-8", errors="replace")
                    text = re.sub(r"<[^>]+>", " ", html)
                    text = re.sub(r"\s+", " ", text).strip()
                    body_parts.append(text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                body_parts.append(payload.decode(charset, errors="replace"))
            except Exception:
                body_parts.append(payload.decode("utf-8", errors="replace"))
    return "\n".join(body_parts)


def extract_attachments_from_message(msg, email_id, output_dir):
    """Extract attachments from an email.message.Message, return list of attachment info."""
    attachments = []
    if not msg.is_multipart():
        return attachments
    att_dir = os.path.join(output_dir, "attachments", email_id)
    for part in msg.walk():
        cd = str(part.get("Content-Disposition", ""))
        if "attachment" in cd or (part.get_content_maintype() not in ("text", "multipart")
                                   and "attachment" not in cd
                                   and part.get_filename()):
            filename = part.get_filename()
            if not filename:
                ext = mimetypes.guess_extension(part.get_content_type()) or ".bin"
                filename = f"attachment_{len(attachments)+1}{ext}"
            # Sanitize filename
            filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
            payload = part.get_payload(decode=True)
            if payload:
                if not os.path.exists(att_dir):
                    os.makedirs(att_dir, exist_ok=True)
                filepath = os.path.join(att_dir, filename)
                # Avoid overwrites
                base, ext = os.path.splitext(filepath)
                counter = 1
                while os.path.exists(filepath):
                    filepath = f"{base}_{counter}{ext}"
                    counter += 1
                with open(filepath, "wb") as f:
                    f.write(payload)
                attachments.append({
                    "filename": filename,
                    "size": len(payload),
                    "type": part.get_content_type(),
                    "path": filepath,
                })
    return attachments


def content_hash(text):
    """Generate a hash of email content for deduplication."""
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Email parsers
# ---------------------------------------------------------------------------

def parse_eml_file(filepath):
    """Parse a single .eml file."""
    with open(filepath, "rb") as f:
        msg = email.message_from_binary_file(f, policy=email.policy.default)
    return msg


def parse_msg_file(filepath):
    """Parse a single .msg file using extract-msg."""
    if not HAS_EXTRACT_MSG:
        log(f"  WARNING: extract-msg not installed, skipping .msg file: {filepath}")
        return None
    try:
        msg_obj = extract_msg.Message(filepath)
        # Convert to stdlib email.message.Message-like dict
        return _msg_to_record(msg_obj, filepath)
    except Exception as e:
        log(f"  ERROR parsing .msg file {filepath}: {e}")
        return None


def _msg_to_record(msg_obj, filepath):
    """Convert an extract_msg.Message to our internal record format directly."""
    raw_date = msg_obj.date
    if isinstance(raw_date, datetime):
        date_iso = raw_date.isoformat()
    elif raw_date:
        try:
            date_iso = dateutil_parser.parse(str(raw_date)).isoformat()
        except Exception:
            date_iso = ""
    else:
        date_iso = ""

    from_addr = msg_obj.sender or ""
    to_addrs = msg_obj.to or ""
    cc_addrs = msg_obj.cc or ""
    bcc_addrs = msg_obj.bcc or ""
    subject = msg_obj.subject or ""
    body = msg_obj.body or ""
    message_id = getattr(msg_obj, "message_id", "") or ""

    attachments = []
    if hasattr(msg_obj, "attachments") and msg_obj.attachments:
        for att in msg_obj.attachments:
            attachments.append({
                "filename": getattr(att, "longFilename", None) or getattr(att, "shortFilename", "unknown"),
                "size": len(att.data) if hasattr(att, "data") and att.data else 0,
                "type": getattr(att, "mimetype", "application/octet-stream") or "application/octet-stream",
            })

    record = {
        "source_file": filepath,
        "format": "msg",
        "message_id": message_id,
        "date": date_iso,
        "from": from_addr,
        "to": to_addrs,
        "cc": cc_addrs,
        "bcc": bcc_addrs,
        "subject": subject,
        "body": body,
        "in_reply_to": "",
        "references": "",
        "attachments": attachments,
        "attachment_count": len(attachments),
        "content_hash": content_hash(body),
        "_is_msg_record": True,
    }
    return record


def parse_mbox_file(filepath):
    """Parse an mbox file, yield email.message.Message objects."""
    mbox = mailbox.mbox(filepath)
    for msg in mbox:
        yield msg


def discover_email_files(directory):
    """Walk a directory and return lists of email files by type."""
    eml_files = []
    msg_files = []
    mbox_files = []
    for root, _dirs, files in os.walk(directory):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext == ".eml":
                eml_files.append(fpath)
            elif ext == ".msg":
                msg_files.append(fpath)
            elif ext == ".mbox":
                mbox_files.append(fpath)
    return eml_files, msg_files, mbox_files


# ---------------------------------------------------------------------------
# Record extraction from email.message.Message
# ---------------------------------------------------------------------------

def message_to_record(msg, source_file, fmt, output_dir, email_idx, extract_atts):
    """Convert an email.message.Message to a flat record dict."""
    message_id = safe_decode(msg.get("Message-ID", "")).strip()
    if not message_id:
        message_id = f"generated-{email_idx}-{hashlib.md5(source_file.encode()).hexdigest()[:8]}"

    # Parse date
    date_str = safe_decode(msg.get("Date", ""))
    date_iso = ""
    if date_str:
        try:
            parsed_date = dateutil_parser.parse(date_str, fuzzy=True)
            date_iso = parsed_date.isoformat()
        except Exception:
            date_iso = date_str

    from_raw = safe_decode(msg.get("From", ""))
    to_raw = safe_decode(msg.get("To", ""))
    cc_raw = safe_decode(msg.get("Cc", ""))
    bcc_raw = safe_decode(msg.get("Bcc", ""))
    subject = safe_decode(msg.get("Subject", ""))
    in_reply_to = safe_decode(msg.get("In-Reply-To", "")).strip()
    references = safe_decode(msg.get("References", "")).strip()

    body = extract_text_from_email_message(msg)

    # Attachments
    attachments = []
    if extract_atts:
        eid = re.sub(r"[^a-zA-Z0-9]", "_", message_id)[:60]
        attachments = extract_attachments_from_message(msg, eid, output_dir)
    else:
        # Just list them without extracting
        if msg.is_multipart():
            for part in msg.walk():
                cd = str(part.get("Content-Disposition", ""))
                if "attachment" in cd or (part.get_content_maintype() not in ("text", "multipart")
                                           and part.get_filename()):
                    fname = part.get_filename() or "unknown"
                    payload = part.get_payload(decode=True)
                    attachments.append({
                        "filename": fname,
                        "size": len(payload) if payload else 0,
                        "type": part.get_content_type(),
                    })

    record = {
        "source_file": source_file,
        "format": fmt,
        "message_id": message_id,
        "date": date_iso,
        "from": from_raw,
        "to": to_raw,
        "cc": cc_raw,
        "bcc": bcc_raw,
        "subject": subject,
        "body": body,
        "in_reply_to": in_reply_to,
        "references": references,
        "attachments": attachments,
        "attachment_count": len(attachments),
        "content_hash": content_hash(body),
    }
    return record


# ---------------------------------------------------------------------------
# Thread reconstruction
# ---------------------------------------------------------------------------

def reconstruct_threads(records):
    """Group emails into threads using Message-ID, In-Reply-To, References."""
    id_to_record = {}
    for r in records:
        mid = r["message_id"]
        if mid:
            id_to_record[mid] = r

    thread_map = {}  # message_id -> thread_id
    thread_counter = 0

    for r in records:
        mid = r["message_id"]
        refs = r.get("references", "")
        in_reply = r.get("in_reply_to", "")

        # Collect all referenced IDs
        ref_ids = []
        if refs:
            ref_ids.extend(re.findall(r"<[^>]+>", refs))
            ref_ids.extend([x.strip() for x in refs.split() if "@" in x and "<" not in x])
        if in_reply:
            ref_ids.append(in_reply.strip())

        # Find existing thread for any reference
        existing_thread = None
        for ref in ref_ids:
            ref_clean = ref.strip("<>").strip()
            if ref_clean in thread_map:
                existing_thread = thread_map[ref_clean]
                break
            if ref in thread_map:
                existing_thread = thread_map[ref]
                break

        if mid in thread_map:
            # Already assigned
            if existing_thread is not None and existing_thread != thread_map[mid]:
                # Merge threads
                old_thread = thread_map[mid]
                for k, v in list(thread_map.items()):
                    if v == old_thread:
                        thread_map[k] = existing_thread
        elif existing_thread is not None:
            thread_map[mid] = existing_thread
        else:
            thread_counter += 1
            thread_map[mid] = f"thread_{thread_counter:04d}"

        # Assign all refs to the same thread
        tid = thread_map.get(mid)
        if tid:
            for ref in ref_ids:
                ref_clean = ref.strip("<>").strip()
                if ref_clean not in thread_map:
                    thread_map[ref_clean] = tid
                if ref not in thread_map:
                    thread_map[ref] = tid

    # Assign thread IDs to records
    for r in records:
        mid = r["message_id"]
        r["thread_id"] = thread_map.get(mid, f"thread_{mid[:12]}")

    # Build thread structure
    threads = defaultdict(list)
    for r in records:
        threads[r["thread_id"]].append({
            "message_id": r["message_id"],
            "date": r["date"],
            "from": r["from"],
            "to": r["to"],
            "subject": r["subject"],
        })

    # Sort each thread by date
    for tid in threads:
        threads[tid].sort(key=lambda x: x["date"] or "")

    return dict(threads)


# ---------------------------------------------------------------------------
# De-duplication
# ---------------------------------------------------------------------------

def find_duplicates(records):
    """Detect exact and near-duplicate messages."""
    seen_ids = {}
    seen_hashes = {}
    duplicates = []

    for i, r in enumerate(records):
        mid = r["message_id"]
        chash = r["content_hash"]
        is_dup = False
        dup_reason = ""

        # Check by Message-ID
        if mid and mid in seen_ids:
            is_dup = True
            dup_reason = f"Duplicate Message-ID (same as email #{seen_ids[mid]+1})"
        elif mid:
            seen_ids[mid] = i

        # Check by content hash
        if not is_dup and chash and chash in seen_hashes:
            is_dup = True
            dup_reason = f"Duplicate content hash (same as email #{seen_hashes[chash]+1})"
        elif chash:
            seen_hashes[chash] = i

        r["is_duplicate"] = is_dup
        r["duplicate_reason"] = dup_reason
        if is_dup:
            duplicates.append({
                "email_index": i + 1,
                "message_id": mid,
                "date": r["date"],
                "from": r["from"],
                "subject": r["subject"],
                "reason": dup_reason,
            })

    return duplicates


# ---------------------------------------------------------------------------
# Privilege flag detection
# ---------------------------------------------------------------------------

PRIVILEGE_KEYWORDS = [
    "privileged", "attorney-client", "attorney client",
    "work product", "legal advice", "counsel",
    "confidential communication", "litigation hold",
    "attorney work product", "protected communication",
]


def detect_privilege_flags(records, attorney_names=None, privileged_domains=None):
    """Scan emails for privilege indicators."""
    attorney_list = []
    if attorney_names:
        attorney_list = [n.strip().lower() for n in attorney_names.split(",") if n.strip()]

    domain_list = []
    if privileged_domains:
        domain_list = [d.strip().lower() for d in privileged_domains.split(",") if d.strip()]

    flags = []

    for i, r in enumerate(records):
        reasons = []

        # Keyword scanning in subject + body
        text = f"{r.get('subject', '')} {r.get('body', '')}".lower()
        for kw in PRIVILEGE_KEYWORDS:
            if kw in text:
                reasons.append(f"Keyword: '{kw}'")
                break  # One keyword match is enough

        # Attorney name matching
        all_addrs = f"{r.get('from', '')} {r.get('to', '')} {r.get('cc', '')} {r.get('bcc', '')}".lower()
        combined_text = f"{all_addrs} {text}"
        for name in attorney_list:
            if name in combined_text:
                reasons.append(f"Attorney name: '{name}'")
                break

        # Domain matching
        for domain in domain_list:
            if domain in all_addrs:
                reasons.append(f"Privileged domain: '{domain}'")
                break

        r["privilege_flag"] = len(reasons) > 0
        r["privilege_reasons"] = reasons

        if reasons:
            flags.append({
                "email_index": i + 1,
                "message_id": r["message_id"],
                "date": r["date"],
                "from": r["from"],
                "to": r["to"],
                "subject": r["subject"],
                "reasons": "; ".join(reasons),
            })

    return flags


# ---------------------------------------------------------------------------
# Communication network
# ---------------------------------------------------------------------------

def build_communication_network(records):
    """Build a networkx graph of email communications."""
    G = nx.DiGraph()
    edge_weights = defaultdict(int)

    for r in records:
        if r.get("is_duplicate"):
            continue
        from_addrs = parse_address_list(r.get("from", ""))
        to_addrs = parse_address_list(r.get("to", ""))
        cc_addrs = parse_address_list(r.get("cc", ""))

        senders = [normalize_address(a) for a in from_addrs if a[1]]
        recipients = [normalize_address(a) for a in to_addrs + cc_addrs if a[1]]

        for s in senders:
            if not G.has_node(s):
                G.add_node(s, sent=0, received=0)
            G.nodes[s]["sent"] = G.nodes[s].get("sent", 0) + 1

            for recip in recipients:
                if recip == s:
                    continue
                if not G.has_node(recip):
                    G.add_node(recip, sent=0, received=0)
                G.nodes[recip]["received"] = G.nodes[recip].get("received", 0) + 1
                edge_weights[(s, recip)] += 1

    for (s, r), w in edge_weights.items():
        G.add_edge(s, r, weight=w)

    return G


def generate_network_visualization(G, output_path):
    """Generate an interactive network graph using plotly."""
    if len(G.nodes()) == 0:
        log("  No nodes in communication network; skipping visualization.")
        return

    # Use spring layout
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    # Edges
    edge_x, edge_y = [], []
    edge_texts = []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        edge_texts.append(f"{u} -> {v}: {data.get('weight', 1)} emails")

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    # Nodes
    node_x, node_y, node_text, node_size = [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        sent = G.nodes[node].get("sent", 0)
        received = G.nodes[node].get("received", 0)
        total = sent + received
        node_text.append(f"{node}<br>Sent: {sent}<br>Received: {received}<br>Total: {total}")
        node_size.append(max(10, min(50, total * 2)))

    # Color by degree centrality
    centrality = nx.degree_centrality(G)
    node_color = [centrality.get(n, 0) for n in G.nodes()]

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        hoverinfo="text",
        text=[n.split("@")[0] for n in G.nodes()],
        textposition="top center",
        textfont=dict(size=8),
        hovertext=node_text,
        marker=dict(
            showscale=True,
            colorscale="YlOrRd",
            color=node_color,
            size=node_size,
            colorbar=dict(
                thickness=15,
                title="Centrality",
                xanchor="left",
            ),
            line_width=2,
        ),
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title="E-Discovery Communication Network",
            titlefont_size=16,
            showlegend=False,
            hovermode="closest",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            template="plotly_white",
            height=800,
            width=1200,
        ),
    )
    fig.write_html(output_path)
    log(f"  Network visualization: {output_path}")


# ---------------------------------------------------------------------------
# Timeline visualization
# ---------------------------------------------------------------------------

def generate_timeline(records, output_path):
    """Generate a communication volume timeline using plotly."""
    dates = []
    for r in records:
        if r.get("is_duplicate"):
            continue
        d = r.get("date", "")
        if d:
            try:
                parsed = dateutil_parser.parse(d)
                dates.append(parsed.date())
            except Exception:
                continue

    if not dates:
        log("  No parseable dates; skipping timeline.")
        return

    date_counts = defaultdict(int)
    for d in dates:
        date_counts[d] += 1

    sorted_dates = sorted(date_counts.keys())
    counts = [date_counts[d] for d in sorted_dates]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[str(d) for d in sorted_dates],
        y=counts,
        marker_color="steelblue",
    ))
    fig.update_layout(
        title="E-Discovery Email Volume Over Time",
        xaxis_title="Date",
        yaxis_title="Number of Emails",
        template="plotly_white",
        height=500,
        width=1200,
    )
    fig.write_html(output_path)
    log(f"  Timeline visualization: {output_path}")


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def write_outputs(records, threads, duplicates, privilege_flags, G, output_dir):
    """Write all output files."""
    # 1. email_metadata.xlsx
    log("  Writing email_metadata.xlsx...")
    meta_rows = []
    for i, r in enumerate(records):
        meta_rows.append({
            "Index": i + 1,
            "Date": r.get("date", ""),
            "From": r.get("from", ""),
            "To": r.get("to", ""),
            "CC": r.get("cc", ""),
            "BCC": r.get("bcc", ""),
            "Subject": r.get("subject", ""),
            "Attachment Count": r.get("attachment_count", 0),
            "Thread ID": r.get("thread_id", ""),
            "Privilege Flag": "YES" if r.get("privilege_flag") else "",
            "Privilege Reasons": "; ".join(r.get("privilege_reasons", [])),
            "Duplicate": "YES" if r.get("is_duplicate") else "",
            "Duplicate Reason": r.get("duplicate_reason", ""),
            "Message-ID": r.get("message_id", ""),
            "Source File": r.get("source_file", ""),
            "Format": r.get("format", ""),
        })
    df_meta = pd.DataFrame(meta_rows)
    meta_path = os.path.join(output_dir, "email_metadata.xlsx")
    df_meta.to_excel(meta_path, index=False, engine="xlsxwriter")

    # 2. threads.json
    log("  Writing threads.json...")
    threads_path = os.path.join(output_dir, "threads.json")
    with open(threads_path, "w", encoding="utf-8") as f:
        json.dump(threads, f, indent=2, default=str)

    # 3. privilege_flags.xlsx
    if privilege_flags:
        log("  Writing privilege_flags.xlsx...")
        df_priv = pd.DataFrame(privilege_flags)
        priv_path = os.path.join(output_dir, "privilege_flags.xlsx")
        df_priv.to_excel(priv_path, index=False, engine="xlsxwriter")

    # 4. duplicates.xlsx
    if duplicates:
        log("  Writing duplicates.xlsx...")
        df_dup = pd.DataFrame(duplicates)
        dup_path = os.path.join(output_dir, "duplicates.xlsx")
        df_dup.to_excel(dup_path, index=False, engine="xlsxwriter")

    # 5. Communication network visualization
    log("  Generating communication network...")
    net_path = os.path.join(output_dir, "communication_network.html")
    generate_network_visualization(G, net_path)

    # 6. Timeline visualization
    log("  Generating timeline...")
    timeline_path = os.path.join(output_dir, "communication_timeline.html")
    generate_timeline(records, timeline_path)

    # 7. processing_summary.txt
    log("  Writing processing_summary.txt...")
    total = len(records)
    unique = sum(1 for r in records if not r.get("is_duplicate"))
    dup_count = sum(1 for r in records if r.get("is_duplicate"))
    priv_count = sum(1 for r in records if r.get("privilege_flag"))
    att_count = sum(r.get("attachment_count", 0) for r in records)
    thread_count = len(threads)

    # Date range
    parsed_dates = []
    for r in records:
        d = r.get("date", "")
        if d:
            try:
                parsed_dates.append(dateutil_parser.parse(d))
            except Exception:
                pass
    date_range_str = ""
    if parsed_dates:
        earliest = min(parsed_dates).strftime("%Y-%m-%d")
        latest = max(parsed_dates).strftime("%Y-%m-%d")
        date_range_str = f"{earliest} to {latest}"

    # Format breakdown
    format_counts = defaultdict(int)
    for r in records:
        format_counts[r.get("format", "unknown")] += 1

    # Top communicators
    top_senders = defaultdict(int)
    for r in records:
        if not r.get("is_duplicate"):
            addrs = parse_address_list(r.get("from", ""))
            for _, addr in addrs:
                if addr:
                    top_senders[addr] += 1
    sorted_senders = sorted(top_senders.items(), key=lambda x: -x[1])[:10]

    summary_lines = [
        "=" * 60,
        "E-DISCOVERY EMAIL PROCESSING SUMMARY",
        "=" * 60,
        "",
        f"Total emails processed: {total}",
        f"Unique emails: {unique}",
        f"Duplicates found: {dup_count}",
        f"Threads reconstructed: {thread_count}",
        f"Attachments found: {att_count}",
        f"Privilege flags: {priv_count}",
        f"Date range: {date_range_str or 'N/A'}",
        "",
        "Format breakdown:",
    ]
    for fmt, cnt in sorted(format_counts.items()):
        summary_lines.append(f"  {fmt}: {cnt}")
    summary_lines.append("")
    summary_lines.append("Top senders:")
    for addr, cnt in sorted_senders:
        summary_lines.append(f"  {addr}: {cnt} emails")
    summary_lines.append("")
    summary_lines.append("=" * 60)
    summary_lines.append("Output files:")
    summary_lines.append(f"  email_metadata.xlsx - Master email spreadsheet")
    summary_lines.append(f"  threads.json - Reconstructed conversation threads")
    summary_lines.append(f"  communication_network.html - Interactive network graph")
    summary_lines.append(f"  communication_timeline.html - Volume over time")
    if privilege_flags:
        summary_lines.append(f"  privilege_flags.xlsx - {priv_count} flagged emails")
    if duplicates:
        summary_lines.append(f"  duplicates.xlsx - {dup_count} duplicate emails")
    if os.path.exists(os.path.join(output_dir, "attachments")):
        summary_lines.append(f"  attachments/ - Extracted email attachments")
    summary_lines.append("=" * 60)

    summary_text = "\n".join(summary_lines)
    summary_path = os.path.join(output_dir, "processing_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    return {
        "total_emails": total,
        "unique_emails": unique,
        "duplicates": dup_count,
        "threads": thread_count,
        "attachments": att_count,
        "privilege_flags": priv_count,
        "date_range": date_range_str,
        "format_breakdown": dict(format_counts),
        "top_senders": sorted_senders[:5],
        "output_dir": output_dir,
        "files_generated": [
            "email_metadata.xlsx",
            "threads.json",
            "communication_network.html",
            "communication_timeline.html",
            "processing_summary.txt",
        ] + (["privilege_flags.xlsx"] if privilege_flags else [])
          + (["duplicates.xlsx"] if duplicates else []),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="E-Discovery Email Processor")
    parser.add_argument("--input", required=True, help="Email file or directory path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--attorney-names", default=None,
                        help="Comma-separated attorney names for privilege detection")
    parser.add_argument("--privileged-domains", default=None,
                        help="Comma-separated law firm domains for privilege detection")
    parser.add_argument("--extract-attachments", action="store_true",
                        help="Extract email attachments to output directory")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(input_path):
        log(f"ERROR: Input path does not exist: {input_path}")
        sys.exit(1)

    records = []
    email_idx = 0

    if os.path.isdir(input_path):
        log(f"Scanning directory: {input_path}")
        eml_files, msg_files, mbox_files = discover_email_files(input_path)
        total_files = len(eml_files) + len(msg_files) + len(mbox_files)
        log(f"Found {total_files} email files ({len(eml_files)} .eml, {len(msg_files)} .msg, {len(mbox_files)} .mbox)")

        if total_files == 0:
            log("ERROR: No email files found in directory.")
            sys.exit(1)

        for fpath in eml_files:
            email_idx += 1
            log(f"  [{email_idx}] Parsing .eml: {os.path.basename(fpath)}")
            try:
                msg = parse_eml_file(fpath)
                record = message_to_record(msg, fpath, "eml", output_dir, email_idx, args.extract_attachments)
                records.append(record)
            except Exception as e:
                log(f"    ERROR: {e}")

        for fpath in msg_files:
            email_idx += 1
            log(f"  [{email_idx}] Parsing .msg: {os.path.basename(fpath)}")
            result = parse_msg_file(fpath)
            if result and result.get("_is_msg_record"):
                result.pop("_is_msg_record", None)
                records.append(result)

        for fpath in mbox_files:
            log(f"  Parsing .mbox: {os.path.basename(fpath)}")
            try:
                for msg in parse_mbox_file(fpath):
                    email_idx += 1
                    if email_idx % 100 == 0:
                        log(f"    [{email_idx}] Processing...")
                    record = message_to_record(msg, fpath, "mbox", output_dir, email_idx, args.extract_attachments)
                    records.append(record)
            except Exception as e:
                log(f"    ERROR reading mbox: {e}")

    elif os.path.isfile(input_path):
        ext = os.path.splitext(input_path)[1].lower()
        if ext == ".eml":
            log(f"Parsing .eml file: {input_path}")
            email_idx += 1
            msg = parse_eml_file(input_path)
            record = message_to_record(msg, input_path, "eml", output_dir, email_idx, args.extract_attachments)
            records.append(record)
        elif ext == ".msg":
            log(f"Parsing .msg file: {input_path}")
            email_idx += 1
            result = parse_msg_file(input_path)
            if result and result.get("_is_msg_record"):
                result.pop("_is_msg_record", None)
                records.append(result)
        elif ext == ".mbox":
            log(f"Parsing .mbox file: {input_path}")
            for msg in parse_mbox_file(input_path):
                email_idx += 1
                if email_idx % 100 == 0:
                    log(f"  [{email_idx}] Processing...")
                record = message_to_record(msg, input_path, "mbox", output_dir, email_idx, args.extract_attachments)
                records.append(record)
        else:
            log(f"ERROR: Unsupported file type: {ext}")
            log("Supported: .eml, .msg, .mbox")
            sys.exit(1)
    else:
        log(f"ERROR: Path is neither file nor directory: {input_path}")
        sys.exit(1)

    if not records:
        log("ERROR: No emails could be parsed.")
        sys.exit(1)

    log(f"\nTotal emails parsed: {len(records)}")

    # Thread reconstruction
    log("Reconstructing threads...")
    threads = reconstruct_threads(records)
    log(f"  Threads found: {len(threads)}")

    # De-duplication
    log("Detecting duplicates...")
    duplicates = find_duplicates(records)
    log(f"  Duplicates found: {len(duplicates)}")

    # Privilege detection
    log("Scanning for privilege flags...")
    privilege_flags = detect_privilege_flags(
        records,
        attorney_names=args.attorney_names,
        privileged_domains=args.privileged_domains,
    )
    log(f"  Privilege flags: {len(privilege_flags)}")

    # Communication network
    log("Building communication network...")
    G = build_communication_network(records)
    log(f"  Network nodes: {len(G.nodes())}, edges: {len(G.edges())}")

    # Write all outputs
    log("\nWriting outputs...")
    result = write_outputs(records, threads, duplicates, privilege_flags, G, output_dir)

    log(f"\nProcessing complete. Output: {output_dir}")

    # Print JSON to stdout for Claude
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
