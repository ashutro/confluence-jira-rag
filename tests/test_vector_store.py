"""Unit tests for Qdrant Vector Store, Embeddings, and Semantic Search."""

import json
from pathlib import Path

import pytest
from rag_assistant.core.models import Chunk
from rag_assistant.sample_data import load_benchmark_queries
from rag_assistant.vector_store.embeddings import MockEmbedder, get_embedder
from rag_assistant.vector_store.qdrant import QdrantVectorStore, SearchResult


# -----------------------------------------------------------------------------
# Embedding Layer Tests
# -----------------------------------------------------------------------------

def test_mock_embedder_properties():
    embedder = MockEmbedder(dimension=384)
    assert embedder.dimension == 384

    vec1 = embedder.embed_text("Incident response runbook for webhook 504 gateway timeout")
    assert len(vec1) == 384
    # Verify L2 norm is ~1.0
    norm = sum(x * x for x in vec1) ** 0.5
    assert pytest.approx(norm, 0.001) == 1.0

    # Test batch embedding
    batch = embedder.embed_batch(["Hello world", "Payment settlement engine"])
    assert len(batch) == 2
    assert len(batch[0]) == 384
    assert len(batch[1]) == 384


def test_mock_embedder_semantic_similarity():
    embedder = MockEmbedder(dimension=384)

    # Cosine dot product
    def dot_product(v1, v2):
        return sum(a * b for a, b in zip(v1, v2))

    v_query = embedder.embed_text("webhook 504 gateway timeout error")
    v_related = embedder.embed_text("Webhook worker 504 gateway timeout runbook")
    v_unrelated = embedder.embed_text("GDPR data retention policy and customer anonymization")

    sim_related = dot_product(v_query, v_related)
    sim_unrelated = dot_product(v_query, v_unrelated)

    assert sim_related > sim_unrelated
    assert sim_related > 0.4


# -----------------------------------------------------------------------------
# Qdrant Vector Store Tests
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_chunks() -> list[Chunk]:
    chunks_path = Path("data/processed/chunks.json")
    if chunks_path.exists():
        with open(chunks_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [Chunk.from_dict(c) for c in raw]

    # Minimal fallback chunks if processed file does not exist yet
    return [
        Chunk(
            chunk_id="confluence:ENG-PAGE-02:chunk_0",
            doc_id="confluence:ENG-PAGE-02",
            source_type="confluence",
            source_id="ENG-PAGE-02",
            title="Incident Response Runbook: Payment Webhook 504 Gateway Timeouts",
            section_title="Overview",
            section_path=["Runbook", "Overview"],
            chunk_index=0,
            text="[Document: Runbook]\n[Section: Overview]\n\nResponding to 504 Gateway Timeouts on webhooks.",
            raw_text="Responding to 504 Gateway Timeouts on webhooks.",
            metadata={"space_key": "ENG", "tags": ["runbook", "webhooks", "sev-2", "confluence"]},
        ),
        Chunk(
            chunk_id="jira:PAY-104:chunk_0",
            doc_id="jira:PAY-104",
            source_type="jira",
            source_id="PAY-104",
            title="[PAY-104] Implement Tiered Rate Limiting middleware",
            section_title="Description",
            section_path=["[PAY-104] Rate Limiting", "Description"],
            chunk_index=0,
            text="[Document: PAY-104]\n[Section: Description]\n\nToken bucket rate limiting with Redis for Starter, Growth, Enterprise tiers.",
            raw_text="Token bucket rate limiting with Redis for Starter, Growth, Enterprise tiers.",
            metadata={"project_key": "PAY", "tags": ["rate-limiting", "redis", "jira"]},
        ),
    ]


def test_qdrant_in_memory_indexing_and_search(sample_chunks: list[Chunk]):
    embedder = MockEmbedder(dimension=384)
    vector_store = QdrantVectorStore(
        embedder=embedder,
        in_memory=True,
        default_collection="test_kb",
    )

    indexed_count = vector_store.index_chunks(sample_chunks, collection_name="test_kb")
    assert indexed_count == len(sample_chunks)

    # Search for webhook runbook
    results = vector_store.search(
        query="webhook 504 timeout runbook triage",
        limit=5,
        collection_name="test_kb",
    )
    assert len(results) > 0
    top_hit = results[0]
    assert isinstance(top_hit, SearchResult)
    assert top_hit.score > 0
    assert "webhook" in top_hit.text.lower() or "504" in top_hit.text.lower()


def test_qdrant_source_filtering(sample_chunks: list[Chunk]):
    embedder = MockEmbedder(dimension=384)
    vector_store = QdrantVectorStore(
        embedder=embedder,
        in_memory=True,
        default_collection="test_kb",
    )
    vector_store.index_chunks(sample_chunks, collection_name="test_kb")

    # Filter by Confluence
    conf_results = vector_store.search(
        query="rate limiting or webhooks",
        limit=10,
        filter_source="confluence",
        collection_name="test_kb",
    )
    for res in conf_results:
        assert res.source_type == "confluence"

    # Filter by Jira
    jira_results = vector_store.search(
        query="rate limiting or webhooks",
        limit=10,
        filter_source="jira",
        collection_name="test_kb",
    )
    for res in jira_results:
        assert res.source_type == "jira"


def test_benchmark_queries_retrieval(sample_chunks: list[Chunk]):
    embedder = MockEmbedder(dimension=384)
    vector_store = QdrantVectorStore(
        embedder=embedder,
        in_memory=True,
        default_collection="test_benchmark_kb",
    )
    vector_store.index_chunks(sample_chunks, collection_name="test_benchmark_kb")

    queries = load_benchmark_queries()
    assert len(queries) >= 5

    # Test that each benchmark query retrieves at least one of its target sources in top 5
    for q in queries:
        results = vector_store.search(
            query=q.question,
            limit=5,
            collection_name="test_benchmark_kb",
        )
        retrieved_source_ids = {r.source_id for r in results}
        # Check intersection with expected target sources
        intersection = set(q.target_sources).intersection(retrieved_source_ids)
        assert len(intersection) > 0, (
            f"Query '{q.question}' expected one of {q.target_sources}, but got {retrieved_source_ids}"
        )
