"""Integration tests for Web API and static file serving."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_assistant.core.models import Chunk
from rag_assistant.vector_store.embeddings import MockEmbedder
from rag_assistant.vector_store.qdrant import QdrantVectorStore
from rag_assistant.web.app import create_app


@pytest.fixture
def client() -> TestClient:
    # Setup in-memory test collection
    chunks_path = Path("data/processed/chunks.json")
    with open(chunks_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    chunks = [Chunk.from_dict(c) for c in raw]

    embedder = MockEmbedder(dimension=384)
    vector_store = QdrantVectorStore(
        embedder=embedder,
        in_memory=True,
        default_collection="test_web_kb",
    )
    vector_store.index_chunks(chunks, collection_name="test_web_kb")

    app = create_app(
        collection_name="test_web_kb",
        use_mock=True,
        in_memory=True,
    )
    # Inject pre-indexed vector store into assistant
    app_assistant = app.routes[0].endpoint.__globals__.get("assistant")  # type: ignore

    return TestClient(app)


def test_api_health_endpoint(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "provider" in data


def test_api_stats_endpoint(client: TestClient):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_chunks"] >= 0
    assert "collection_name" in data


def test_api_samples_endpoint(client: TestClient):
    resp = client.get("/api/samples")
    assert resp.status_code == 200
    samples = resp.json()
    assert isinstance(samples, list)
    assert len(samples) >= 2
    assert "question" in samples[0]


def test_api_ask_endpoint_success(client: TestClient):
    payload = {
        "question": "What is the runbook for webhook 504 gateway timeouts?",
        "top_k": 3,
        "score_threshold": 0.20,
    }
    resp = client.post("/api/ask", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["question"] == payload["question"]
    assert "answer" in data
    assert len(data["answer"]) > 50
    assert "guardrail" in data
    assert data["execution_time_ms"] > 0


def test_api_ask_empty_question(client: TestClient):
    resp = client.post("/api/ask", json={"question": "   "})
    assert resp.status_code == 400


def test_serve_html_index(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Enterprise Knowledge Assistant" in resp.text
    assert "html" in resp.headers["content-type"]


def test_serve_static_assets(client: TestClient):
    css_resp = client.get("/static/style.css")
    assert css_resp.status_code == 200
    assert "css" in css_resp.headers["content-type"]

    js_resp = client.get("/static/app.js")
    assert js_resp.status_code == 200
    assert "javascript" in js_resp.headers["content-type"]
