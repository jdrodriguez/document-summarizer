---
description: Extract named entities from legal documents and map relationships using NLP network analysis
argument-hint: "<file or folder of documents>"
---

# /map-entities -- Entity & Relationship Mapper

Extract named entities (people, organizations, dates, monetary amounts, jurisdictions, legal references) from legal documents and build interactive relationship graphs showing how entities connect across documents.

@$1

## Workflow

- **Validate** the input path (file or directory) and check for supported formats (.pdf, .docx, .txt, .md)
- **Extract** entities using the `map-entities` skill's Python script with spaCy NLP for named entity recognition
- **Present** entity summary: total entities by type (PERSON, ORG, DATE, MONEY, GPE, LAW), most frequent entities, key people, key organizations
- **Highlight** relationships: most connected entities, entity clusters, and cross-document entity appearances
- **Generate** output files: entity_database.xlsx, relationship_graph.html (interactive network), cross_reference_matrix.xlsx, timeline_dates.xlsx, financial_mentions.xlsx
- Refer to the `map-entities` skill (SKILL.md) for NLP model options, minimum mention thresholds, and AI-powered relationship analysis
