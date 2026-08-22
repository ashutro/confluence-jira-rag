"""Qdrant Vector Database integration for semantic document indexing and retrieval."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from rag_assistant.config import Settings
from rag_assistant.core.models import Chunk
from rag_assistant.vector_store.embeddings import BaseEmbedder, get_embedder

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Standardized semantic search result item."""

    chunk_id: str
    doc_id: str
    score: float
    text: str
    raw_text: str
    title: str
    source_type: str
    source_id: str
    section_title: str
    section_path: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QdrantVectorStore:
    """Manages Qdrant vector database connection, indexing, and semantic search."""

    def __init__(
        self,
        embedder: Optional[BaseEmbedder] = None,
        client: Optional[QdrantClient] = None,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        path: Optional[str | Path] = None,
        in_memory: bool = False,
        default_collection: str = "knowledge_base",
    ) -> None:
        self.embedder = embedder or get_embedder()
        self.default_collection = default_collection

        if client:
            self.client = client
        elif in_memory:
            self.client = QdrantClient(location=":memory:")
        elif url:
            self.client = QdrantClient(url=url, api_key=api_key)
        elif path:
            Path(path).mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(path))
        else:
            # Default embedded local storage
            default_path = Path("data/qdrant_db")
            default_path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(default_path))

    @classmethod
    def from_settings(
        cls,
        settings: Optional[Settings] = None,
        embedder: Optional[BaseEmbedder] = None,
        in_memory: bool = False,
    ) -> QdrantVectorStore:
        """Instantiate QdrantVectorStore from environment settings."""
        cfg = settings or Settings.from_env()
        q_url = getattr(cfg, "qdrant_url", None)
        q_key = getattr(cfg, "qdrant_api_key", None)
        q_path = getattr(cfg, "qdrant_path", "data/qdrant_db")
        q_col = getattr(cfg, "qdrant_collection_name", "knowledge_base")

        return cls(
            embedder=embedder,
            url=q_url,
            api_key=q_key,
            path=q_path if not q_url and not in_memory else None,
            in_memory=in_memory,
            default_collection=q_col or "knowledge_base",
        )

    def init_collection(
        self,
        collection_name: Optional[str] = None,
        recreate: bool = False,
    ) -> None:
        """Initialize a Qdrant collection with vector configuration and payload indexes."""
        col_name = collection_name or self.default_collection
        collections = [c.name for c in self.client.get_collections().collections]

        if recreate and col_name in collections:
            self.client.delete_collection(col_name)
            collections.remove(col_name)

        if col_name not in collections:
            self.client.create_collection(
                collection_name=col_name,
                vectors_config=VectorParams(
                    size=self.embedder.dimension,
                    distance=Distance.COSINE,
                ),
            )
            # Create payload indexes on remote/server Qdrant (skipped in local embedded mode)
            if hasattr(self.client, "_client") and not getattr(self.client, "_is_local", True):
                for field_name in ["source_type", "source_id", "tags", "space_key", "project_key"]:
                    try:
                        self.client.create_payload_index(
                            collection_name=col_name,
                            field_name=field_name,
                            field_schema=models.PayloadSchemaType.KEYWORD,
                        )
                    except Exception:
                        pass

    def index_chunks(
        self,
        chunks: List[Chunk],
        collection_name: Optional[str] = None,
        batch_size: int = 64,
    ) -> int:
        """Embed and upsert chunks into Qdrant in batches."""
        if not chunks:
            return 0

        col_name = collection_name or self.default_collection
        self.init_collection(col_name)

        total_indexed = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.text for c in batch]
            embeddings = self.embedder.embed_batch(texts)

            points: List[PointStruct] = []
            for chunk, vector in zip(batch, embeddings):
                # Generate deterministic integer ID from chunk_id hash
                point_id = int(hashlib.md5(chunk.chunk_id.encode("utf-8")).hexdigest()[:16], 16)
                payload = {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "source_type": chunk.source_type,
                    "source_id": chunk.source_id,
                    "title": chunk.title,
                    "section_title": chunk.section_title,
                    "section_path": chunk.section_path,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "raw_text": chunk.raw_text,
                    "char_count": chunk.char_count,
                    "word_count": chunk.word_count,
                    **chunk.metadata,
                }
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                )

            self.client.upsert(collection_name=col_name, points=points)
            total_indexed += len(points)

        return total_indexed

    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: Optional[float] = None,
        filter_source: Optional[str] = None,
        filter_tags: Optional[List[str]] = None,
        collection_name: Optional[str] = None,
    ) -> List[SearchResult]:
        """Perform semantic vector search against Qdrant collection with optional filters."""
        col_name = collection_name or self.default_collection
        query_vector = self.embedder.embed_text(query)

        # Build Qdrant filter
        must_conditions: List[models.Condition] = []
        if filter_source:
            must_conditions.append(
                FieldCondition(
                    key="source_type",
                    match=MatchValue(value=filter_source.lower()),
                )
            )

        if filter_tags:
            for tag in filter_tags:
                must_conditions.append(
                    FieldCondition(
                        key="tags",
                        match=MatchValue(value=tag.lower()),
                    )
                )

        qdrant_filter = Filter(must=must_conditions) if must_conditions else None

        # Execute search (supports query_points and search methods)
        try:
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=col_name,
                    query=query_vector,
                    query_filter=qdrant_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                )
                hits = response.points
            else:
                hits = self.client.search(
                    collection_name=col_name,
                    query_vector=query_vector,
                    query_filter=qdrant_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                )
        except Exception as e:
            logger.error(f"Qdrant search query failed: {e}")
            return []

        results: List[SearchResult] = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                SearchResult(
                    chunk_id=payload.get("chunk_id", str(hit.id)),
                    doc_id=payload.get("doc_id", ""),
                    score=float(hit.score) if hasattr(hit, "score") and hit.score is not None else 0.0,
                    text=payload.get("text", ""),
                    raw_text=payload.get("raw_text", ""),
                    title=payload.get("title", ""),
                    source_type=payload.get("source_type", "unknown"),
                    source_id=payload.get("source_id", ""),
                    section_title=payload.get("section_title", ""),
                    section_path=payload.get("section_path", []),
                    metadata={k: v for k, v in payload.items() if k not in ("text", "raw_text")},
                )
            )

        return results
