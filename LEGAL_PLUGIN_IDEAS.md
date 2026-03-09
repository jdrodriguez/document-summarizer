# Legal Productivity Plugin Suite — Product Plan

> **Date**: February 2026
> **Author**: Josue Rodriguez / Integrum
> **Status**: Research & Planning

---

## Table of Contents

1. [Market Opportunity](#market-opportunity)
2. [Plugin Ideas](#plugin-ideas)
3. [Monetization Strategy](#monetization-strategy)
4. [Distribution & Installation](#distribution--installation)
5. [Technical Architecture](#technical-architecture)
6. [Build Priority & Roadmap](#build-priority--roadmap)
7. [Package Reference](#package-reference)

---

## Market Opportunity

### The Numbers

| Metric | Value | Source |
|--------|-------|--------|
| Legal AI market (2026) | $1.89B, 17.3% CAGR | Precedence Research |
| Attorney utilization rate | 38% — only 3 of 8 hours are billable | Clio 2025 Legal Trends |
| Revenue lost to contract inefficiency | 9.2% of annual revenue | LexCheck |
| Revenue lost to billing problems | 16-30% | LawNext |
| Firms ramping AI spend next 12 months | 73% | National Law Review |
| Average attorney hourly rate | $349 | Clio |
| Solo practitioners spending under $3K/yr on software | 74% | Clio |
| Individual AI usage among solos | 72% | Clio |
| Firm-wide AI adoption among solos | 8% | Clio |

### The Gap

BigLaw has Harvey ($1,200/seat/year). Solo and small firms (the vast majority of the market) are priced out. 72% of solos use AI personally but only 8% have firm-wide tools. The opportunity is affordable, privacy-first, practice-area-specific plugins that run locally.

### Why Cowork Plugins Win

1. **No server infrastructure** — plugins run on the user's machine or Cowork's VM
2. **Privacy by default** — audio, documents, and data stay local (huge for attorney-client privilege)
3. **Composable** — plugins can call other plugins (`/docx`, `/xlsx`, `/pdf`)
4. **Low barrier** — drag-and-drop zip install in Cowork

---

## Plugin Ideas

### CATEGORY 1: Audio & Media Processing

#### Plugin 1: Legal Transcriber
**Slug**: `legal-transcriber`
**Command**: `/legal-transcriber:transcribe`

**What it does**: Transcribes audio recordings of client interviews, hearings, mediations, and meetings with speaker identification. Produces a timestamped transcript document and an AI-generated summary of key facts, decisions, and action items.

**Packages**:
- `faster-whisper` — local transcription, 4x faster than OpenAI Whisper, works offline (~200MB + 1.5GB model)
- `pyannote-audio` — speaker diarization (who said what) (~500MB + model)
- `pydub` + `ffmpeg` — audio format conversion and preprocessing

**Why it matters**:
- Client interviews are transcribed manually or not at all
- Otter.ai and similar cloud tools send audio to third-party servers — a privilege/confidentiality concern
- Paralegals spend hours creating meeting notes from recordings
- Immigration attorneys need multilingual transcription (Whisper supports 100+ languages)

**Key differentiator**: 100% local processing. No audio data leaves the machine. This is a massive selling point for any firm handling privileged communications.

**Outputs**:
- Timestamped transcript with speaker labels (.docx)
- Summary with key facts, decisions, action items (.docx)
- Raw transcript (.txt) for search/archival
- Audio metadata (duration, speakers detected, language)

**Target users**: All attorneys, paralegals, legal assistants

---

#### Plugin 2: Deposition Video Indexer
**Slug**: `legal-depo-indexer`
**Command**: `/legal-depo-indexer:index`

**What it does**: Takes deposition video/audio recordings, transcribes them with speaker identification, and creates a searchable index with timestamps linked to video timecodes. Flags key testimony (admissions, contradictions, emotional moments).

**Packages**:
- `faster-whisper` / `WhisperX` — transcription with word-level timestamps
- `pyannote-audio` — identify attorney vs. witness vs. other speakers
- `ffmpeg-python` — extract audio from video, split into segments
- `pydub` — audio preprocessing (noise reduction, normalization)

**Why it matters**:
- Deposition summaries take paralegals 4-8 hours per transcript
- 31% of litigation support professionals specifically want AI chronology/deposition tools
- Video depositions are increasingly common but harder to index than written transcripts
- Flagging key testimony saves attorneys hours of video review before trial

**Outputs**:
- Full transcript with speaker IDs and timestamps (.docx)
- Page-line style summary (matches court reporter format)
- Searchable topic index with video timecodes
- "Key moments" report flagging admissions, contradictions, and pivotal testimony
- Timeline of testimony (.xlsx)

**Target users**: Litigation paralegals, trial attorneys

---

### CATEGORY 2: Scanned Document & OCR Pipeline

#### Plugin 3: Legal OCR Engine
**Slug**: `legal-ocr`
**Command**: `/legal-ocr:process`

**What it does**: Processes scanned documents, faxes, old case files, and photographed evidence into searchable, extractable text. Pairs naturally with the document-summarizer plugin for a full pipeline: scan -> OCR -> summarize.

**Packages**:
- `PaddleOCR` — 94.5% accuracy on printed documents, 100+ languages (~738MB)
- `pytesseract` + Tesseract — lightweight fallback for simpler environments
- `Pillow` — image preprocessing (deskew, denoise, enhance contrast)
- `pdf2image` / `PyMuPDF` — convert PDF pages to images for OCR

**Why it matters**:
- Law firms have decades of scanned-only documents they can't search
- Incoming faxes (yes, courts still fax) arrive as image PDFs
- Medical records, police reports, and old contracts are often scanned
- OCR is a prerequisite for AI analysis — you can't summarize what you can't read

**Key differentiator**: Designed specifically for legal document types (court filings, medical records, faxes). Preprocessing pipeline optimized for common legal document quality issues (poor scans, fax artifacts, stamp marks).

**Outputs**:
- Searchable text file per document
- Searchable PDF (text layer added to original images)
- Extraction report with confidence scores
- Structured data extraction (dates, names, amounts found)

**Target users**: Paralegals, records managers, litigation support

**Composability**: Output feeds directly into `/document-summarizer:summarize` or `/legal-entities:map`

---

### CATEGORY 3: Email & Communication Analysis

#### Plugin 4: E-Discovery Email Processor
**Slug**: `legal-ediscovery`
**Command**: `/legal-ediscovery:process`

**What it does**: Ingests email archives (.pst, .mbox, .msg, .eml) from custodians, extracts metadata, reconstructs conversation threads, pulls attachments, and generates review-ready outputs including communication maps and privilege log drafts.

**Packages**:
- Python `email` + `mailbox` (stdlib) — parse .eml and .mbox (0 bytes)
- `extract-msg` — parse Outlook .msg files (~1MB)
- `libratom` — parse .pst archives (purpose-built for legal/archival)
- `networkx` — map communication networks (~5MB)
- `plotly` — interactive timeline and network visualizations (~25MB)
- `pandas` — tabular data processing (~30MB)

**Why it matters**:
- E-discovery processing tools (Relativity, Logikcull) cost $15K+/year
- First-pass email processing is 80% of the work in many cases
- Small/mid-size firms handle discovery manually or outsource at high cost
- 45% of firms use 5-10 different technologies with no unified workflow

**Outputs**:
- Communication metadata table (.xlsx) — sender, recipients, date, subject, attachments
- Thread reconstruction — grouped conversation chains
- Interactive communication network map (HTML) — who talked to whom, how often
- Interactive timeline of communications (HTML)
- Attachment extraction — all attachments pulled and cataloged
- Privilege flag report — emails involving attorney names/legal terms
- De-duplication report — identical and near-duplicate messages identified

**Target users**: Litigation paralegals, e-discovery teams, in-house counsel

---

#### Plugin 5: Communication Pattern Analyzer
**Slug**: `legal-comms-analyzer`
**Command**: `/legal-comms-analyzer:analyze`

**What it does**: Takes any communication dataset (email exports, text message CSVs, chat logs, phone records) and builds relationship graphs, identifies patterns, detects gaps, and visualizes communication flows over time.

**Packages**:
- `networkx` — graph analysis (centrality, communities, shortest paths)
- `plotly` — interactive network and timeline visualizations
- `pandas` — data processing and aggregation
- `community` (python-louvain) — community detection in networks

**Why it matters**:
- Communication patterns are powerful evidence in litigation
- Identifying who was in which "group" is critical for conspiracy, fraud, and employment cases
- Gaps in communication records can indicate spoliation
- Currently requires expensive forensic tools or manual analysis

**Outputs**:
- Interactive relationship graph (HTML) — node size = communication volume
- Communication timeline (HTML) — volume over time with anomaly detection
- Key player report — most connected nodes, bridges between groups
- Gap analysis — periods with missing communications
- Community detection — automatically identified communication clusters
- Export-ready data (.xlsx) for expert reports

**Target users**: Litigation attorneys, forensic consultants, employment lawyers

---

### CATEGORY 4: Financial & Billing Analysis

#### Plugin 6: Legal Billing Auditor
**Slug**: `legal-billing-auditor`
**Command**: `/legal-billing-auditor:audit`

**What it does**: Parses law firm billing data (LEDES files, Excel invoices, CSV time entries), analyzes for common billing problems, compares against outside counsel guidelines, and generates an audit report with flagged entries and savings calculations.

**Packages**:
- `pandas` — data analysis and aggregation
- `DuckDB` — fast SQL analytics on CSV/Excel without loading into memory (~30MB)
- `openpyxl` — read Excel files (~5MB)
- `XlsxWriter` — generate formatted Excel reports (~3MB)
- `plotly` — spend dashboards and trend visualizations

**Why it matters**:
- Firms lose 16-30% of revenue to billing inefficiency
- In-house counsel departments pay $500-2K/month for billing audit tools
- Block billing, vague descriptions, and rate violations are rampant
- Small firms doing outside counsel management have no affordable tools

**What it flags**:
- Block billing (multiple tasks in one entry without time breakdown)
- Vague descriptions ("Research", "Review documents", "Attention to matter")
- Excessive hours for task type
- Rate violations (above agreed caps)
- Duplicate entries (same date, same task, same timekeeper)
- Weekend/holiday billing anomalies
- Timekeeper staffing issues (senior partner doing paralegal work)

**Outputs**:
- Audit report (.docx) with findings, flags, and recommendations
- Flagged entries spreadsheet (.xlsx) with severity ratings
- Spend dashboard (HTML) — by matter, timekeeper, task code, time period
- Savings calculation — estimated recoverable amounts
- Trend analysis — spending patterns over time

**Target users**: In-house counsel, managing partners, legal operations

---

#### Plugin 7: Financial Forensics Toolkit
**Slug**: `legal-forensics`
**Command**: `/legal-forensics:analyze`

**What it does**: Ingests bank statements, transaction records, and financial spreadsheets. Normalizes data across different formats, traces money flows, identifies patterns, flags anomalies, and generates visual money flow diagrams.

**Packages**:
- `pandas` — normalize and analyze transaction data
- `networkx` — map fund transfers between entities as directed graphs
- `plotly` — money flow Sankey diagrams, timeline charts
- `openpyxl` — read various Excel formats
- `DuckDB` — fast analytical queries on large transaction sets

**Why it matters**:
- Financial forensics experts charge $300-500/hr
- Family law cases require tracing marital assets and hidden income
- Fraud litigation needs money flow visualization
- Business disputes require financial analysis of damages
- This gives attorneys a first-pass analysis before engaging expensive experts

**Outputs**:
- Transaction timeline (HTML) — visual chronology of all transactions
- Money flow diagram (HTML) — Sankey or network graph showing funds between entities
- Anomaly report (.docx) — unusual patterns, large transactions, round numbers, suspicious timing
- Entity summary (.xlsx) — all parties with total inflows/outflows
- Pattern analysis — recurring payments, escalating amounts, structuring indicators

**Target users**: Family law attorneys, fraud litigators, business dispute lawyers, forensic accountants

---

### CATEGORY 5: Evidence & Investigation Tools

#### Plugin 8: Evidence Photo Analyzer
**Slug**: `legal-evidence-photos`
**Command**: `/legal-evidence-photos:analyze`

**What it does**: Processes evidence photos from cases (accident scenes, property damage, injuries, crime scenes), extracts EXIF metadata (GPS, timestamps, camera info), plots locations on interactive maps, and generates an evidence catalog with chain-of-custody-ready metadata.

**Packages**:
- `Pillow` + `exifread` — EXIF/GPS metadata extraction (~5MB)
- `folium` — interactive map generation with markers (~1MB)
- `geopy` — reverse geocoding (coordinates to addresses) (~500KB)
- `XlsxWriter` — evidence catalog spreadsheet

**Why it matters**:
- Proving when and where a photo was taken is critical evidence
- Insurance defense, personal injury, and property cases rely heavily on photographic evidence
- EXIF data can corroborate or contradict witness testimony
- Investigators charge $150+/hr for metadata extraction
- Detecting modified EXIF data can reveal photo tampering

**Outputs**:
- Interactive evidence map (HTML) — photos plotted on map with clickable markers
- Evidence catalog (.xlsx) — filename, date, GPS, camera, dimensions, hash
- Metadata report (.docx) — per-photo analysis with tampering indicators
- Timeline view (HTML) — photos arranged chronologically
- Geographic clustering — photos grouped by location

**Target users**: Personal injury attorneys, insurance defense, criminal defense, property lawyers

---

#### Plugin 9: Entity & Relationship Mapper
**Slug**: `legal-entity-mapper`
**Command**: `/legal-entity-mapper:map`

**What it does**: Takes any set of documents (contracts, emails, filings, depositions) and automatically extracts all named entities (people, organizations, dates, money, locations) using NLP, then maps relationships between them into an interactive graph.

**Packages**:
- `spaCy` + `en_core_web_trf` — transformer-based NER (~490MB total)
- `networkx` — relationship graph construction and analysis
- `plotly` — interactive relationship visualization
- `pandas` — entity database management

**spaCy entity types directly useful for legal work**:

| Entity | Type | Legal Application |
|--------|------|-------------------|
| PERSON | Named persons | Parties, witnesses, judges |
| ORG | Organizations | Companies, courts, agencies |
| DATE | Dates | Filing dates, incident dates, deadlines |
| MONEY | Monetary values | Damages, settlements, fees |
| GPE | Geopolitical entities | Jurisdictions, venues |
| LAW | Named laws/acts | Statutes, regulations |

**Why it matters**:
- Complex litigation involves hundreds of documents with thousands of entity mentions
- Understanding who's connected to whom is the hardest part of large cases
- Corporate transaction due diligence requires mapping all parties across deal documents
- Currently requires expensive litigation support platforms or weeks of manual review

**Outputs**:
- Interactive entity relationship graph (HTML) — nodes = entities, edges = co-occurrence
- Entity database (.xlsx) — all entities with type, frequency, source documents
- Key player report — most connected entities, central figures
- Timeline (.xlsx) — all date entities with their context
- Financial summary — all monetary mentions with context
- Cross-reference matrix — which entities appear in which documents

**Target users**: Complex litigation teams, corporate lawyers, due diligence reviewers

---

### CATEGORY 6: Deadline & Calendar Management

#### Plugin 10: Court Deadline Calculator
**Slug**: `legal-deadlines`
**Command**: `/legal-deadlines:calculate`

**What it does**: Calculates litigation deadlines based on jurisdiction-specific court rules, accounting for holidays, weekends, service method adjustments, and cascading deadline chains. Generates calendar files for import into any calendar app.

**Packages**:
- `holidays` — government holidays for 249 country codes, state-level support (~2MB)
- `workalendar` — business day arithmetic with custom calendars (~3MB)
- `python-dateutil` — relative date calculations
- `icalendar` — generate .ics calendar files

**Implemented court rules**:
- FRCP Rule 6 (federal deadline counting)
- Service method adjustments (FRCP 6(d) — +3 days for mail, +1 for electronic in some jurisdictions)
- State-specific rules (configurable per jurisdiction)
- Cascading chains: motion -> opposition -> reply -> hearing

**Why it matters**:
- Missed deadlines are the #1 cause of legal malpractice claims
- Existing deadline calculators cost $100-300/month (LawToolBox, CompuLaw)
- Every litigation attorney and paralegal needs this daily
- Jurisdiction-specific rules make manual calculation error-prone
- This is a "must-have" gateway plugin that gets firms into the ecosystem

**Outputs**:
- Deadline schedule (.docx) with all calculated dates and rules applied
- Calendar file (.ics) for direct import into Outlook, Google Calendar, Apple Calendar
- Deadline spreadsheet (.xlsx) with rule citations and calculations shown
- Visual timeline (HTML) with all deadlines plotted

**Target users**: Every litigation attorney and paralegal. Period.

---

### CATEGORY 7: Document Intelligence (Beyond Creation)

#### Plugin 11: Contract Redline Generator
**Slug**: `legal-redline`
**Command**: `/legal-redline:compare`

**What it does**: Takes two versions of a contract (.docx), generates a proper tracked-changes redline document, and adds an AI-powered change analysis that categorizes and risk-rates each modification.

**Packages**:
- `Python-Redlines` — produces native Word tracked-changes markup
- `python-docx` — document manipulation
- `spaCy` — semantic understanding of changed clauses
- `difflib` (stdlib) — text-level diff for analysis

**Why it matters**:
- Word's built-in compare is decent but provides no intelligence about what the changes mean
- Associates spend hours reading redlines to identify material changes
- Contract negotiation requires quick turnaround on redline analysis
- Risk-rating changes saves partners from reviewing every modification

**Outputs**:
- Tracked-changes redline (.docx) — native Word format, ready for review
- Change analysis report (.docx) — categorized changes with risk ratings
- Change summary (.xlsx) — tabular view of all modifications
- Material changes alert — high-risk changes highlighted for partner review

**Target users**: Corporate/transactional attorneys, in-house counsel, paralegals

---

#### Plugin 12: Legal Document Comparison Suite
**Slug**: `legal-doc-compare`
**Command**: `/legal-doc-compare:analyze`

**What it does**: Compares any two legal documents (not just contracts — policies, regulations, court orders, leases, legislation) and generates a visual diff with semantic analysis of what changed and why it matters.

**Packages**:
- `difflib` (stdlib) — text-level diff
- `python-docx` — document parsing
- `spaCy` — semantic analysis
- `plotly` — visual change heatmap

**Outputs**:
- Side-by-side HTML comparison with color-coded changes
- Change log (.xlsx) — each modification with category and impact assessment
- Summary of material changes (.docx)
- Change heatmap — visual showing which sections changed most

**Target users**: Regulatory compliance, legislative tracking, policy management

---

### CATEGORY 8: Court & Public Records Research

#### Plugin 13: Public Records Researcher
**Slug**: `legal-records`
**Command**: `/legal-records:search`

**What it does**: Searches and processes public corporate filings from SEC EDGAR (free, no API key needed), extracts key data, and generates structured research reports.

**Packages**:
- `edgartools` — free SEC EDGAR API access, all filing types since 1993
- `pandas` — data extraction and analysis
- `plotly` — financial trend visualization

**Why it matters**:
- Associates spend hours on EDGAR pulling and reading filings
- Due diligence requires systematic extraction of officer names, risk factors, financials
- Securities litigation needs filing timeline analysis
- This is free data that's expensive to process manually

**Outputs**:
- Company research report (.docx) — officers, financials, risk factors, recent filings
- Filing timeline (.xlsx) — chronological list of all filings
- Financial trend charts (HTML) — revenue, income, key metrics over time
- Officer/director history — changes in leadership over time

**Target users**: Corporate lawyers, securities litigators, M&A teams

---

### CATEGORY 9: Workflow Automation

#### Plugin 14: Legal Intake Processor
**Slug**: `legal-intake`
**Command**: `/legal-intake:process`

**What it does**: Takes raw client intake data (forms, emails, notes, transcribed interviews) and structures it into a standardized client profile with conflict check data, matter type classification, and initial document checklists.

**Packages**:
- `spaCy` — extract entities from unstructured intake notes
- `python-docx` — generate intake reports
- `XlsxWriter` — conflict check spreadsheets

**Why it matters**:
- Client intake is manual, inconsistent, and error-prone
- Conflict checks are often incomplete because entity names aren't standardized
- Estate planning intake (the most underserved area — only 18% AI adoption) involves extracting complex family and asset structures
- Immigration intake requires matching clients to visa categories

**Outputs**:
- Structured client profile (.docx)
- Conflict check entity list (.xlsx) — all persons and organizations for cross-reference
- Document checklist (.docx) — what documents to request from the client
- Matter summary (.docx) — initial case assessment

**Target users**: Receptionists, legal assistants, intake coordinators

---

#### Plugin 15: Case Chronology Builder
**Slug**: `legal-chronology`
**Command**: `/legal-chronology:build`

**What it does**: Ingests a directory of case documents (pleadings, medical records, correspondence, reports) and automatically builds a master chronology by extracting dates and events from every document. Uses the document-summarizer's multi-agent pattern for large document sets.

**Packages**:
- `spaCy` — date and event extraction from text
- `pdfplumber` / `python-docx` — document text extraction (reuses document-summarizer's pipeline)
- `pandas` — chronology data management
- `XlsxWriter` — formatted chronology spreadsheet
- `plotly` — interactive visual timeline

**Why it matters**:
- Chronology building is the single most time-consuming paralegal task in litigation
- Medical malpractice and personal injury cases can have hundreds of dated events across thousands of pages
- Manual chronologies are slow and miss events buried in documents
- This directly reuses and extends the document-summarizer's architecture

**Outputs**:
- Master chronology (.xlsx) — date, event, source document, page reference
- Interactive timeline (HTML) — zoomable, filterable, color-coded by source
- Event summary (.docx) — narrative chronology for pleadings
- Gap analysis — periods with no documented events

**Target users**: Litigation paralegals, medical malpractice teams, personal injury firms

---

## Monetization Strategy

### The Reality of Cowork Plugins

Cowork plugins are unlimited-use once installed. We cannot charge per-document or per-use. This means our monetization must happen at the point of purchase/access, not at the point of use.

### Recommended Model: Annual License + Suite Bundle

#### Individual Plugin Pricing

| Tier | Price | What You Get |
|------|-------|--------------|
| **Lite (Free)** | $0 | Limited version (e.g., 5-min audio, 5-page OCR, basic features) |
| **Pro** | $99 - $249/year | Full unlimited plugin, 1 year of updates + support |
| **Lifetime** | 2.5x annual | Full plugin forever, 1 year of support (renewal optional) |

#### Suite Bundle Pricing

| Bundle | Contents | Price | Savings |
|--------|----------|-------|---------|
| Litigation Pack | Transcriber + Depo Indexer + E-Discovery + Chronology + Comms Analyzer | $499/year | ~40% off individual |
| Corporate Pack | Redline Generator + Doc Compare + Entity Mapper + Records Researcher | $349/year | ~35% off individual |
| Full Suite | All 15 plugins | $699/year | ~70% off individual |
| Lifetime Full Suite | All plugins, forever | $1,499 one-time | Best value for early adopters |

#### Why These Prices Work

- **Solo attorneys**: $699/year = $58/month. Well within the sub-$3K/year budget. ROI: saving even 2 hours/month at $349/hr = $8,376/year in recovered billable time
- **Small firms**: $699/year for the whole firm. Cheaper than one month of most legal AI tools
- **Mid-size firms**: $699/year per seat or negotiate volume licensing
- **Compared to alternatives**: Harvey = $1,200/seat/year. CoCounsel = $4,800/seat/year. LawToolBox = $1,200-3,600/year

### Revenue Projections (Conservative)

| Scenario | Users | Avg. Revenue/User | Annual Revenue |
|----------|-------|-------------------|----------------|
| Year 1 (launch) | 200 | $199 (mostly individual plugins) | $39,800 |
| Year 2 (growth) | 1,000 | $349 (mix of bundles) | $349,000 |
| Year 3 (scale) | 5,000 | $449 (more suite buyers) | $2,245,000 |

### Sales Channels

1. **Own website** (highest margin) — Gumroad, LemonSqueezy, or Stripe direct
2. **Legal tech directories** — Clio App Directory, ABA TechShow
3. **CLE presentations** — Continuing Legal Education events (huge credibility + lead gen)
4. **Bar association partnerships** — member discounts
5. **Legal consultants** — referral commissions for practice management advisors
6. **Content marketing** — blog posts, YouTube demos, legal tech podcasts

---

## Distribution & Installation

### The Friction Problem

The biggest barrier to plugin adoption is installation complexity. Law firms are not developer shops. Many attorneys and paralegals will struggle with:
- Downloading zip files and knowing where to put them
- Terminal/command-line operations
- Python/Node.js dependency management
- Troubleshooting errors

### Current Installation Methods

| Method | For | Friction Level |
|--------|-----|----------------|
| Drag zip into Cowork | Cowork users | LOW — but requires finding and downloading the zip |
| `/install-plugin <github-url>` | Claude Code CLI | MEDIUM — requires CLI comfort |
| `install.sh` | CLI fallback | HIGH — requires terminal knowledge |

### Proposed: Frictionless Installation System

#### For Cowork (Primary Target — Lowest Friction)

**Flow**: Purchase on website -> Receive email with download link -> Drag zip into Cowork -> Done

The Cowork drag-and-drop zip install is already the lowest friction path. We need to optimize the surrounding experience:

1. **Purchase page** on our website (LemonSqueezy/Gumroad)
2. **Instant download** after purchase — the zip file
3. **Clear visual instructions** — 3-step graphic: "1. Download 2. Open Cowork 3. Drag the file in"
4. **Auto-dependency handling** — Cowork's VM has Python/Node pre-installed. Our `check_dependencies.py` pattern already auto-installs packages on first run. Extend this to all plugins
5. **Verification prompt** — After install, plugin tells user: "Legal Transcriber installed. Try: /legal-transcriber:transcribe"

**Bundle delivery**: For suite purchases, deliver a single zip containing all plugins. The marketplace.json format already supports multiple plugins:

```json
{
  "name": "legal-productivity-suite",
  "plugins": [
    { "name": "legal-transcriber", "source": "./legal-transcriber" },
    { "name": "legal-ocr", "source": "./legal-ocr" },
    { "name": "legal-deadlines", "source": "./legal-deadlines" }
  ]
}
```

One zip, one drag, all plugins installed at once.

#### For Claude Code CLI (Secondary Target)

**Flow**: Purchase -> Receive GitHub repo access or download link -> One command install

Option A — Private GitHub repo (best for updates):
```
/install-plugin https://github.com/integrum-legal/legal-suite
```
Requires: GitHub access token. More friction but enables automatic updates.

Option B — Direct zip URL:
```
/install-plugin https://plugins.integrum.legal/download/legal-suite-v1.0.zip
```
Requires: Our server hosting the zip. Simpler for users.

Option C — Local install from downloaded zip:
```bash
unzip legal-suite.zip
claude --plugin-dir ./legal-suite/legal-transcriber
```
Most friction, but works offline.

#### Dependency Auto-Install Pattern (Already Proven)

Our document-summarizer already handles this well. Every plugin should follow the same pattern:

```
SKILL.md Step 2: Check Dependencies
  -> check_dependencies.py
     -> Tries to import each package
     -> If missing, runs pip install / npm install
     -> Exit 0 (all good) / Exit 1 (installed) / Exit 2 (failed)
```

**For heavy dependencies** (Whisper models, spaCy models, PaddleOCR):
- First run downloads models with progress feedback
- Subsequent runs are instant
- SKILL.md tells Claude to inform the user: "First run will download the transcription model (~1.5GB). This only happens once."

#### License Key System (If Needed Later)

If we want to enforce paid access:

1. Plugin zip is freely downloadable (removes distribution friction)
2. On first run, `check_license.py` prompts for a license key
3. Key is stored in `~/.claude/plugins/legal-suite/.license`
4. Validation: simple offline check (signed key contains expiry date + plugin list)
5. No server call needed — keeps it simple and offline-compatible

This is a "Phase 2" feature. For launch, sell the zip directly and trust the payment gate.

### Installation Friction Reduction Checklist

- [ ] Single zip for suite (one drag installs everything)
- [ ] Auto-dependency installation with clear progress messages
- [ ] First-run model download with size warnings
- [ ] Post-install verification message
- [ ] Troubleshooting guide built into SKILL.md error handling
- [ ] Video tutorial on website (30 seconds: download, drag, done)
- [ ] Email onboarding sequence after purchase

---

## Technical Architecture

### Plugin Structure Pattern (Standardized)

Every plugin follows this structure:

```
legal-{name}/
  .claude-plugin/
    plugin.json               # Manifest (name, version, description)
  skills/
    {command}/
      SKILL.md                # Entry point with YAML frontmatter
      scripts/
        check_dependencies.py # Auto-install dependencies
        {main_script}.py      # Core processing logic
        {helper}.py           # Additional helpers
  install.sh                  # Fallback manual install
```

### Suite Structure (Multi-Plugin Zip)

```
legal-productivity-suite/
  .claude-plugin/
    marketplace.json          # Lists all contained plugins
  legal-transcriber/
    .claude-plugin/plugin.json
    skills/transcribe/...
  legal-ocr/
    .claude-plugin/plugin.json
    skills/process/...
  legal-deadlines/
    .claude-plugin/plugin.json
    skills/calculate/...
  [... more plugins ...]
```

### Composability Pattern

Plugins can chain together by referencing each other's skills:

```
Audio file -> /legal-transcriber:transcribe -> transcript.docx
transcript.docx -> /document-summarizer:summarize -> summary.docx
transcript.docx -> /legal-entities:map -> entity_graph.html
```

Or within a single SKILL.md:
```markdown
### Step 5: (Optional) Summarize the transcript
If the user requested a summary, invoke `/document-summarizer:summarize` on the transcript output.
```

### Shared Utilities Pattern

Common functionality should be shared across plugins:

```
legal-shared/
  scripts/
    check_dependencies.py     # Standardized dep checker
    file_utils.py             # Common file handling
    output_utils.py           # Standard output formatting
```

Each plugin can copy or symlink shared utilities to avoid cross-plugin dependencies.

---

## Build Priority & Roadmap

### Phase 1: Foundation (Month 1-2)
**Goal**: Ship 3 plugins + the suite infrastructure

| # | Plugin | Effort | Why First |
|---|--------|--------|-----------|
| 1 | **Legal Transcriber** | 2 weeks | Highest wow factor. Clear differentiation (local/private). Showcases package-powered capability |
| 2 | **Court Deadline Calculator** | 1 week | Every lawyer needs it. Lightweight. Gateway drug into the ecosystem |
| 3 | **Legal OCR Engine** | 1 week | Natural companion to document-summarizer. Unlocks scanned documents |

Also in Phase 1:
- Suite zip packaging system
- Website with purchase flow (LemonSqueezy)
- 30-second installation video
- Email onboarding sequence

### Phase 2: Litigation Pack (Month 3-4)
**Goal**: Complete the litigation bundle

| # | Plugin | Effort |
|---|--------|--------|
| 4 | **Case Chronology Builder** | 2 weeks |
| 5 | **Deposition Video Indexer** | 2 weeks |
| 6 | **E-Discovery Email Processor** | 2 weeks |

### Phase 3: Analysis & Intelligence (Month 5-6)
**Goal**: Add the analysis layer

| # | Plugin | Effort |
|---|--------|--------|
| 7 | **Entity & Relationship Mapper** | 2 weeks |
| 8 | **Communication Pattern Analyzer** | 1 week |
| 9 | **Contract Redline Generator** | 1 week |

### Phase 4: Financial & Research (Month 7-8)
**Goal**: Complete the full suite

| # | Plugin | Effort |
|---|--------|--------|
| 10 | **Legal Billing Auditor** | 2 weeks |
| 11 | **Financial Forensics Toolkit** | 2 weeks |
| 12 | **Evidence Photo Analyzer** | 1 week |
| 13 | **Document Comparison Suite** | 1 week |
| 14 | **Public Records Researcher** | 1 week |
| 15 | **Legal Intake Processor** | 1 week |

### Phase 5: Polish & Scale (Month 9+)
- Lite/free versions of each plugin
- License key system (if needed)
- Clio App Directory integration
- CLE presentation circuit
- Referral program for legal consultants

---

## Package Reference

### Quick Reference: Key Packages by Plugin

| Plugin | Primary Packages | Install Size | Offline? |
|--------|-----------------|--------------|----------|
| Legal Transcriber | faster-whisper, pyannote-audio, pydub | ~700MB + 1.5GB model | Yes |
| Depo Video Indexer | WhisperX, ffmpeg-python, pyannote | ~700MB + model | Yes |
| Legal OCR Engine | PaddleOCR, Pillow | ~738MB | Yes |
| E-Discovery Email | email (stdlib), extract-msg, libratom, networkx, plotly | ~60MB | Yes |
| Comms Analyzer | networkx, plotly, pandas | ~60MB | Yes |
| Billing Auditor | pandas, DuckDB, openpyxl, XlsxWriter, plotly | ~90MB | Yes |
| Financial Forensics | pandas, networkx, plotly, openpyxl | ~60MB | Yes |
| Evidence Photos | Pillow, exifread, folium, geopy | ~7MB | Partially |
| Entity Mapper | spaCy + en_core_web_trf, networkx, plotly | ~490MB | Yes |
| Court Deadlines | holidays, workalendar, icalendar | ~5MB | Yes |
| Contract Redline | Python-Redlines, spaCy, difflib | ~490MB | Yes |
| Doc Compare | difflib (stdlib), spaCy, plotly | ~490MB | Yes |
| Records Researcher | edgartools, pandas, plotly | ~55MB | Online |
| Legal Intake | spaCy, python-docx, XlsxWriter | ~490MB | Yes |
| Case Chronology | spaCy, pdfplumber, pandas, plotly, XlsxWriter | ~520MB | Yes |

### Dependency Overlap (Efficiency Gains)

Many plugins share the same packages. If a user installs the full suite, total unique dependencies are much smaller than the sum of individual plugins:

| Package | Used By (# of plugins) |
|---------|----------------------|
| pandas | 8 |
| plotly | 9 |
| spaCy | 6 |
| networkx | 4 |
| XlsxWriter | 5 |
| openpyxl | 3 |
| Pillow | 3 |
| pydub/ffmpeg | 2 |
| faster-whisper | 2 |

---

## Open Questions

1. **Cowork VM limitations**: What's the disk space and RAM available? Whisper large model needs 1.5GB disk + 4.7GB VRAM (or ~3GB RAM on CPU). Need to test on actual Cowork environment.

2. **Model download on Cowork**: Cowork VMs may have session limits. If the VM resets, models would need to re-download. Need to test persistence.

3. **Bundle zip size**: A full suite zip with all Python scripts could be 5-10MB (code only, no models). Models download on first run. Is this acceptable for drag-and-drop?

4. **Pricing validation**: Should we survey potential customers before setting prices? Consider a pre-launch landing page to gauge interest.

5. **Legal compliance**: Do we need disclaimers about AI-generated legal work? Probably yes — "This tool assists legal professionals. All output should be reviewed by a licensed attorney."

6. **Trademark**: Should we trademark the suite name? Need a good brand name beyond "Legal Productivity Suite."

7. **Competition monitoring**: Watch for Anthropic launching their own legal plugins or partnering with Harvey/Thomson Reuters for Cowork integrations.

---

## Next Steps

1. Build the Legal Transcriber plugin (highest impact, clearest demo)
2. Build the Court Deadline Calculator (lightweight, universal need)
3. Set up the suite packaging infrastructure (multi-plugin zip)
4. Create the sales website with LemonSqueezy/Gumroad
5. Record the 30-second installation video
6. Beta test with 5-10 attorneys for feedback and testimonials
