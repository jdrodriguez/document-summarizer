---
name: map-entities
description: "Extract named entities from legal documents and map relationships between them using NLP. Processes PDF, DOCX, TXT, and MD files or directories of documents. Uses spaCy for named entity recognition to identify people, organizations, dates, monetary amounts, jurisdictions, and legal references, then builds interactive relationship graphs showing how entities connect across documents. Use when: (1) a user provides legal documents and asks to identify entities or map relationships, (2) a user says 'find all entities', 'map relationships', 'who is mentioned in these documents', 'extract names and dates', or 'analyze entity connections', (3) any legal analysis task requiring entity extraction, relationship mapping, or cross-document entity tracking, (4) a user needs to understand which people, organizations, and dates appear across a set of legal documents."
---

# Entity & Relationship Mapper

Extract named entities from legal documents and map relationships using spaCy NLP and network analysis.

**Supported formats**: `.pdf`, `.docx`, `.txt`, `.md`
**Input modes**: single file OR a directory containing multiple files
**NLP model**: `en_core_web_sm` (default). For better accuracy on complex legal text, upgrade to `en_core_web_trf` by running `python3 -m spacy download en_core_web_trf` and passing `--model en_core_web_trf`.

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path. If not, ask: "Please provide the path to the document or folder you want to analyze for entities."
2. Determine if the path is a file or directory:
   - **File**: verify it exists and has a supported extension (`.pdf`, `.docx`, `.txt`, `.md`)
   - **Directory**: verify it exists; the script will find all supported files inside it
3. If a directory, tell the user which files were found before proceeding.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).
- Note: On first run, the spaCy model `en_core_web_sm` (~12MB) will be downloaded automatically.

### Step 3: Run Entity Extraction

Determine the output directory:
- **Single file**: `OUTPUT_DIR="{parent_dir}/{filename_without_ext}_entities"`
- **Directory**: `OUTPUT_DIR="{directory_path}/_entity_analysis"`

```bash
mkdir -p "$OUTPUT_DIR"

python3 "$SKILL_DIR/scripts/map_entities.py" \
  --input "<file_or_directory_path>" \
  --output-dir "$OUTPUT_DIR" \
  [--model en_core_web_sm] \
  [--min-mentions 2]
```

The script prints JSON to stdout with entity extraction results. Read this output to present findings.

### Step 4: Present Entity Summary

Read `$OUTPUT_DIR/entity_summary.txt` and present key findings:

1. **Total entities found** with breakdown by type (PERSON, ORG, DATE, MONEY, GPE, LAW, etc.)
2. **Most frequent entities** - top 10 across all types
3. **Key people** - most mentioned PERSON entities
4. **Key organizations** - most mentioned ORG entities
5. **Date range** - earliest and latest DATE entities detected
6. **Financial mentions** - summary of MONEY entities

### Step 5: Highlight Key Relationships

From the relationship graph data:

1. **Most connected entities** - entities with the highest centrality scores
2. **Entity clusters** - groups of entities that frequently co-occur
3. **Cross-document entities** - entities that appear in multiple documents (if multi-file)

### Step 6: Direct User to Outputs

List all generated files with descriptions:

- `entity_database.xlsx` - Complete entity database with all mentions
- `relationship_graph.html` - Interactive network graph (open in browser)
- `cross_reference_matrix.xlsx` - Which entities appear in which documents
- `timeline_dates.xlsx` - All date entities with surrounding context
- `financial_mentions.xlsx` - All monetary amounts with context
- `entity_summary.txt` - Human-readable summary
- `entities.json` - Structured entity data for programmatic use

Tell the user: "Open `relationship_graph.html` in your browser to explore the interactive entity network. Nodes are colored by entity type."

### Step 7: Offer AI Analysis

Ask: "Would you like me to analyze these entity relationships and their potential legal significance?"

If yes:
1. Read `entities.json` for the full entity data
2. Provide analysis of:
   - Key parties and their apparent roles
   - Significant dates and their potential relevance
   - Financial amounts and patterns
   - Organizational relationships
   - Cross-document patterns suggesting connections between matters
3. Offer to generate a formal entity analysis report (.docx) using the `docx` skill

## Error Handling

- **Path not found**: Ask user to verify the path
- **Unsupported format**: Supported types are `.pdf`, `.docx`, `.txt`, `.md`
- **Empty directory**: No supported files found -- ask user to check the folder
- **Empty extraction**: File may be scanned/image-only; suggest OCR or a different format
- **spaCy model not found**: Run `python3 -m spacy download en_core_web_sm`
- **Low entity count**: Document may not contain recognizable entities; suggest reviewing raw text
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
