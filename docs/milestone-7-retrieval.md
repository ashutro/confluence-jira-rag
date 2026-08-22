# Milestone 7: Retrieval Engine & Benchmark Evaluation

## Goal

Build an enterprise-grade **Context-Grounded Retrieval Engine** that takes natural language questions, extracts domain entities, queries Qdrant dense vectors, applies hybrid re-ranking and section diversity, and formats prompt-ready context blocks with verifiable source citations.

```text
               User Question
                     ↓
         +-----------------------+
         |  Query Preprocessing  |
         |  - Entity Extraction  |  (e.g., PAY-102, 504, ADR-001)
         +-----------------------+
                     ↓
         +-----------------------+
         |  Dense Qdrant Vector  |
         |  + Lexical Boosting   |
         +-----------------------+
                     ↓
         +-----------------------+
         |  Re-Ranking & Dedup   |
         |  - Section Diversity  |
         +-----------------------+
                     ↓
         +-----------------------+
         | Context & Citations   |
         |  - Formatted Sources  |
         |  - Grounding Blocks   |
         +-----------------------+
```

---

## 1. Architecture Overview

### Components
1. **`RAGRetriever`** ([`src/rag_assistant/retrieval/retriever.py`](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/src/rag_assistant/retrieval/retriever.py)):
   - **Entity Detection**: Automatically detects Jira keys (`PAY-102`), Confluence page IDs (`ENG-PAGE-02`), HTTP codes (`504`, `502`), and architectural decision records (`ADR-001`).
   - **Candidate Over-Sampling**: Fetches $3 \times K$ candidates from Qdrant vector space.
   - **Hybrid Re-ranking**: Combines cosine similarity with exact-entity match boosting and lexical keyword overlap.
   - **Section Diversity**: Prevents adjacent redundant chunks from dominating the top-$K$ list.
   - **Prompt Context Assembly**: Generates cleanly delimited multi-source context blocks with citation tags (e.g., `--- [Source 1] CONFLUENCE [ENG-PAGE-02] ---`).

2. **`RetrievalEvaluator`** ([`src/rag_assistant/retrieval/evaluator.py`](file:///Users/ashutosh/Documents/Codex/2026-08-22/referenced-chatgpt-conversation-this-is-an/confluence-jira-rag/src/rag_assistant/retrieval/evaluator.py)):
   - Evaluates retrieval against all benchmark queries in `data/sample/queries.json`.
   - Computes standard IR metrics: **Hit Rate @ 1**, **Hit Rate @ 3**, **Hit Rate @ 5**, and **Mean Reciprocal Rank (MRR)**.

---

## 2. Benchmark Evaluation Results

Running `rag-assistant evaluate-retrieval --mock`:

| Query ID | Question Summary | Target Sources | Retrieved Rank 1 | Hit @ 1 | Hit @ 3 | RR |
|---|---|---|---|---|---|---|
| `QUERY-01` | Webhook 504 Gateway Timeout on-call runbook | `ENG-PAGE-02`, `PAY-102` | `ENG-PAGE-02` | ✅ | ✅ | 1.000 |
| `QUERY-02` | API rate limits for each merchant tier | `ENG-PAGE-04`, `PAY-104` | `PAY-104` | ✅ | ✅ | 1.000 |
| `QUERY-03` | GDPR customer PII retention & purge policy | `ENG-PAGE-05`, `PAY-107` | `ENG-PAGE-05` | ✅ | ✅ | 1.000 |
| `QUERY-04` | Docker compose crash on Apple Silicon M-series | `ENG-PAGE-03`, `PAY-105` | `PAY-105` | ✅ | ✅ | 1.000 |
| `QUERY-05` | Status of 504 batch settlement bug | `PAY-103`, `ENG-PAGE-01` | `PAY-103` | ✅ | ✅ | 1.000 |
| `QUERY-06` | Black Friday DB connection pool starvation postmortem | `PAY-106`, `ENG-PAGE-01` | `PAY-106` | ✅ | ✅ | 1.000 |

### Aggregated Metrics:
- **Total Queries**: 6
- **Hit Rate @ 1**: 100.0%
- **Hit Rate @ 3**: 100.0%
- **Hit Rate @ 5**: 100.0%
- **Mean Reciprocal Rank (MRR)**: 1.0000

---

## 3. CLI Commands

### 1. Retrieve Context for a Question
```bash
# Retrieve top-3 chunks with source citations
rag-assistant retrieve "What is the runbook for webhook 504 gateway timeouts?" --mock --top-k 3

# Retrieve prompt-ready context formatted for LLM synthesis
rag-assistant retrieve "How do rate limit tiers work?" --mock --top-k 2 --format context

# Filter retrieval by source (Confluence only)
rag-assistant retrieve "Developer onboarding steps" --mock --source confluence --top-k 2
```

### 2. Run Retrieval Benchmark Evaluation
```bash
rag-assistant evaluate-retrieval --mock
```

---

## 4. Python API Usage

```python
from rag_assistant import QdrantVectorStore, RAGRetriever, get_embedder

# 1. Initialize Retriever
embedder = get_embedder(use_mock=True)
store = QdrantVectorStore(embedder=embedder, path="data/qdrant_db")
retriever = RAGRetriever(vector_store=store, default_top_k=3)

# 2. Retrieve grounded context
ctx = retriever.retrieve(
    query="What caused the database pool starvation during Black Friday?"
)

print(f"Retrieved {len(ctx.chunks)} chunks across {len(ctx.sources)} documents\n")
for chunk in ctx.chunks:
    print(f"{chunk.citation_tag} (Score: {chunk.score:.4f})")
    print(f"Section: {' > '.join(chunk.section_path)}")
    print(f"Snippet: {chunk.raw_text[:160]}...\n")

# 3. Use prompt context for LLM generation (Milestone 8)
print("=== Formatted LLM Prompt Context ===")
print(ctx.formatted_prompt_context)
```

---

## 5. Automated Tests

```bash
pytest tests/test_retrieval.py -v
```

Tests cover:
- Entity and keyword extraction (`PAY-xxx`, `ENG-PAGE-xx`, `504`, `ADR-xxx`, `SEV-xx`).
- Hybrid re-ranking and candidate selection.
- Citation tag generation and source mapping.
- Source type filtering (`confluence` / `jira`).
- Full benchmark evaluation verifying 100% Hit Rate @ 3.
