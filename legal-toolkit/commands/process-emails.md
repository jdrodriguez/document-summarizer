---
description: Process email archives for e-discovery with threading, deduplication, privilege detection, and network visualization
argument-hint: "<email file or directory>"
---

# /process-emails -- E-Discovery Email Processor

Parse email archives, reconstruct threads, detect duplicates, flag potentially privileged communications, and visualize communication networks for legal review.

@$1

## Workflow

- **Validate** the input path and check for supported formats (.eml, .msg, .mbox, or directories of email files)
- **Configure** processing options: attorney names for privilege detection, privileged domains, and attachment extraction preferences
- **Process** emails using the `process-emails` skill's Python script for parsing, threading, deduplication, and privilege flagging
- **Present** findings: emails processed, threads reconstructed, duplicates found, privilege flags (with warning that these require human review)
- **Generate** output files: email_metadata.xlsx, threads.json, communication_network.html, communication_timeline.html, privilege_flags.xlsx, duplicates.xlsx
- Refer to the `process-emails` skill (SKILL.md) for privilege configuration, attachment handling, and formal e-discovery report options
