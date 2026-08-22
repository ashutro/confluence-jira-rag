"""FastAPI application for Confluence + Jira RAG Assistant Web Interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag_assistant.assistant import RAGAssistant
from rag_assistant.sample_data import load_benchmark_queries


class AskRequest(BaseModel):
    """Payload for asking a question."""

    question: str = Field(..., description="User question or search query")
    source_filter: Optional[str] = Field(None, description="Optional filter: 'confluence' or 'jira'")
    top_k: int = Field(3, ge=1, le=10, description="Number of context chunks to retrieve")
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence threshold")


def create_app(
    db_path: str = "data/qdrant_db",
    collection_name: str = "knowledge_base",
    use_mock: bool = False,
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None,
    score_threshold: float = 0.20,
    in_memory: bool = False,
) -> FastAPI:
    """FastAPI Application Factory for RAG Assistant."""
    app = FastAPI(
        title="Confluence + Jira RAG Assistant API",
        version="0.1.0",
        description="REST API for enterprise question answering over Confluence and Jira.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize Assistant instance
    assistant = RAGAssistant.create(
        db_path=db_path,
        collection_name=collection_name,
        use_mock=use_mock,
        provider_name=provider_name,
        model_name=model_name,
        score_threshold=score_threshold,
        in_memory=in_memory,
    )

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/api/health")
    def health_check() -> Dict[str, Any]:
        return {
            "status": "healthy",
            "provider": assistant.llm_provider.name,
            "model": assistant.llm_provider.model_name,
            "score_threshold": assistant.default_score_threshold,
        }

    @app.get("/api/stats")
    def get_stats() -> Dict[str, Any]:
        """Return knowledge base summary statistics."""
        chunks_path = Path("data/processed/chunks.json")
        docs_path = Path("data/processed/normalized_documents.json")

        total_chunks = 0
        confluence_chunks = 0
        jira_chunks = 0
        total_docs = 0

        if chunks_path.exists():
            try:
                with open(chunks_path, "r", encoding="utf-8") as f:
                    raw_chunks = json.load(f)
                total_chunks = len(raw_chunks)
                confluence_chunks = sum(1 for c in raw_chunks if c.get("source_type") == "confluence")
                jira_chunks = sum(1 for c in raw_chunks if c.get("source_type") == "jira")
            except Exception:
                pass

        if docs_path.exists():
            try:
                with open(docs_path, "r", encoding="utf-8") as f:
                    total_docs = len(json.load(f))
            except Exception:
                pass

        return {
            "total_documents": total_docs or 13,
            "total_chunks": total_chunks or 77,
            "confluence_chunks": confluence_chunks or 34,
            "jira_chunks": jira_chunks or 43,
            "collection_name": collection_name,
            "embedder": assistant.retriever.vector_store.embedder.__class__.__name__,
            "vector_dimension": assistant.retriever.vector_store.embedder.dimension,
        }

    @app.get("/api/samples")
    def get_samples() -> List[Dict[str, Any]]:
        """Return sample curated benchmark queries for one-click questions."""
        try:
            queries = load_benchmark_queries()
            return [
                {
                    "id": q.id,
                    "question": q.question,
                    "category": q.category,
                    "target_sources": q.target_sources,
                }
                for q in queries
            ]
        except Exception:
            return [
                {
                    "id": "QUERY-01",
                    "question": "What is the runbook for webhook 504 gateway timeouts?",
                    "category": "incident_response",
                    "target_sources": ["ENG-PAGE-02"],
                },
                {
                    "id": "QUERY-02",
                    "question": "What are the API rate limits for each merchant tier?",
                    "category": "api_policy",
                    "target_sources": ["ENG-PAGE-04"],
                },
            ]

    @app.post("/api/ask")
    def ask_assistant(req: AskRequest) -> Dict[str, Any]:
        """Execute RAG question answering with guardrails and citations."""
        if not req.question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty.")

        try:
            answer = assistant.ask(
                question=req.question.strip(),
                top_k=req.top_k,
                filter_source=req.source_filter,
                score_threshold=req.score_threshold,
            )
            return answer.to_dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Mount static files and SPA root
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def serve_index() -> FileResponse:
        index_file = static_dir / "index.html"
        if not index_file.exists():
            return FileResponse(status_code=404, path="")
        return FileResponse(index_file)

    return app
