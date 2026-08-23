"""End-to-End Enterprise RAG Assistant combining Retrieval, LLM Synthesis, and Guardrails."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rag_assistant.guardrails.service import GuardrailResult, GuardrailService
from rag_assistant.llm.prompts import SYSTEM_PROMPT, format_user_prompt
from rag_assistant.llm.providers import BaseLLMProvider, MockLLMProvider, get_llm_provider
from rag_assistant.retrieval.retriever import RAGRetriever, RetrievalContext
from rag_assistant.vector_store.embeddings import get_embedder
from rag_assistant.vector_store.qdrant import QdrantVectorStore


@dataclass
class RAGAnswer:
    """Complete synthesized RAG response with source citations, guardrails, and execution metadata."""

    question: str
    answer: str
    sources: List[Dict[str, Any]]
    context: RetrievalContext
    provider: str
    model_name: str
    execution_time_ms: float
    guardrail: Optional[GuardrailResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "sources": self.sources,
            "provider": self.provider,
            "model_name": self.model_name,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "guardrail": self.guardrail.to_dict() if self.guardrail else None,
            "context": self.context.to_dict(),
        }


class RAGAssistant:
    """Coordinates retrieval, generative answer synthesis, and hallucination guardrails."""

    def __init__(
        self,
        retriever: RAGRetriever,
        llm_provider: Optional[BaseLLMProvider] = None,
        guardrails: Optional[GuardrailService] = None,
        default_score_threshold: float = 0.20,
    ) -> None:
        self.retriever = retriever
        self.llm_provider = llm_provider or MockLLMProvider()
        self.guardrails = guardrails or GuardrailService(default_threshold=default_score_threshold)
        self.default_score_threshold = default_score_threshold

    @classmethod
    def create(
        cls,
        db_path: str = "data/qdrant_db",
        collection_name: str = "knowledge_base",
        use_mock: bool = False,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        score_threshold: float = 0.20,
        in_memory: bool = False,
    ) -> RAGAssistant:
        """Convenience factory creating all RAG components."""
        embedder = get_embedder(use_mock=use_mock)
        vector_store = QdrantVectorStore(
            embedder=embedder,
            path=db_path if not in_memory else None,
            in_memory=in_memory,
            default_collection=collection_name,
        )
        retriever = RAGRetriever(vector_store=vector_store, default_top_k=3)
        llm = get_llm_provider(
            provider_name=provider_name,
            model_name=model_name,
            use_mock=use_mock,
        )
        guardrails = GuardrailService(default_threshold=score_threshold)
        return cls(
            retriever=retriever,
            llm_provider=llm,
            guardrails=guardrails,
            default_score_threshold=score_threshold,
        )

    def ask(
        self,
        question: str,
        top_k: int = 3,
        filter_source: Optional[str] = None,
        filter_tags: Optional[List[str]] = None,
        score_threshold: Optional[float] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> RAGAnswer:
        """Retrieve grounded context, apply guardrails, and synthesize a verified factual answer."""
        start_time = time.perf_counter()
        effective_threshold = score_threshold if score_threshold is not None else self.default_score_threshold

        # 1. Retrieve relevant context
        context = self.retriever.retrieve(
            query=question,
            top_k=top_k,
            filter_source=filter_source,
            filter_tags=filter_tags,
        )

        # 2. Guardrail check: Confidence score and domain grounding
        if not self.guardrails.is_confident(context, score_threshold=effective_threshold):
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            fallback_answer = self.guardrails.format_fallback_response(question)
            guardrail_res = GuardrailResult(
                is_grounded=False,
                citations_valid=True,
                confidence_score=max((c.score for c in context.chunks), default=0.0),
                cited_source_ids=[],
                available_source_ids=[s["source_id"] for s in context.sources],
                hallucinated_source_ids=[],
            )
            return RAGAnswer(
                question=question,
                answer=fallback_answer,
                sources=[],
                context=context,
                provider="guardrail_shortcircuit",
                model_name=self.llm_provider.model_name,
                execution_time_ms=duration_ms,
                guardrail=guardrail_res,
            )

        # 3. Format user prompt with context blocks
        user_prompt = format_user_prompt(
            question=question,
            formatted_context=context.formatted_prompt_context,
        )

        # 4. Synthesize answer via LLM (multi-turn if history provided)
        if history and hasattr(self.llm_provider, "generate_with_messages"):
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for h in history[-6:]:
                role = h.get("role", "user")
                content = h.get("content") or h.get("text") or ""
                if content:
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_prompt})
            raw_answer = self.llm_provider.generate_with_messages(messages)
        else:
            raw_answer = self.llm_provider.generate_answer(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )

        # 5. Citation verification and source link enrichment
        guardrail_audit = self.guardrails.verify_citations(raw_answer, context)
        final_answer = self.guardrails.append_source_links(raw_answer, context)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return RAGAnswer(
            question=question,
            answer=final_answer,
            sources=context.sources,
            context=context,
            provider=self.llm_provider.name,
            model_name=self.llm_provider.model_name,
            execution_time_ms=duration_ms,
            guardrail=guardrail_audit,
        )
