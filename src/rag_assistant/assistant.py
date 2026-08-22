"""End-to-End Enterprise RAG Assistant combining Retrieval and LLM Synthesis."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rag_assistant.llm.prompts import SYSTEM_PROMPT, format_user_prompt
from rag_assistant.llm.providers import BaseLLMProvider, MockLLMProvider, get_llm_provider
from rag_assistant.retrieval.retriever import RAGRetriever, RetrievalContext
from rag_assistant.vector_store.embeddings import get_embedder
from rag_assistant.vector_store.qdrant import QdrantVectorStore


@dataclass
class RAGAnswer:
    """Complete synthesized RAG response with source citations and execution metadata."""

    question: str
    answer: str
    sources: List[Dict[str, Any]]
    context: RetrievalContext
    provider: str
    model_name: str
    execution_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "sources": self.sources,
            "provider": self.provider,
            "model_name": self.model_name,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "context": self.context.to_dict(),
        }


class RAGAssistant:
    """Coordinates retrieval and generative answer synthesis for Confluence and Jira."""

    def __init__(
        self,
        retriever: RAGRetriever,
        llm_provider: Optional[BaseLLMProvider] = None,
    ) -> None:
        self.retriever = retriever
        self.llm_provider = llm_provider or MockLLMProvider()

    @classmethod
    def create(
        cls,
        db_path: str = "data/qdrant_db",
        collection_name: str = "knowledge_base",
        use_mock: bool = False,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
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
        return cls(retriever=retriever, llm_provider=llm)

    def ask(
        self,
        question: str,
        top_k: int = 3,
        filter_source: Optional[str] = None,
        filter_tags: Optional[List[str]] = None,
    ) -> RAGAnswer:
        """Retrieve grounded context and synthesize a verified factual answer."""
        start_time = time.perf_counter()

        # 1. Retrieve relevant context
        context = self.retriever.retrieve(
            query=question,
            top_k=top_k,
            filter_source=filter_source,
            filter_tags=filter_tags,
        )

        # 2. Format user prompt with context blocks
        user_prompt = format_user_prompt(
            question=question,
            formatted_context=context.formatted_prompt_context,
        )

        # 3. Synthesize answer via LLM
        raw_answer = self.llm_provider.generate_answer(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return RAGAnswer(
            question=question,
            answer=raw_answer,
            sources=context.sources,
            context=context,
            provider=self.llm_provider.name,
            model_name=self.llm_provider.model_name,
            execution_time_ms=duration_ms,
        )
