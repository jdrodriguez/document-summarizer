---
description: Analyze communication patterns from emails, texts, phone records, and chat logs with network and temporal analysis
argument-hint: "<communication data file or directory>"
---

# /analyze-communications -- Communication Pattern Analyzer

Analyze communication datasets to build relationship networks, detect communities, identify key players, and find temporal anomalies. Supports emails, texts, phone records, and chat logs.

@$1

## Workflow

- **Validate** the input path (file or directory) and check for supported formats (.csv, .xlsx)
- **Configure** optional key dates to analyze around (incidents, signings, terminations) and date range filters
- **Analyze** communications using the `analyze-communications` skill's Python script for network building, community detection, and temporal pattern analysis
- **Present** findings: total communications, unique participants, communities detected, key players by centrality metrics, and temporal patterns (spikes, drops, gaps around key dates)
- **Generate** output files: relationship_graph.html (interactive network), communication_timeline.html, communication_heatmap.html, key_players.xlsx, gap_analysis.xlsx
- Refer to the `analyze-communications` skill (SKILL.md) for centrality metrics, before/after key date analysis, and formal report generation
