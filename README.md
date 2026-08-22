# Confluence + Jira RAG Assistant

Internal knowledge assistant that answers questions from Confluence pages and Jira issues.

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
  src/
    rag_assistant/      # Python package
      config.py         # Environment configuration
      cli.py            # Command Line Interface
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
  tests/                # Automated tests
    test_sample_data.py
    test_confluence_connector.py
    test_jira_connector.py
    test_normalizer_and_chunker.py
    test_vector_store.py
    test_retrieval.py
```

## Local Setup

Create and activate the virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Run automated tests:

```bash
pytest tests/ -v
```

## Data & Retrieval Pipeline Commands

### 1. Ingest Data (Milestones 3 & 4)
```bash
rag-assistant fetch-confluence --mock --output data/raw/confluence/pages.json
rag-assistant fetch-jira --mock --output data/raw/jira/issues.json
```

### 2. Normalize and Chunk (Milestone 5)
```bash
rag-assistant normalize-chunk --mock
```

### 3. Vector Database Indexing (Milestone 6)
```bash
rag-assistant index-qdrant --mock --db-path data/qdrant_db --recreate
```

### 4. Context Retrieval & Evaluation (Milestone 7)
```bash
# Retrieve grounded context with source citations:
rag-assistant retrieve "What is the runbook for webhook 504 gateway timeouts?" --mock --top-k 3

# Retrieve formatted LLM prompt context:
rag-assistant retrieve "How do rate limit tiers work?" --mock --top-k 2 --format context

# Run retrieval benchmark evaluation:
rag-assistant evaluate-retrieval --mock
```

See [docs/milestone-7-retrieval.md](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/docs/milestone-7-retrieval.md) for full details.

## Status

- [x] **Milestone 1**: Local Project Setup
- [x] **Milestone 2**: Atlassian Setup & Sample Data
- [x] **Milestone 3**: Confluence Connector
- [x] **Milestone 4**: Jira Connector
- [x] **Milestone 5**: Data Normalization & Chunking
- [x] **Milestone 6**: Vector Database (Qdrant) & Semantic Search
- [x] **Milestone 7**: Context-Grounded Retrieval & Benchmark Evaluation
- [ ] **Milestone 8**: LLM Q&A Assistant CLI / Web App
