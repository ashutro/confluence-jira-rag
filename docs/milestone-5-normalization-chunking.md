# Milestone 5: Data Normalization & Chunking

## Goal

Transform heterogeneous raw exports from Confluence (`data/raw/confluence/pages.json`) and Jira (`data/raw/jira/issues.json`) into a **Unified Document Model** and generate structured, context-aware **Semantic Text Chunks** (`data/processed/chunks.json`) ready for embedding and vector database indexing.

```text
  data/raw/confluence/pages.json         data/raw/jira/issues.json
                 \                                     /
                  v                                   v
          +---------------------------------------------------+
          |            Document Normalizer Layer              |
          |  - Converts Confluence & Jira to Unified Document |
          |  - Standardizes metadata, tags, URLs, timestamps  |
          +---------------------------------------------------+
                                    |
                                    v
          +---------------------------------------------------+
          |          Hierarchical Markdown Chunker            |
          |  - Header-based section splitting (#, ##, ###)    |
          |  - Breadcrumb / context injection per chunk       |
          |  - Configurable chunk size (800) & overlap (100)  |
          |  - Preserves tables & code blocks intact          |
          +---------------------------------------------------+
                                    |
                                    v
          +---------------------------------------------------+
          |    data/processed/chunks.json                     |
          |    data/processed/normalized_documents.json       |
          +---------------------------------------------------+
```

---

## 1. Unified Document Schema (`UnifiedDocument`)

Both Confluence documentation pages and Jira issue tickets are normalized into a single standardized representation:

```json
{
  "doc_id": "confluence:ENG-PAGE-01",
  "source_type": "confluence",
  "source_id": "ENG-PAGE-01",
  "title": "Architecture Overview & Service Topology",
  "url": "https://cloudscale-pay.atlassian.net/wiki/spaces/ENG/pages/1001/Architecture+Overview",
  "author": "alex.morgan@example.com",
  "created_at": "2026-08-15T14:30:00Z",
  "updated_at": "2026-08-15T14:30:00Z",
  "tags": ["architecture", "confluence", "eng", "kafka", "microservices", "redis", "topology"],
  "metadata": {
    "space_key": "ENG",
    "version": 4,
    "summary": "Core architectural blueprint of CloudScale Payments...",
    "labels": ["architecture", "microservices", "topology"]
  },
  "text_content": "# Architecture Overview & Service Topology\n\n- **Source**: Confluence Space `ENG`\n..."
}
```

---

## 2. Hierarchical Context-Aware Chunker (`MarkdownChunker`)

### Why Hierarchical Chunking?
Traditional naive text splitters slice text every $N$ characters. This cuts code blocks and tables in half and completely separates chunks from their parent section headers. When retrieved in isolation, a chunk saying *"Run kubectl rollout restart"* lacks the context of *which service* it applies to.

### The `MarkdownChunker` Solution:
1. **Section Hierarchy Tracking**: Recursively tracks Markdown headers (`#`, `##`, `###`) into a path stack (e.g. `["Architecture Overview", "2. Core Service Topology", "2.1 Services Breakdown"]`).
2. **Context Breadcrumb Injection**: Prepends document and section metadata directly into the chunk text:
   ```text
   [Document: Architecture Overview & Service Topology | Source: CONFLUENCE (ENG-PAGE-01)]
   [Section: Architecture Overview & Service Topology > 2. Core Service Topology > 2.1 Services Breakdown]

   - **Payment Ingestion Service (`pay-ingest`)**: High-performance Go service...
   ```
3. **Atomic Unit Preservation**: Keeps fenced code blocks (```` ```...``` ````) and tables (`|...|`) intact within chunks.
4. **Natural Boundary Splitting & Overlap**: For large sections, splits on paragraph and sentence boundaries with configurable `chunk_overlap`.

---

## 3. Chunk Output Schema (`Chunk`)

Stored in `data/processed/chunks.json`:

```json
{
  "chunk_id": "confluence:ENG-PAGE-01:chunk_1",
  "doc_id": "confluence:ENG-PAGE-01",
  "source_type": "confluence",
  "source_id": "ENG-PAGE-01",
  "title": "Architecture Overview & Service Topology",
  "section_title": "1. Executive Summary",
  "section_path": [
    "Architecture Overview & Service Topology",
    "1. Executive Summary"
  ],
  "chunk_index": 1,
  "text": "[Document: Architecture Overview & Service Topology | Source: CONFLUENCE (ENG-PAGE-01)]\n[Section: Architecture Overview & Service Topology > 1. Executive Summary]\n\nThe CloudScale Payments Platform is a distributed event-driven payment processing infrastructure...",
  "raw_text": "The CloudScale Payments Platform is a distributed event-driven payment processing infrastructure...",
  "char_count": 473,
  "word_count": 55,
  "metadata": {
    "space_key": "ENG",
    "version": 4,
    "tags": ["architecture", "confluence", "eng", "kafka"],
    "url": "https://cloudscale-pay.atlassian.net/wiki/spaces/ENG/pages/1001/Architecture+Overview",
    "author": "alex.morgan@example.com",
    "updated_at": "2026-08-15T14:30:00Z"
  }
}
```

---

## 4. Running Normalization & Chunking via CLI

```bash
# Process raw data into normalized documents and chunks:
rag-assistant normalize-chunk --mock

# Or specify custom chunk parameters:
rag-assistant normalize-chunk \
  --input-confluence data/raw/confluence/pages.json \
  --input-jira data/raw/jira/issues.json \
  --output-docs data/processed/normalized_documents.json \
  --output-chunks data/processed/chunks.json \
  --chunk-size 800 \
  --chunk-overlap 100
```

---

## 5. Python API Usage

```python
import json
from rag_assistant import (
    DocumentNormalizer,
    MarkdownChunker,
    load_sample_confluence_pages,
    load_sample_jira_issues,
)

# 1. Load raw records
conf_pages = load_sample_confluence_pages()
jira_issues = load_sample_jira_issues()

# 2. Normalize
normalizer = DocumentNormalizer()
docs = normalizer.normalize_all(conf_pages, jira_issues)
print(f"Normalized {len(docs)} documents")

# 3. Chunk
chunker = MarkdownChunker(chunk_size=800, chunk_overlap=100)
chunks = chunker.chunk_documents(docs)
print(f"Generated {len(chunks)} chunks")

# 4. Save to JSON
DocumentNormalizer.save_documents_to_json(docs, "data/processed/normalized_documents.json")
MarkdownChunker.save_chunks_to_json(chunks, "data/processed/chunks.json")
```

---

## 6. Verification & Automated Tests

Run the test suite:

```bash
pytest tests/test_normalizer_and_chunker.py -v
```

Tests cover:
- Confluence document normalization and metadata formatting.
- Jira issue normalization with comments and relationship links.
- Section hierarchy AST parsing and breadcrumb generation.
- Long section sentence/paragraph splitting with overlap.
- Code block and table preservation.
- End-to-end batch processing and JSON file serialization.
