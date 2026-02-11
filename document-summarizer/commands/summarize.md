---
description: Process and summarize large documents (PDF, DOCX, TXT, Markdown) or entire directories of mixed documents
argument-hint: "<path to file or directory>"
---

# /summarize

Summarize documents into professional reports with executive summaries, section-by-section analysis, and key findings.

## Usage

```
/summarize /path/to/document.pdf
/summarize /path/to/folder/
```

Provide the path to a file (`.pdf`, `.docx`, `.txt`, `.md`) or a directory containing multiple files.

---

This command uses the `summarize` skill. Follow the full workflow defined in the skill at `skills/summarize/SKILL.md` within this plugin's directory. Resolve `SKILL_DIR` as the absolute path to the `skills/summarize/` directory of this plugin, then execute all steps from that SKILL.md file.

The user's input is: $ARGUMENTS
