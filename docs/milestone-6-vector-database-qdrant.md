# Milestone 6: Vector Database (Qdrant) & Semantic Search

## Goal

Index normalized text chunks into **Qdrant Vector Database**, generate dense vector embeddings, and perform sub-millisecond semantic search with metadata filtering across Confluence pages and Jira tickets.

```text
       data/processed/chunks.json (77 Chunks)
                         ↓
             +-----------------------+
             |    Embedding Layer    |
             |  - FastEmbed (Default)|
             |  - MockEmbedder (Dev) |
             +-----------------------+
                         ↓  (384-d Dense Vectors)
             +-------------------------------------+
             |         Qdrant Vector Store         |
             |  - Local On-Disk (`data/qdrant_db`) |
             |  - In-Memory (Unit Tests)           |
             |  - Remote Server / Cloud            |
             |  - HNSW + Cosine Distance           |
             |  - Metadata Payload Indexing        |
             +-------------------------------------+
                         ↓
           +---------------------------+
           |   Semantic Search API     |
           |   & CLI Query Interface   |
           +---------------------------+
```

---

## 1. Vector Database Architecture (Qdrant)

The system uses **Qdrant** (`qdrant-client`):
- **Embedded Local On-Disk Mode**: Stores vector index directly in `data/qdrant_db` using SQLite and memory-mapped files without requiring Docker containers.
- **In-Memory Mode**: Used during automated test runs for instant isolation (`location=":memory:"`).
- **Remote Qdrant Server / Cloud**: Supported by setting `QDRANT_URL` and `QDRANT_API_KEY` in `.env`.
- **Vector Metric**: Cosine distance ($D=384$).

---

## 2. Embedding Layer (`src/rag_assistant/vector_store/embeddings.py`)

- **`FastEmbedder`**: Uses FastEmbed with local ONNX runtime (`BAAI/bge-small-en-v1.5`, 384 dimensions) for high-performance embeddings.
- **`MockEmbedder`**: Zero-dependency deterministic hash/n-gram embedder producing unit-normalized dense vectors for instant offline testing and CI/CD.

---

## 3. Qdrant Vector Store (`src/rag_assistant/vector_store/qdrant.py`)

`QdrantVectorStore` provides:
- **`init_collection(collection_name, recreate=False)`**: Configures vector dimensions and distance metric.
- **`index_chunks(chunks, collection_name, batch_size=64)`**: Embeds chunks and batch-upserts points with full document metadata (`source_type`, `source_id`, `title`, `section_path`, `tags`, `url`, `updated_at`).
- **`search(query, limit=5, filter_source=None, filter_tags=None)`**: Executes semantic vector search with optional payload filters.

---

## 4. CLI Commands

### 1. Index Chunks into Qdrant

```bash
# Index into local Qdrant database:
rag-assistant index-qdrant --mock --db-path data/qdrant_db --recreate
```

**Output:**
```text
============================================================
Qdrant Vector Database Indexing (Milestone 6)
============================================================
Loaded 77 chunk(s) from data/processed/chunks.json
Embedder: MockEmbedder (dimension=384)
Qdrant Storage: Local on-disk (data/qdrant_db)
Target Collection: 'knowledge_base'
Recreating collection 'knowledge_base'...

Generating embeddings and upserting points to Qdrant...
Successfully indexed 77 vector points into Qdrant collection 'knowledge_base'.
```

### 2. Perform Semantic Search

```bash
# Search across all sources:
rag-assistant search-qdrant "What should on-call do for webhook 504?" --mock --limit 3

# Search filtered by source (Confluence only):
rag-assistant search-qdrant "API rate limits" --mock --source confluence --limit 3

# Search Jira tickets only:
rag-assistant search-qdrant "Apple Silicon docker build crash" --mock --source jira --limit 3
```

---

## 5. Python API Usage

```python
from rag_assistant import QdrantVectorStore, get_embedder

# 1. Initialize Vector Store
embedder = get_embedder(use_mock=True)
store = QdrantVectorStore(embedder=embedder, path="data/qdrant_db")

# 2. Search
results = store.search(
    query="How to handle webhook delivery timeouts?",
    limit=3,
    filter_source="confluence",
)

for r in results:
    print(f"[{r.score:.4f}] {r.title} > {' > '.join(r.section_path)}")
    print(f"Snippet: {r.raw_text[:200]}...\n")
```

---

## 6. Automated Testing

Run the vector store and retrieval test suite:

```bash
pytest tests/test_vector_store.py -v
```

Tests verify:
- Vector dimension and unit $L_2$ norm normalization.
- In-memory collection creation and payload storage.
- Top-$K$ semantic similarity ranking.
- Source and tag metadata filtering.
- Ground truth benchmark retrieval accuracy on all 6 evaluation queries.
