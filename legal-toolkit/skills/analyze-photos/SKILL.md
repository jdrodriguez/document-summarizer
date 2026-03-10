---
name: analyze-photos
description: "Analyze evidence photos for EXIF metadata, GPS coordinates, timestamps, camera identification, file hashes for integrity verification, and tampering indicators. Generates interactive maps, evidence catalogs, and timelines. Use when: (1) a user has a directory of photos to analyze for legal evidence purposes, (2) a user says 'analyze these photos', 'extract photo metadata', 'check photo EXIF data', 'map photo locations', 'evidence catalog', or 'check for photo tampering', (3) any evidence documentation task involving photographs, (4) a user needs to create an evidence exhibit catalog with metadata and integrity hashes."
---

# Evidence Photo Analyzer

Analyze evidence photos for metadata, GPS locations, tampering indicators, and generate evidence catalogs with interactive maps.

**Supported formats**: `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`, `.heic`
**Input**: directory containing image files

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a directory path. If not, ask: "Please provide the path to the directory containing the evidence photos."
2. Verify the directory exists.
3. Check that the directory contains supported image files (.jpg, .jpeg, .png, .tiff, .tif, .heic).
4. Tell the user how many image files were found before proceeding.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).

### Step 3: Run Photo Analyzer

Determine the work directory:
```bash
WORK_DIR="{input_directory}/_evidence_analysis"
mkdir -p "$WORK_DIR"
```

```bash
python3 "$SKILL_DIR/scripts/analyze_photos.py" \
  --input-dir "<photo_directory>" \
  --output-dir "$WORK_DIR"
```

The script outputs JSON to stdout with the analysis results.

### Step 4: Present Results

1. Read `$WORK_DIR/analysis_summary.txt` and present the summary to the user.
2. Highlight key findings:
   - Total photos analyzed
   - Photos with GPS data (and locations found)
   - Date range of photos
   - Cameras/devices identified
   - Any tampering flags detected
3. Inform the user that the following files were generated:
   - `evidence_catalog.xlsx` - complete evidence catalog spreadsheet
   - `evidence_map.html` - interactive map with photo locations (if GPS data found)
   - `evidence_timeline.html` - chronological timeline of photos
   - `metadata_report.json` - full structured metadata per photo
   - `analysis_summary.txt` - human-readable summary

### Step 5: Offer Additional Actions

- **View map**: Point user to `$WORK_DIR/evidence_map.html` to open in browser
- **DOCX report**: Offer to create a formal evidence report (.docx) using the npm `docx` package
- **Specific photo details**: If user asks about a specific photo, look it up in `metadata_report.json`
- **Tampering review**: If tampering flags were found, provide detailed analysis


## Accuracy and QA (Required)

Read the full QA protocol at `$SKILL_DIR/../../QA_AND_ACCURACY.md` and follow it.

**Anti-hallucination rules** (include in ALL subagent prompts):
- Every factual claim must cite a source document — unsourced claims are prohibited
- Never fabricate legal citations — all case law → `[VERIFY]`, unknown authority → `[CASE LAW RESEARCH NEEDED]`
- Never assume facts not in source material — missing info → `[NEEDS INVESTIGATION]`
- Quote exactly when comparing documents — label analysis vs. facts distinctly

**QA review**: After completing all work but BEFORE presenting to the user, launch a QA agent (`subagent_type: "general-purpose"`) following the protocol in the file above. The QA agent reads all outputs and source materials, checks for hallucination and accuracy, and writes `qa_review.md`. Apply any fixes before presenting to the user.

## Error Handling

- **Path not found**: Ask user to verify the directory path
- **No supported images**: List supported formats and ask user to check the folder
- **EXIF extraction failure**: Report which files could not be read and continue with others
- **No GPS data**: Note that GPS data was not found but other metadata is still available
- **Geocoding failure**: Note that reverse geocoding failed (network issue) but GPS coordinates are still in the catalog
- **Script not found**: Verify the skill is installed (`ls $SKILL_DIR/scripts/`)
