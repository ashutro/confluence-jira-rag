"""Unit and integration tests for LLM providers, prompts, and RAGAssistant."""

import json
from pathlib import Path

import pytest
from rag_assistant.assistant import RAGAnswer, RAGAssistant
from rag_assistant.core.models import Chunk
from rag_assistant.llm.prompts import SYSTEM_PROMPT, format_user_prompt
from rag_assistant.llm.providers import MockLLMProvider, get_llm_provider
from rag_assistant.retrieval.retriever import RAGRetriever
from rag_assistant.sample_data import load_benchmark_queries
from rag_assistant.vector_store.embeddings import MockEmbedder
from rag_assistant.vector_store.qdrant import QdrantVectorStore


@pytest.fixture
def assistant() -> RAGAssistant:
    chunks_path = Path("data/processed/chunks.json")
    assert chunks_path.exists(), "data/processed/chunks.json must exist"

    with open(chunks_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    chunks = [Chunk.from_dict(c) for c in raw]

    embedder = MockEmbedder(dimension=384)
    vector_store = QdrantVectorStore(
        embedder=embedder,
        in_memory=True,
        default_collection="test_llm_kb",
    )
    vector_store.index_chunks(chunks, collection_name="test_llm_kb")
    retriever = RAGRetriever(vector_store=vector_store, default_top_k=3)
    llm = MockLLMProvider(model_name="mock-gpt-4o")

    return RAGAssistant(retriever=retriever, llm_provider=llm)


def test_prompt_formatting():
    q = "What is the webhook timeout policy?"
    ctx = "--- [Source 1] CONFLUENCE [ENG-PAGE-02] ---\nSection: Overview\n\nRunbook details."
    prompt = format_user_prompt(q, ctx)

    assert "Context Excerpts from Knowledge Base:" in prompt
    assert q in prompt
    assert "[ENG-PAGE-02]" in prompt


def test_mock_llm_provider_generation():
    provider = MockLLMProvider()
    user_prompt = """Context Excerpts from Knowledge Base:
============================================================
--- [Source 1] CONFLUENCE [ENG-PAGE-02]: Webhook Runbook (https://example.com/ENG-PAGE-02) ---
Section: Overview

Runbook for 504 gateway timeouts.
============================================================

Question: What should on-call do for webhook 504 timeouts?"""

    answer = provider.generate_answer(SYSTEM_PROMPT, user_prompt)
    assert "### Summary" in answer
    assert "[Source 1: ENG-PAGE-02]" in answer or "[ENG-PAGE-02]" in answer
    assert "### Sources" in answer


def test_mock_llm_provider_empty_context():
    provider = MockLLMProvider()
    user_prompt = "Question: What is the secret recipe?"
    answer = provider.generate_answer(SYSTEM_PROMPT, user_prompt)
    assert "cannot find information" in answer.lower()


def test_get_llm_provider_factory():
    mock_p = get_llm_provider("mock")
    assert isinstance(mock_p, MockLLMProvider)
    assert mock_p.name == "mock"

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_provider("unknown-provider-xyz")


def test_rag_assistant_end_to_end(assistant: RAGAssistant):
    q = "What should an on-call engineer do when the webhook worker experiences 504 Gateway Timeouts?"
    resp = assistant.ask(question=q, top_k=3)

    assert isinstance(resp, RAGAnswer)
    assert resp.question == q
    assert len(resp.sources) >= 1
    assert resp.provider == "mock"
    assert resp.execution_time_ms > 0
    assert "### Summary" in resp.answer
    assert "ENG-PAGE-02" in resp.answer or "PAY-102" in resp.answer

    # Verify serialization
    d = resp.to_dict()
    assert d["question"] == q
    assert "execution_time_ms" in d


def test_benchmark_qa_evaluation(assistant: RAGAssistant):
    queries = load_benchmark_queries()
    assert len(queries) >= 6

    for q in queries:
        resp = assistant.ask(question=q.question, top_k=3)
        assert resp.answer is not None
        assert len(resp.answer.strip()) > 50

        # Verify that at least one of target sources is cited or retrieved in context
        retrieved_ids = {c.source_id for c in resp.context.chunks}
        target_set = set(q.target_sources)
        assert bool(target_set.intersection(retrieved_ids)), (
            f"Query '{q.question}' failed to retrieve target sources {q.target_sources}. Got {retrieved_ids}"
        )
