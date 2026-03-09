---
description: Analyze evidence photos for EXIF metadata, GPS locations, timestamps, tampering indicators, and integrity hashes
argument-hint: "<directory of photos>"
---

# /analyze-photos -- Evidence Photo Analyzer

Analyze evidence photos for EXIF metadata, GPS coordinates, timestamps, camera identification, file hashes for integrity verification, and tampering indicators. Generates interactive maps, evidence catalogs, and timelines.

@$1

## Workflow

- **Validate** the input directory and identify supported image files (.jpg, .jpeg, .png, .tiff, .tif, .heic)
- **Analyze** all photos using the `analyze-photos` skill's Python script, extracting EXIF data, GPS coordinates, camera info, and computing integrity hashes
- **Present** findings: total photos analyzed, GPS locations found, date range, cameras identified, and any tampering flags
- **Generate** output files: evidence_catalog.xlsx, evidence_map.html (interactive map), evidence_timeline.html, metadata_report.json
- Refer to the `analyze-photos` skill (SKILL.md) for detailed analysis parameters and tampering detection methodology
