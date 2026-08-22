"""Unit tests for Context-Grounded Retrieval Engine and Benchmark Evaluator."""

import json
from pathlib import Path

import pytest
from rag_assistant.core.models import Chunk
from rag_assistant.retrieval.evaluator import RetrievalEvaluator
from rag_assistant.retrieval.retriever import RAGRetriever, RetrievalContext, RetrievedChunk
from rag_assistant.sample_data import load_benchmark_queries
from rag_assistant.vector_store.embeddings import MockEmbedder
from rag_assistant.vector_store.qdrant import QdrantVectorStore


@pytest.fixture
def retriever() -> RAGRetriever:
    chunks_path = Path("data/processed/chunks.json")
    assert chunks_path.exists(), "data/processed/chunks.json must exist for retrieval testing"

    with open(chunks_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    chunks = [Chunk.from_dict(c) for c in raw]

    embedder = MockEmbedder(dimension=384)
    vector_store = QdrantVectorStore(
        embedder=embedder,
        in_memory=True,
        default_collection="test_retrieval_kb",
    )
    vector_store.index_chunks(chunks, collection_name="test_retrieval_kb")
    return RAGRetriever(vector_store=vector_store, default_top_k=3)


def test_entity_extraction():
    retriever = RAGRetriever(vector_store=None)  # type: ignore[arg-type]
    entities = retriever._extract_entities(
        "What is the triage runbook for webhook 504 errors in PAY-102 and ADR-001 under SEV-2?"
    )
    assert "504" in entities
    assert "PAY-102" in entities
    assert "ADR-001" in entities
    assert "SEV-2" in entities


def test_retrieval_and_citation_generation(retriever: RAGRetriever):
    query = "What should the on-call engineer do during a webhook 504 gateway timeout?"
    ctx = retriever.retrieve(query=query, top_k=3)

    assert isinstance(ctx, RetrievalContext)
    assert len(ctx.chunks) == 3
    assert len(ctx.sources) >= 1

    # Check first chunk citation
    top_chunk = ctx.chunks[0]
    assert isinstance(top_chunk, RetrievedChunk)
    assert top_chunk.citation_index == 1
    assert "CONFLUENCE" in top_chunk.citation_tag.upper() or "JIRA" in top_chunk.citation_tag.upper()
    assert top_chunk.source_id in ["ENG-PAGE-02", "PAY-102", "PAY-103"]

    # Check prompt context formatting
    prompt_ctx = ctx.formatted_prompt_context
    assert "--- [Source 1]" in prompt_ctx
    assert "Section:" in prompt_ctx


def test_retrieval_source_filter(retriever: RAGRetriever):
    # Filter Jira only
    jira_ctx = retriever.retrieve(
        query="memory leak in webhook dispatcher",
        top_k=3,
        filter_source="jira",
    )
    for c in jira_ctx.chunks:
        assert c.source_type == "jira"

    # Filter Confluence only
    conf_ctx = retriever.retrieve(
        query="memory leak in webhook dispatcher",
        top_k=3,
        filter_source="confluence",
    )
    for c in conf_ctx.chunks:
        assert c.source_type == "confluence"


def test_benchmark_evaluation_metrics(retriever: RAGRetriever):
    evaluator = RetrievalEvaluator(retriever=retriever)
    report = evaluator.evaluate()

    assert report.total_queries == 6
    assert report.hit_rate_at_3 == 1.0  # 100% of benchmark queries hit target source in Top 3
    assert report.hit_rate_at_1 >= 0.6
    assert report.mrr >= 0.8

    # Verify report dictionary serialization
    d = report.to_dict()
    assert d["hit_rate_at_3"] == 1.0
    assert len(d["query_results"]) == 6
