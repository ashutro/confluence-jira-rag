# Confluence + Jira RAG Assistant

Internal knowledge assistant that answers questions from Confluence documentation pages and Jira issues using Qdrant Vector Database and LLM synthesis.

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
| LLM Q&A Synthesis (OpenAI / Anthropic / Gemini)     |
+-----------------------------------------------------+
```

## Project Structure

```text
confluence-jira-rag/
  data/
    sample/             # Milestone 2 sample dataset (Confluence & Jira)
      confluence/       # Confluence pages (Markdown & pages.json)
      jira/             # Jira issues (issues.json)
      queries.json      # Benchmark evaluation questions
    raw/                # Exported raw source data
      confluence/       # Confluence connector output (pages.json)
      jira/             # Jira connector output (issues.json)
    processed/          # Normalized & chunked datasets ready for RAG
      normalized_documents.json # UnifiedDocument collection
      chunks.json       # Context-enriched text chunks
    qdrant_db/          # Local on-disk Qdrant vector database
  docs/                 # Notes and project documentation
    milestone-1-setup.md
    milestone-2-atlassian-setup.md
    milestone-3-confluence-connector.md
    milestone-4-jira-connector.md
    milestone-5-normalization-chunking.md
    milestone-6-vector-database-qdrant.md
    milestone-7-retrieval.md
    milestone-8-llm-assistant.md
  src/
    rag_assistant/      # Python package
      config.py         # Environment configuration
      cli.py            # Command Line Interface
      assistant.py      # End-to-end RAG assistant coordinator
      sample_data.py    # Sample dataset loaders
      core/
        models.py       # UnifiedDocument & Chunk models
      connectors/       # External source connectors
        confluence.py   # Confluence REST API connector
        html_cleaner.py # XHTML storage format cleaner
        jira.py         # Jira REST API connector
        adf_cleaner.py  # Jira Atlassian Document Format cleaner
      processing/       # Normalization & Chunking
        normalizer.py   # Document normalizer
        chunker.py      # Hierarchical Markdown chunker
      vector_store/     # Embeddings & Vector Database (Milestone 6)
        embeddings.py   # FastEmbed & MockEmbedder
        qdrant.py       # QdrantVectorStore & SearchResult
      retrieval/        # Retrieval Engine & Evaluation (Milestone 7)
        retriever.py    # RAGRetriever & RetrievalContext
        evaluator.py    # RetrievalEvaluator & BenchmarkReport
      llm/              # LLM Generation & Prompts (Milestone 8)
        prompts.py      # System prompts & grounding templates
        providers.py    # OpenAI, Anthropic, Gemini, Ollama, Mock providers
  tests/                # Automated tests
    test_sample_data.py
    test_confluence_connector.py
    test_jira_connector.py
    test_normalizer_and_chunker.py
    test_vector_store.py
    test_retrieval.py
    test_llm_and_assistant.py
```

## Local Setup

Create and activate the virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Run automated tests (47/47 passing):

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

### 4. Ask Questions with the RAG Assistant (Milestone 8)
```bash
# Ask a single question:
rag-assistant ask "What is the runbook for webhook 504 gateway timeouts?" --mock

# Interactive terminal chat:
rag-assistant chat --mock

# Run end-to-end benchmark evaluation:
rag-assistant evaluate-qa --mock
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
