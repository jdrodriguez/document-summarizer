#!/usr/bin/env python3
"""
Entity & Relationship Mapper

Extracts named entities from legal documents using spaCy NLP and maps
relationships between them via co-occurrence analysis and network graphs.

Outputs JSON to stdout for Claude to parse. Progress/errors go to stderr.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

import pandas as pd
import networkx as nx
import plotly.graph_objects as go
try:
    import spacy
    HAS_SPACY = True
except ImportError:
    spacy = None
    HAS_SPACY = False

# Optional: PDF extraction
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# DOCX extraction
try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def log(msg):
    """Print progress to stderr."""
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(filepath):
    """Extract text from a PDF file."""
    if HAS_PDFPLUMBER:
        try:
            pages = []
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
            if pages:
                return "\n\n".join(pages)
        except Exception as e:
            log(f"  pdfplumber failed: {e}, trying PyMuPDF...")

    if HAS_PYMUPDF:
        try:
            doc = fitz.open(filepath)
            pages = []
            for page in doc:
                text = page.get_text()
                if text:
                    pages.append(text)
            doc.close()
            if pages:
                return "\n\n".join(pages)
        except Exception as e:
            log(f"  PyMuPDF failed: {e}")

    log(f"  WARNING: No PDF reader available for {filepath}")
    return ""


def extract_text_from_docx(filepath):
    """Extract text from a DOCX file."""
    if not HAS_DOCX:
        log(f"  WARNING: python-docx not available for {filepath}")
        return ""
    try:
        doc = docx.Document(filepath)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        log(f"  ERROR extracting DOCX: {e}")
        return ""


def extract_text_from_file(filepath):
    """Extract text from a file based on its extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(filepath)
    elif ext == ".docx":
        return extract_text_from_docx(filepath)
    elif ext in (".txt", ".md"):
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            log(f"  ERROR reading {filepath}: {e}")
            return ""
    else:
        log(f"  Unsupported file type: {ext}")
        return ""


def discover_documents(directory):
    """Walk a directory and return supported document files."""
    supported = {".pdf", ".docx", ".txt", ".md"}
    files = []
    for root, _dirs, filenames in os.walk(directory):
        for fname in sorted(filenames):
            if fname.startswith("."):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in supported:
                files.append(os.path.join(root, fname))
    return files


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------

ENTITY_TYPES_OF_INTEREST = {
    "PERSON", "ORG", "DATE", "MONEY", "GPE", "LAW", "NORP", "FAC", "EVENT",
}


def split_into_paragraphs(text):
    """Split text into paragraphs for co-occurrence analysis."""
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def extract_entities_from_text(nlp, text, source_file):
    """Extract named entities from text using spaCy."""
    entities = []
    paragraphs = split_into_paragraphs(text)

    # Process in chunks to avoid spaCy max length issues
    max_chunk = 100000  # chars
    chunks = []
    current_chunk = ""
    current_paras = []

    for para in paragraphs:
        if len(current_chunk) + len(para) > max_chunk and current_chunk:
            chunks.append((current_chunk, list(current_paras)))
            current_chunk = ""
            current_paras = []
        current_chunk += para + "\n\n"
        current_paras.append(para)
    if current_chunk:
        chunks.append((current_chunk, list(current_paras)))

    para_entities = []  # List of (para_index, list_of_entities) for co-occurrence

    global_para_idx = 0
    for chunk_text, chunk_paras in chunks:
        try:
            doc = nlp(chunk_text)
        except Exception as e:
            log(f"    spaCy processing error: {e}")
            global_para_idx += len(chunk_paras)
            continue

        for ent in doc.ents:
            if ent.label_ not in ENTITY_TYPES_OF_INTEREST:
                continue

            # Get context (surrounding sentence)
            sent = ent.sent
            context = sent.text.strip() if sent else ""
            if len(context) > 300:
                context = context[:300] + "..."

            # Determine which paragraph this entity is in
            ent_start = ent.start_char
            char_count = 0
            para_idx = global_para_idx
            for i, para in enumerate(chunk_paras):
                if char_count + len(para) + 2 >= ent_start:
                    para_idx = global_para_idx + i
                    break
                char_count += len(para) + 2  # +2 for \n\n

            entity_record = {
                "text": ent.text.strip(),
                "label": ent.label_,
                "source_file": os.path.basename(source_file),
                "source_path": source_file,
                "context": context,
                "paragraph_index": para_idx,
            }
            entities.append(entity_record)

        global_para_idx += len(chunk_paras)

    return entities


def normalize_entity_name(text):
    """Normalize an entity name for deduplication."""
    # Remove common titles
    text = re.sub(r"^(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Hon\.|Judge|Attorney|Atty\.)\s+", "", text.strip())
    # Remove trailing punctuation
    text = text.strip(" .,;:\"'")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_entities(entities):
    """Merge entity variants into canonical forms."""
    # Group by label
    by_label = defaultdict(list)
    for e in entities:
        by_label[e["label"]].append(e)

    # For each label, find groups where one name is a substring of another
    canonical_map = {}  # normalized_text -> canonical_text
    for label, ents in by_label.items():
        names = Counter()
        for e in ents:
            norm = normalize_entity_name(e["text"])
            if norm:
                names[norm] += 1

        sorted_names = sorted(names.keys(), key=lambda x: -len(x))
        assigned = {}

        for name in sorted_names:
            if name in assigned:
                continue
            # This is a potential canonical name
            assigned[name] = name
            canonical_map[(name, label)] = name

            # Find shorter variants
            name_lower = name.lower()
            for other in sorted_names:
                if other == name or other in assigned:
                    continue
                other_lower = other.lower()
                # Check if other is a suffix (last name) or the full name contains it
                if (other_lower in name_lower or
                        name_lower.endswith(other_lower) or
                        name_lower.startswith(other_lower)):
                    if len(other) >= 3:  # Avoid very short matches
                        assigned[other] = name
                        canonical_map[(other, label)] = name

    # Apply normalization
    for e in entities:
        norm = normalize_entity_name(e["text"])
        key = (norm, e["label"])
        e["normalized_name"] = canonical_map.get(key, norm)

    return entities


# ---------------------------------------------------------------------------
# Relationship analysis
# ---------------------------------------------------------------------------

def build_relationship_graph(entities):
    """Build a co-occurrence based relationship graph."""
    G = nx.Graph()

    # Group entities by (source_file, paragraph_index) for co-occurrence
    para_groups = defaultdict(set)
    entity_info = {}  # normalized_name -> {label, count, sources}

    for e in entities:
        name = e["normalized_name"]
        label = e["label"]
        source = e["source_file"]
        para_key = (source, e["paragraph_index"])
        para_groups[para_key].add((name, label))

        if name not in entity_info:
            entity_info[name] = {
                "label": label,
                "count": 0,
                "sources": set(),
                "first_context": e.get("context", ""),
            }
        entity_info[name]["count"] += 1
        entity_info[name]["sources"].add(source)

    # Add nodes
    for name, info in entity_info.items():
        G.add_node(name,
                    label=info["label"],
                    count=info["count"],
                    sources=list(info["sources"]),
                    first_context=info["first_context"])

    # Add edges based on co-occurrence
    edge_weights = defaultdict(int)
    for para_key, ent_set in para_groups.items():
        ent_list = list(ent_set)
        for i in range(len(ent_list)):
            for j in range(i + 1, len(ent_list)):
                name_a, _ = ent_list[i]
                name_b, _ = ent_list[j]
                if name_a != name_b:
                    edge_key = tuple(sorted([name_a, name_b]))
                    edge_weights[edge_key] += 1

    for (a, b), weight in edge_weights.items():
        G.add_edge(a, b, weight=weight)

    return G


def compute_centrality(G):
    """Compute centrality metrics for the graph."""
    if len(G.nodes()) == 0:
        return {}
    metrics = {}
    try:
        degree_cent = nx.degree_centrality(G)
        betweenness = nx.betweenness_centrality(G)
        for node in G.nodes():
            metrics[node] = {
                "degree_centrality": round(degree_cent.get(node, 0), 4),
                "betweenness_centrality": round(betweenness.get(node, 0), 4),
                "degree": G.degree(node),
            }
    except Exception as e:
        log(f"  Centrality computation error: {e}")
    return metrics


def detect_communities(G):
    """Detect communities in the entity graph."""
    communities = []
    try:
        from networkx.algorithms.community import greedy_modularity_communities
        comms = greedy_modularity_communities(G)
        for i, comm in enumerate(comms):
            communities.append({
                "community_id": i + 1,
                "members": sorted(list(comm)),
                "size": len(comm),
            })
    except Exception as e:
        log(f"  Community detection error: {e}")
    return communities


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

LABEL_COLORS = {
    "PERSON": "#FF6B6B",
    "ORG": "#4ECDC4",
    "DATE": "#45B7D1",
    "MONEY": "#96CEB4",
    "GPE": "#FFEAA7",
    "LAW": "#DDA0DD",
    "NORP": "#98D8C8",
    "FAC": "#F7DC6F",
    "EVENT": "#BB8FCE",
}


def generate_relationship_graph(G, output_path):
    """Generate an interactive plotly network graph."""
    if len(G.nodes()) == 0:
        log("  No entities for visualization; skipping.")
        return

    # Layout
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    # Create edge traces
    edge_traces = []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        weight = data.get("weight", 1)
        edge_traces.append(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line=dict(width=max(0.5, min(4, weight * 0.5)), color="#CCCCCC"),
            hoverinfo="none",
            showlegend=False,
        ))

    # Create node traces by label
    label_groups = defaultdict(list)
    for node in G.nodes():
        label = G.nodes[node].get("label", "UNKNOWN")
        label_groups[label].append(node)

    node_traces = []
    for label, nodes in label_groups.items():
        xs, ys, texts, sizes = [], [], [], []
        for node in nodes:
            x, y = pos[node]
            xs.append(x)
            ys.append(y)
            count = G.nodes[node].get("count", 1)
            sources = G.nodes[node].get("sources", [])
            context = G.nodes[node].get("first_context", "")
            if len(context) > 150:
                context = context[:150] + "..."
            texts.append(
                f"<b>{node}</b><br>"
                f"Type: {label}<br>"
                f"Mentions: {count}<br>"
                f"Documents: {len(sources)}<br>"
                f"Context: {context}"
            )
            sizes.append(max(10, min(50, count * 3)))

        color = LABEL_COLORS.get(label, "#999999")
        node_traces.append(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            name=label,
            text=[n[:20] for n in nodes],
            textposition="top center",
            textfont=dict(size=8),
            hovertext=texts,
            hoverinfo="text",
            marker=dict(
                size=sizes,
                color=color,
                line=dict(width=1, color="white"),
            ),
        ))

    fig = go.Figure(
        data=edge_traces + node_traces,
        layout=go.Layout(
            title="Entity Relationship Graph",
            titlefont_size=16,
            showlegend=True,
            hovermode="closest",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            template="plotly_white",
            height=900,
            width=1200,
            legend=dict(
                title="Entity Types",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
            ),
        ),
    )
    fig.write_html(output_path)
    log(f"  Relationship graph: {output_path}")


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def write_outputs(entities, G, centrality, communities, documents, output_dir, min_mentions):
    """Write all output files."""

    # Aggregate entity data
    entity_db = defaultdict(lambda: {
        "name": "",
        "label": "",
        "count": 0,
        "sources": set(),
        "first_context": "",
        "contexts": [],
    })

    for e in entities:
        name = e["normalized_name"]
        label = e["label"]
        key = (name, label)
        rec = entity_db[key]
        rec["name"] = name
        rec["label"] = label
        rec["count"] += 1
        rec["sources"].add(e["source_file"])
        if not rec["first_context"]:
            rec["first_context"] = e.get("context", "")
        if len(rec["contexts"]) < 5:
            rec["contexts"].append(e.get("context", ""))

    # Filter by min_mentions
    filtered_db = {k: v for k, v in entity_db.items() if v["count"] >= min_mentions}

    # 1. entity_database.xlsx
    log("  Writing entity_database.xlsx...")
    rows = []
    for (name, label), info in sorted(filtered_db.items(), key=lambda x: -x[1]["count"]):
        rows.append({
            "Entity": name,
            "Type": label,
            "Mentions": info["count"],
            "Documents": ", ".join(sorted(info["sources"])),
            "Document Count": len(info["sources"]),
            "First Context": info["first_context"],
        })
    df_entities = pd.DataFrame(rows)
    if not df_entities.empty:
        df_entities.to_excel(os.path.join(output_dir, "entity_database.xlsx"),
                             index=False, engine="xlsxwriter")

    # 2. relationship_graph.html
    log("  Generating relationship graph...")
    generate_relationship_graph(G, os.path.join(output_dir, "relationship_graph.html"))

    # 3. cross_reference_matrix.xlsx
    log("  Writing cross_reference_matrix.xlsx...")
    if documents and filtered_db:
        doc_names = sorted(set(os.path.basename(d) for d in documents))
        matrix_rows = []
        for (name, label), info in sorted(filtered_db.items(), key=lambda x: -x[1]["count"]):
            row = {"Entity": name, "Type": label, "Total": info["count"]}
            for doc in doc_names:
                row[doc] = "X" if doc in info["sources"] else ""
            matrix_rows.append(row)
        df_matrix = pd.DataFrame(matrix_rows)
        df_matrix.to_excel(os.path.join(output_dir, "cross_reference_matrix.xlsx"),
                           index=False, engine="xlsxwriter")

    # 4. timeline_dates.xlsx
    log("  Writing timeline_dates.xlsx...")
    date_rows = []
    for e in entities:
        if e["label"] == "DATE":
            date_rows.append({
                "Date Text": e["normalized_name"],
                "Context": e.get("context", ""),
                "Source Document": e["source_file"],
            })
    if date_rows:
        df_dates = pd.DataFrame(date_rows)
        df_dates.to_excel(os.path.join(output_dir, "timeline_dates.xlsx"),
                          index=False, engine="xlsxwriter")

    # 5. financial_mentions.xlsx
    log("  Writing financial_mentions.xlsx...")
    money_rows = []
    for e in entities:
        if e["label"] == "MONEY":
            money_rows.append({
                "Amount": e["normalized_name"],
                "Context": e.get("context", ""),
                "Source Document": e["source_file"],
            })
    if money_rows:
        df_money = pd.DataFrame(money_rows)
        df_money.to_excel(os.path.join(output_dir, "financial_mentions.xlsx"),
                          index=False, engine="xlsxwriter")

    # 6. entity_summary.txt
    log("  Writing entity_summary.txt...")
    type_counts = Counter()
    for (_, label), info in filtered_db.items():
        type_counts[label] += info["count"]

    top_entities = sorted(filtered_db.values(), key=lambda x: -x["count"])[:20]

    # Most connected
    top_central = sorted(centrality.items(), key=lambda x: -x[1].get("degree_centrality", 0))[:10]

    summary_lines = [
        "=" * 60,
        "ENTITY & RELATIONSHIP ANALYSIS SUMMARY",
        "=" * 60,
        "",
        f"Documents analyzed: {len(documents)}",
        f"Total unique entities (>= {min_mentions} mentions): {len(filtered_db)}",
        "",
        "Entities by type:",
    ]
    for label, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        summary_lines.append(f"  {label}: {count} mentions")

    summary_lines.extend(["", "Top entities by frequency:"])
    for info in top_entities:
        summary_lines.append(f"  [{info['label']}] {info['name']}: {info['count']} mentions in {len(info['sources'])} docs")

    summary_lines.extend(["", "Most connected entities (by centrality):"])
    for name, metrics in top_central:
        node_label = G.nodes[name].get("label", "?") if name in G.nodes() else "?"
        summary_lines.append(
            f"  [{node_label}] {name}: degree={metrics.get('degree', 0)}, "
            f"centrality={metrics.get('degree_centrality', 0):.3f}"
        )

    if communities:
        summary_lines.extend(["", f"Entity clusters detected: {len(communities)}"])
        for comm in communities[:5]:
            members_preview = ", ".join(comm["members"][:5])
            if len(comm["members"]) > 5:
                members_preview += f" ... (+{len(comm['members'])-5} more)"
            summary_lines.append(f"  Cluster {comm['community_id']} ({comm['size']} entities): {members_preview}")

    summary_lines.extend([
        "",
        "=" * 60,
        "Output files:",
        "  entity_database.xlsx - Complete entity database",
        "  relationship_graph.html - Interactive network graph",
        "  cross_reference_matrix.xlsx - Entity-document matrix",
        "  timeline_dates.xlsx - Date entities with context",
        "  financial_mentions.xlsx - Money entities with context",
        "  entity_summary.txt - This summary",
        "  entities.json - Structured data for programmatic use",
        "=" * 60,
    ])

    summary_text = "\n".join(summary_lines)
    with open(os.path.join(output_dir, "entity_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary_text)

    # 7. entities.json
    log("  Writing entities.json...")
    json_data = {
        "documents_analyzed": len(documents),
        "total_entities": len(filtered_db),
        "entity_type_counts": dict(type_counts),
        "entities": [],
        "communities": communities,
        "centrality": {k: v for k, v in centrality.items()},
    }
    for (name, label), info in sorted(filtered_db.items(), key=lambda x: -x[1]["count"]):
        json_data["entities"].append({
            "name": name,
            "type": label,
            "count": info["count"],
            "sources": sorted(info["sources"]),
            "first_context": info["first_context"],
            "centrality": centrality.get(name, {}),
        })
    with open(os.path.join(output_dir, "entities.json"), "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, default=str)

    # Build result summary for stdout
    return {
        "documents_analyzed": len(documents),
        "total_entities": len(filtered_db),
        "entity_type_counts": dict(type_counts),
        "top_entities": [
            {"name": e["name"], "type": e["label"], "count": e["count"]}
            for e in top_entities[:10]
        ],
        "most_connected": [
            {"name": name, "centrality": metrics.get("degree_centrality", 0)}
            for name, metrics in top_central[:5]
        ],
        "communities_detected": len(communities),
        "output_dir": output_dir,
        "files_generated": [
            "entity_database.xlsx",
            "relationship_graph.html",
            "cross_reference_matrix.xlsx",
            "timeline_dates.xlsx",
            "financial_mentions.xlsx",
            "entity_summary.txt",
            "entities.json",
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Entity & Relationship Mapper")
    parser.add_argument("--input", required=True, help="Document file or directory path")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--model", default="en_core_web_sm",
                        help="spaCy model name (default: en_core_web_sm)")
    parser.add_argument("--min-mentions", type=int, default=2,
                        help="Minimum mentions to include an entity (default: 2)")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(input_path):
        log(f"ERROR: Input path does not exist: {input_path}")
        sys.exit(1)

    # Load spaCy model
    if not HAS_SPACY:
        log("ERROR: spaCy is not installed. Run check_dependencies.py first.")
        result = {"status": "error", "error": "spaCy is not installed. Run check_dependencies.py first."}
        print(json.dumps(result))
        sys.exit(1)
    log(f"Loading spaCy model: {args.model}")
    try:
        nlp = spacy.load(args.model)
    except OSError:
        log(f"Model '{args.model}' not found. Attempting download...")
        import subprocess
        subprocess.run([sys.executable, "-m", "spacy", "download", args.model],
                       capture_output=True, text=True)
        try:
            nlp = spacy.load(args.model)
        except OSError:
            log(f"ERROR: Could not load spaCy model '{args.model}'")
            sys.exit(1)

    # Increase max length for large documents
    nlp.max_length = 2_000_000

    # Discover documents
    documents = []
    if os.path.isdir(input_path):
        documents = discover_documents(input_path)
        if not documents:
            log("ERROR: No supported documents found in directory.")
            sys.exit(1)
        log(f"Found {len(documents)} documents")
    elif os.path.isfile(input_path):
        documents = [input_path]
    else:
        log(f"ERROR: Path is neither file nor directory: {input_path}")
        sys.exit(1)

    # Extract text and entities from all documents
    all_entities = []
    for doc_path in documents:
        log(f"Processing: {os.path.basename(doc_path)}")
        text = extract_text_from_file(doc_path)
        if not text.strip():
            log(f"  WARNING: No text extracted from {os.path.basename(doc_path)}")
            continue
        log(f"  Extracted {len(text)} characters")
        log(f"  Running NER...")
        doc_entities = extract_entities_from_text(nlp, text, doc_path)
        log(f"  Found {len(doc_entities)} entity mentions")
        all_entities.extend(doc_entities)

    if not all_entities:
        log("WARNING: No entities found in any document.")
        # Still produce empty outputs
        result = write_outputs([], nx.Graph(), {}, [], documents, output_dir, args.min_mentions)
        print(json.dumps(result, indent=2, default=str))
        return

    log(f"\nTotal entity mentions: {len(all_entities)}")

    # Normalize entities
    log("Normalizing entities...")
    all_entities = normalize_entities(all_entities)

    # Build relationship graph
    log("Building relationship graph...")
    G = build_relationship_graph(all_entities)
    log(f"  Nodes: {len(G.nodes())}, Edges: {len(G.edges())}")

    # Compute centrality
    log("Computing centrality metrics...")
    centrality = compute_centrality(G)

    # Detect communities
    log("Detecting entity communities...")
    communities = detect_communities(G)
    log(f"  Communities found: {len(communities)}")

    # Write outputs
    log("\nWriting outputs...")
    result = write_outputs(
        all_entities, G, centrality, communities, documents, output_dir, args.min_mentions
    )

    log(f"\nAnalysis complete. Output: {output_dir}")

    # Print JSON to stdout for Claude
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
