# Confluence + Jira RAG Assistant

Enterprise AI knowledge assistant that answers questions from Confluence documentation pages and Jira issues using Qdrant Vector Database, LLM synthesis, hallucination-preventing guardrails, and an interactive Web UI.

```text
+-----------------------+     +-----------------------+
|  Confluence Cloud API |     |    Jira Cloud API     |
+-----------------------+     +-----------------------+
            |                             |
            v                             v
+-----------------------------------------------------+
| Connectors (ConfluenceConnector & JiraConnector)    |
+-----------------------------------------------------+
            |
            v
+-----------------------------------------------------+
| Document Normalizer & Hierarchical Markdown Chunker |
+-----------------------------------------------------+
            |
            v
+-----------------------------------------------------+
| Dense Embeddings + Qdrant Vector Database           |
+-----------------------------------------------------+
            |
            v
+-----------------------------------------------------+
| RAG Retrieval Engine + Hybrid Re-Ranking            |
+-----------------------------------------------------+
            |
            v
+-----------------------------------------------------+
| Guardrails & Citation Verifier                      |
+-----------------------------------------------------+
            |
            v
+-----------------------------------------------------+
| Grounded Answer Synthesis (OpenAI/Anthropic/Gemini) |
+-----------------------------------------------------+
            |
            v
+-----------------------------------------------------+
| Interactive Web UI & CLI (FastAPI + Modern Web App) |
+-----------------------------------------------------+
```

## Local Setup

Create and activate virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Run test suite (61/61 tests passing):

```bash
pytest tests/ -v
```

---

## Quickstart Guide

### 1. Ingest Data (Milestones 3 & 4)
```bash
rag-assistant fetch-confluence --mock --output data/raw/confluence/pages.json
rag-assistant fetch-jira --mock --output data/raw/jira/issues.json
```

### 2. Normalize and Chunk (Milestone 5)
```bash
rag-assistant normalize-chunk --mock
```

### 3. Index Vector Database (Milestone 6)
```bash
rag-assistant index-qdrant --mock --db-path data/qdrant_db --recreate
```

### 4. Interactive Web Interface (Milestone 10)
```bash
rag-assistant serve --host 127.0.0.1 --port 8000 --mock
```
Open **`http://localhost:8000`** in your browser.

### 5. CLI Interactions (Milestones 8 & 9)
```bash
# Ask a question:
rag-assistant ask "What is the runbook for webhook 504 gateway timeouts?" --mock

# Interactive terminal chat:
rag-assistant chat --mock

# Guardrail & hallucination defense tests:
rag-assistant test-guardrails --mock
```

---

## Milestone Roadmap & Status

- [x] **Milestone 1**: Local Project Setup & Repository Initialization
- [x] **Milestone 2**: Atlassian Setup & Seed Dataset
- [x] **Milestone 3**: Confluence Connector (XHTML $\to$ Markdown)
- [x] **Milestone 4**: Jira Connector (ADF AST $\to$ Markdown)
- [x] **Milestone 5**: Data Normalization & Hierarchical Markdown Chunking
- [x] **Milestone 6**: Vector Database (Qdrant) & Semantic Search
- [x] **Milestone 7**: Context-Grounded Retrieval Engine & Benchmark Evaluation
- [x] **Milestone 8**: LLM Q&A Assistant, Multi-Provider Support & Interactive Chat CLI
- [x] **Milestone 9**: Citations, Source Links, Confidence Thresholds & Guardrails
- [x] **Milestone 10**: Interactive Web UI & FastAPI Server
