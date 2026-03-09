---
name: analyze-communications
description: "Analyze communication patterns from emails, texts, phone records, and chat logs. Builds relationship networks, detects communities, identifies key players, and finds communication gaps or anomalies. Use when: (1) a user provides communication data and asks for analysis, (2) a user says 'analyze these emails', 'map the communication network', 'who are the key players', 'find communication patterns', or 'analyze these phone records', (3) any task involving email analysis, communication pattern mapping, relationship network building, or discovery review, (4) a user wants to understand who communicated with whom, identify clusters or communities, or find gaps in communications around key dates."
---

# Communication Pattern Analyzer

Analyze communication datasets to build relationship networks, detect communities, identify key players, and find temporal anomalies.

**Supported formats**: CSV (`.csv`), Excel (`.xlsx`), common exports (Google Takeout, iMessage, WhatsApp, CDR)
**Input modes**: single file OR a directory containing multiple communication files

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path to communication data. If not, ask: "Please provide the path to the communication data file(s) you want analyzed."
2. Determine if the path is a file or directory:
   - **File**: verify it exists and has a supported extension (`.csv`, `.xlsx`)
   - **Directory**: verify it exists; the script will find all supported files inside it
3. If a directory, tell the user which files were found before proceeding.
4. Ask if they have key dates to analyze around (e.g., dates of incidents, contract signings, terminations).
5. Ask if they want to filter to a specific date range.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).

### Step 3: Run Communication Analysis

Determine the output directory:
- **Single file**: `OUTPUT_DIR="{parent_dir}/{filename_without_ext}_comms_analysis"`
- **Directory**: `OUTPUT_DIR="{directory_path}/_comms_analysis"`

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/analyze_communications.py" \
  --input "<file_or_directory_path>" \
  --output-dir "$OUTPUT_DIR" \
  [--date-range "2025-01-01:2025-12-31"] \
  [--key-dates "2025-06-15,2025-09-01"]
```

The script prints a JSON summary to stdout. Capture and parse it.

### Step 4: Present Network Analysis

Read the output files and present findings to the user:

1. **Start with the overview**: Read `$OUTPUT_DIR/analysis_summary.txt` and present:
   - Total communications analyzed
   - Date range covered
   - Number of unique participants
   - Number of communities/clusters detected
   - Communication gaps identified

2. **Key players**: Present the top participants by centrality metrics:
   - Most connected (degree centrality)
   - Most influential bridges (betweenness centrality)
   - PageRank leaders

3. **Communities**: Describe each detected cluster -- who is in it and how active it is.

4. **Temporal patterns**: Highlight any spikes, drops, or gaps in communication, especially around key dates if provided.

### Step 5: Direct to Interactive Visualizations

Tell the user about the generated files:
- `relationship_graph.html` - Interactive network graph with communities color-coded (open in browser)
- `communication_timeline.html` - Volume over time with anomaly markers
- `communication_heatmap.html` - Who-to-whom communication matrix
- `key_players.xlsx` - Ranked list of participants by centrality metrics
- `gap_analysis.xlsx` - Periods with missing or reduced communications
- `network_analysis.json` - Structured data for further processing

### Step 6: Before/After Analysis (if key dates provided)

If the user provided key dates, present a before/after comparison:
- Communication volume before vs. after each key date
- New relationships that appeared or disappeared
- Changes in key player rankings

### Step 7: Offer Formal Report

Ask: "Would you like me to generate a formal communication analysis report as a Word document (.docx)?"

If yes, use the `docx` skill (invoke with `/docx`) to produce a professional report containing:
1. **Title page**: "Communication Pattern Analysis Report", date, case information
2. **Executive Summary**: Key findings and notable patterns
3. **Methodology**: Analysis techniques and data sources
4. **Network Overview**: Participants, communities, key metrics
5. **Key Players**: Profiles of most central participants
6. **Community Analysis**: Cluster descriptions and inter-group communication
7. **Temporal Analysis**: Volume trends, gaps, and anomalies
8. **Key Date Analysis**: Before/after comparisons (if applicable)
9. **Appendix**: Full participant list and data sources

## Error Handling

- **Path not found**: Ask user to verify the path
- **Unsupported format**: Supported types are `.csv`, `.xlsx`
- **Empty directory**: No supported files found -- ask user to check the folder
- **Parse errors**: Some files may have non-standard column formats; report which files failed and continue with others
- **Too few communications**: Need at least 2 participants for network analysis
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
