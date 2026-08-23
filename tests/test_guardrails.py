"""Unit and adversarial tests for GuardrailService, citation verification, and hallucination defense."""

import json
from pathlib import Path

import pytest
from rag_assistant.assistant import RAGAssistant
from rag_assistant.core.models import Chunk
from rag_assistant.guardrails.service import GuardrailResult, GuardrailService
from rag_assistant.llm.providers import MockLLMProvider
from rag_assistant.retrieval.retriever import RAGRetriever, RetrievalContext, RetrievedChunk
from rag_assistant.vector_store.embeddings import MockEmbedder
from rag_assistant.vector_store.qdrant import QdrantVectorStore


@pytest.fixture
def sample_context() -> RetrievalContext:
    chunks = [
        RetrievedChunk(
            citation_index=1,
            citation_tag="[1] Confluence: Incident Response Runbook: Payment Webhook 504 Gateway Timeouts",
            chunk_id="confluence:ENG-PAGE-02:chunk_0",
            doc_id="confluence:ENG-PAGE-02",
            source_type="confluence",
            source_id="ENG-PAGE-02",
            title="Incident Response Runbook: Payment Webhook 504 Gateway Timeouts",
            section_title="Overview",
            section_path=["Runbook", "Overview"],
            score=0.85,
            raw_text="Runbook for webhook 504 triage.",
            text="[Document: Runbook]\nRunbook for webhook 504 triage.",
            url="https://cloudscale-pay.atlassian.net/wiki/spaces/ENG/pages/1002/Runbook",
        ),
        RetrievedChunk(
            citation_index=2,
            citation_tag="[2] Jira: [PAY-102] Webhook worker exhausted memory",
            chunk_id="jira:PAY-102:chunk_0",
            doc_id="jira:PAY-102",
            source_type="jira",
            source_id="PAY-102",
            title="[PAY-102] Webhook worker exhausted memory",
            section_title="Description",
            section_path=["Description"],
            score=0.72,
            raw_text="Memory exhaustion under traffic burst.",
            text="[Document: PAY-102]\nMemory exhaustion.",
            url="https://cloudscale-pay.atlassian.net/browse/PAY-102",
        ),
    ]
    sources = [
        {"doc_id": "confluence:ENG-PAGE-02", "source_type": "confluence", "source_id": "ENG-PAGE-02", "title": "Runbook", "url": "https://example.com/ENG-PAGE-02", "citation_indices": [1]},
        {"doc_id": "jira:PAY-102", "source_type": "jira", "source_id": "PAY-102", "title": "PAY-102 Bug", "url": "https://example.com/PAY-102", "citation_indices": [2]},
    ]
    return RetrievalContext(
        query="webhook 504 timeout",
        chunks=chunks,
        sources=sources,
        formatted_prompt_context="Formatted context",
    )


@pytest.fixture
def assistant() -> RAGAssistant:
    chunks_path = Path("data/processed/chunks.json")
    with open(chunks_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    chunks = [Chunk.from_dict(c) for c in raw]

    embedder = MockEmbedder(dimension=384)
    vector_store = QdrantVectorStore(
        embedder=embedder,
        in_memory=True,
        default_collection="test_guardrails_kb",
    )
    vector_store.index_chunks(chunks, collection_name="test_guardrails_kb")
    retriever = RAGRetriever(vector_store=vector_store, default_top_k=3)
    llm = MockLLMProvider(model_name="mock-gpt-4o")

    return RAGAssistant(retriever=retriever, llm_provider=llm, default_score_threshold=0.20)


# -----------------------------------------------------------------------------
# Guardrail Service Unit Tests
# -----------------------------------------------------------------------------

def test_guardrail_confidence_check(sample_context: RetrievalContext):
    service = GuardrailService(default_threshold=0.20)
    assert service.is_confident(sample_context) is True
    assert service.is_confident(sample_context, score_threshold=0.90) is False

    empty_ctx = RetrievalContext(query="test", chunks=[], sources=[], formatted_prompt_context="")
    assert service.is_confident(empty_ctx) is False


def test_citation_verification_valid(sample_context: RetrievalContext):
    service = GuardrailService()
    valid_answer = "According to runbook [ENG-PAGE-02] and related issue [PAY-102], scale pods."
    result = service.verify_citations(valid_answer, sample_context)

    assert result.is_grounded is True
    assert result.citations_valid is True
    assert "ENG-PAGE-02" in result.cited_source_ids
    assert "PAY-102" in result.cited_source_ids
    assert len(result.hallucinated_source_ids) == 0


def test_citation_verification_hallucinated(sample_context: RetrievalContext):
    service = GuardrailService()
    hallucinated_answer = "Refer to policy [ENG-PAGE-99] and ticket [PAY-999] for details."
    result = service.verify_citations(hallucinated_answer, sample_context)

    assert result.citations_valid is False
    assert "ENG-PAGE-99" in result.hallucinated_source_ids
    assert "PAY-999" in result.hallucinated_source_ids


def test_append_source_links(sample_context: RetrievalContext):
    service = GuardrailService()
    answer_without_sources = "Here is the solution to your problem."
    enriched = service.append_source_links(answer_without_sources, sample_context)

    assert "### Sources & References" in enriched
    assert "ENG-PAGE-02" in enriched
    assert "PAY-102" in enriched
    assert "https://example.com/ENG-PAGE-02" in enriched


# -----------------------------------------------------------------------------
# End-to-End Adversarial & Out-of-Domain Tests
# -----------------------------------------------------------------------------

def test_in_domain_query_success(assistant: RAGAssistant):
    q = "What is the runbook for webhook 504 gateway timeouts?"
    ans = assistant.ask(question=q)

    assert ans.guardrail is not None
    assert ans.guardrail.is_grounded is True
    assert ans.provider != "guardrail_shortcircuit"
    assert "ENG-PAGE-02" in ans.answer


def test_out_of_domain_query_refusal(assistant: RAGAssistant):
    out_of_domain_queries = [
        "What is the best recipe for baking chocolate chip cookies?",
        "Who was the top goal scorer in the 1998 football tournament?",
        "How do I build a rocket to travel to Jupiter?",
    ]

    for q in out_of_domain_queries:
        ans = assistant.ask(question=q, score_threshold=0.25)
        # Should cleanly state lack of information
        lower = ans.answer.lower()
        is_refusal = (
            "cannot find information" in lower
            or "do not have enough information" in lower
            or ans.provider == "guardrail_shortcircuit"
        )
        assert is_refusal, f"Query '{q}' should have been refused, but got: {ans.answer}"


def test_high_threshold_triggers_fallback(assistant: RAGAssistant):
    q = "What are the rate limit tiers?"
    # Forcing unrealistic 0.99 score threshold should safely trigger fallback
    ans = assistant.ask(question=q, score_threshold=0.99)

    assert ans.provider == "guardrail_shortcircuit"
    assert "do not have enough information" in ans.answer.lower()
    assert len(ans.sources) == 0


def test_guardrail_toggle_disabled(assistant: RAGAssistant):
    # When strict guardrails are disabled, query should not be short-circuited
    q = "What are the rate limit tiers?"
    ans = assistant.ask(question=q, score_threshold=0.99, enable_guardrails=False)

    assert ans.provider != "guardrail_shortcircuit"
    assert len(ans.answer) > 20
