---
description: Summarize documents (PDF, DOCX, TXT, MD) or entire directories of mixed documents into a structured report
argument-hint: "<file or folder path>"
---

# /summarize -- Document Summarizer

Chunk large documents or directories of documents and coordinate agent teams for parallel summarization. Produces a unified report with executive summary, document structure, and section-by-section summaries as a .docx file.

@$1

## Workflow

- **Validate** the input path (single file or directory) and check for supported formats (.pdf, .docx, .txt, .md)
- **Chunk** the document(s) into manageable sections using the `summarize` skill's chunking script
- **Summarize** chunks in parallel using agent teams for medium/large jobs (4+ chunks), or directly for small jobs
- **Produce** a professional .docx summary placed alongside the original file(s), with executive summary, document structure outline, and section-by-section summaries
- Refer to the `summarize` skill (SKILL.md) for detailed chunking parameters, agent coordination, and output format specifications
