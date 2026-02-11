---
name: summarize
description: "Process and summarize large documents (PDF, DOCX, TXT, Markdown) or entire directories of mixed documents. Automatically chunks documents into manageable sections, coordinates a team of agents for parallel summarization, and produces a unified report with executive summary, document structure outline, and section-by-section summaries. Use when: (1) a user provides a file or folder and asks for a summary, overview, analysis, or key takeaways, (2) a user says 'summarize this document', 'summarize these documents', 'give me an executive summary', 'what does this document say', or 'analyze this report', (3) any document processing task where files are too large to read in a single pass, (4) a user points to a directory containing multiple PDFs, DOCX, TXT, or MD files to summarize together."
---

# Document Summarizer

Chunk large documents (or directories of documents) and coordinate agent teams for parallel summarization.

**Supported formats**: `.pdf`, `.docx`, `.txt`, `.md`
**Input modes**: single file OR a directory containing multiple files

## Skill Directory

Scripts are in the `scripts/` subdirectory of this skill's directory.
Resolve `SKILL_DIR` as the absolute path of this SKILL.md file's parent directory. Use `SKILL_DIR` in all script paths below.

## Process

### Step 1: Validate Input

1. Confirm the user provided a path. If not, ask: "Please provide the path to the file or folder you want summarized."
2. Determine if the path is a file or directory:
   - **File**: verify it exists and has a supported extension (`.pdf`, `.docx`, `.txt`, `.md`)
   - **Directory**: verify it exists; the script will find all supported files inside it
3. If a directory, tell the user which files were found before proceeding.

### Step 2: Check Dependencies

```bash
python3 "$SKILL_DIR/scripts/check_dependencies.py"
```

- Exit 0: all good. Exit 1: packages were installed (proceed). Exit 2: failed (report to user).

### Step 3: Chunk the Document(s)

Determine the work directory based on input type:
- **Single file**: `WORK_DIR="{parent_dir}/{filename_without_ext}_summary_work"`
- **Directory**: `WORK_DIR="{directory_path}/_summary_work"`

This places chunks alongside the source so users can review them.

```bash
mkdir -p "$WORK_DIR"

python3 "$SKILL_DIR/scripts/chunk_document.py" \
  "<file_or_directory_path>" \
  "$WORK_DIR" \
  --max-tokens 4000 \
  --overlap 200
```

The script accepts either a single file or a directory. Read `$WORK_DIR/metadata.json` to determine the mode.

**metadata.json `mode` field**:
- `"single_file"`: one document was processed. Chunks are in `chunks` array.
- `"multi_file"`: a directory was processed. Each file is in the `files` array, each with its own `chunks` sub-array.

### Step 4: Determine Strategy

Read metadata.json. Count total chunks:
- **Single file**: `num_chunks` field
- **Multi file**: `total_chunks` field

**Small job (1-3 total chunks):** Summarize directly — no team needed.
- Read each chunk file sequentially
- Skip to Step 6 output format

**Medium/large job (4+ total chunks):** Create an agent team.
- Calculate agent count: `min(8, max(2, total_chunks // 2))`
- Proceed to Step 5

### Step 5: Agent Team Coordination

#### 5a. Create the Team

```
TeamCreate: team_name="doc-summary", description="Summarizing <name>"
```

#### 5b. Spawn Summarizer Agents

Divide chunks evenly across agents. Keep contiguous chunks together. For multi-file mode, keep chunks from the same file together when possible.

For each agent, spawn via Task tool with `subagent_type: "general-purpose"` and this prompt:

```
You are summarizing sections of a large document.

Read these chunk files and write a summary for each:
{list of absolute chunk file paths, e.g. $WORK_DIR/chunks/chunk_001.txt}

For context, here is the chunk metadata:
{chunk entries from metadata.json for assigned chunks}

Write your output to: {WORK_DIR}/summaries/section_{agent_number}.md

Use this format for your output file:

## {heading from chunk metadata}
**Source file**: {filename, if multi-file mode}
**Pages**: {start_page}-{end_page} (omit if pages are 0)

### Summary
[2-4 paragraphs summarizing the content]

### Key Points
- [Important point 1]
- [Important point 2]

### Notable Details
- [Specific data, statistics, quotes, or references worth preserving]

---

Repeat the above for each chunk you are assigned.
After writing the file, confirm completion.
```

Launch all agents in parallel (multiple Task tool calls in one message).

#### 5c. Collect Results

After all agents complete:
1. Read all summary files: `{WORK_DIR}/summaries/section_*.md`
2. Read `metadata.json` for structure
3. Proceed to Step 6

#### 5d. Clean Up

After producing the final output:
- Send shutdown_request to all agents
- TeamDelete to clean up

### Step 6: Produce Final Output

The final deliverables are a `.docx` and a `.pdf` file placed **in the same folder as the original document(s)**.

**Output file naming**:
- **Single file**: `{original_filename_without_ext}_summary.docx` and `_summary.pdf`
- **Directory**: `Summary_{dirname}.docx` and `Summary_{dirname}.pdf`

**How to generate the files**:
Use the `docx` skill (invoke with `/docx`) for the .docx, and `pdfkit` for the .pdf. Both should be generated from a single Node.js script. The docx skill reads `docx-js.md` for the API reference. For PDF, use `pdfkit` with `bufferPages: true` and add page numbers after all content is written.

**Document structure requirements** (for the .docx):
- Title page with document name, date, page/token counts
- Table of Contents using HeadingLevel styles
- Header with document title, footer with page numbers
- Professional styling: Arial font, proper heading hierarchy, consistent spacing
- Tables for structured data (file listings, effective dates, etc.)
- Proper bullet lists (using numbering config, not unicode)
- Page breaks between major sections

Also write a plain-text copy to `{WORK_DIR}/final_summary.md` for reference.

#### Content template for SINGLE FILE mode:

The .docx should contain:
1. **Title**: "Document Summary: {filename}"
2. **Metadata block**: Source path, pages, token count, sections processed
3. **Executive Summary** (Heading 1): 2-3 paragraphs covering what the document is about, main conclusions, intended audience, and key takeaways
4. **Document Structure** (Heading 1): Numbered outline with section headings and page ranges
5. **Section Summaries** (Heading 1): For each section:
   - Section heading (Heading 2) with page range
   - Summary paragraphs
   - Key Points as bullet list
   - Notable Details as bullet list
6. **Key Findings and Takeaways** (Heading 1): Numbered list of the most important findings
7. **Notable Data and References** (Heading 1): Key statistics, dates, figures, citations, named entities

#### Content template for MULTI-FILE mode:

The .docx should contain:
1. **Title**: "Document Collection Summary"
2. **Metadata block**: Source directory, file count, total tokens, total chunks
3. **Files Processed** table: columns for #, Filename, Type, Pages, Tokens, Chunks
4. **Executive Summary** (Heading 1): 2-3 paragraphs synthesizing themes across ALL documents
5. **Per-Document Summaries** (Heading 1): For each document:
   - Document name (Heading 2) with type, pages, tokens
   - Structure outline
   - Summary paragraphs
   - Key Points as bullet list
6. **Cross-Document Findings** (Heading 1): Themes and patterns that span multiple documents
7. **Notable Data and References** (Heading 1): Key statistics, dates, figures across all documents

## Error Handling

- **Path not found**: Ask user to verify the path
- **Unsupported format**: Supported types are `.pdf`, `.docx`, `.txt`, `.md`
- **Empty directory**: No supported files found — ask user to check the folder
- **Empty extraction**: File may be scanned/image-only; suggest OCR
- **Agent failure**: Read the unprocessed chunks directly and summarize yourself
- **Script not found**: Verify the skill is installed (`ls ~/.claude/skills/document-summarizer/scripts/`)
