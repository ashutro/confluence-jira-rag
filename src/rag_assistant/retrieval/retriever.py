"""Context-grounded RAG retrieval engine with hybrid scoring and source citations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rag_assistant.vector_store.qdrant import QdrantVectorStore, SearchResult


@dataclass
class RetrievedChunk:
    """A retrieved chunk enriched with citation index and grounding metadata."""

    citation_index: int
    citation_tag: str
    chunk_id: str
    doc_id: str
    source_type: str
    source_id: str
    title: str
    section_title: str
    section_path: List[str]
    score: float
    raw_text: str
    text: str
    url: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation_index": self.citation_index,
            "citation_tag": self.citation_tag,
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "title": self.title,
            "section_title": self.section_title,
            "section_path": self.section_path,
            "score": round(self.score, 4),
            "raw_text": self.raw_text,
            "url": self.url,
            "metadata": self.metadata,
        }


@dataclass
class RetrievalContext:
    """Prompt-ready context container with verified source citations."""

    query: str
    chunks: List[RetrievedChunk]
    sources: List[Dict[str, Any]]
    formatted_prompt_context: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "chunks": [c.to_dict() for c in self.chunks],
            "sources": self.sources,
            "formatted_prompt_context": self.formatted_prompt_context,
        }


class RAGRetriever:
    """Retrieves and re-ranks top relevant knowledge base chunks for user questions."""

    def __init__(
        self,
        vector_store: QdrantVectorStore,
        default_top_k: int = 5,
    ) -> None:
        self.vector_store = vector_store
        self.default_top_k = default_top_k

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_source: Optional[str] = None,
        filter_tags: Optional[List[str]] = None,
        score_threshold: Optional[float] = None,
    ) -> RetrievalContext:
        """Retrieve most relevant context chunks for a question with citation tags."""
        k = top_k or self.default_top_k
        clean_query = query.strip()

        # Extract explicit key entities (e.g. PAY-102, ENG-PAGE-02, SEV-2, ADR-001)
        entities = self._extract_entities(clean_query)

        # Over-sample candidates from Qdrant vector store
        candidate_limit = max(k * 3, 10)
        candidates = self.vector_store.search(
            query=clean_query,
            limit=candidate_limit,
            filter_source=filter_source,
            filter_tags=filter_tags,
            score_threshold=score_threshold,
        )

        # Apply hybrid re-ranking
        ranked_candidates = self._rerank(
            query=clean_query,
            candidates=candidates,
            entities=entities,
            top_k=k,
        )

        # Build citations & formatted context
        retrieved_chunks: List[RetrievedChunk] = []
        sources_map: Dict[str, Dict[str, Any]] = {}

        for idx, item in enumerate(ranked_candidates, start=1):
            source_label = item.source_type.capitalize()
            citation_tag = f"[{idx}] {source_label}: {item.title}"
            url = item.metadata.get("url", "")

            r_chunk = RetrievedChunk(
                citation_index=idx,
                citation_tag=citation_tag,
                chunk_id=item.chunk_id,
                doc_id=item.doc_id,
                source_type=item.source_type,
                source_id=item.source_id,
                title=item.title,
                section_title=item.section_title,
                section_path=item.section_path,
                score=item.score,
                raw_text=item.raw_text,
                text=item.text,
                url=url,
                metadata=item.metadata,
            )
            retrieved_chunks.append(r_chunk)

            if item.doc_id not in sources_map:
                sources_map[item.doc_id] = {
                    "doc_id": item.doc_id,
                    "source_type": item.source_type,
                    "source_id": item.source_id,
                    "title": item.title,
                    "url": url,
                    "citation_indices": [idx],
                }
            else:
                sources_map[item.doc_id]["citation_indices"].append(idx)

        formatted_context = self._format_prompt_context(retrieved_chunks)

        return RetrievalContext(
            query=clean_query,
            chunks=retrieved_chunks,
            sources=list(sources_map.values()),
            formatted_prompt_context=formatted_context,
        )

    def _extract_entities(self, query: str) -> List[str]:
        """Extract domain keys and identifiers from query text."""
        patterns = [
            r"\b[A-Z]{2,10}-\d+\b",  # e.g. PAY-102, ENG-PAGE-01
            r"\bENG-PAGE-\d+\b",
            r"\bADR-\d+\b",
            r"\bSEV-\d+\b",
            r"\b(?:502|504|500|429|401|403)\b",  # HTTP status codes
        ]
        entities: List[str] = []
        for pat in patterns:
            matches = re.findall(pat, query, re.IGNORECASE)
            entities.extend([m.upper() for m in matches])
        return list(set(entities))

    def _rerank(
        self,
        query: str,
        candidates: List[SearchResult],
        entities: List[str],
        top_k: int,
    ) -> List[SearchResult]:
        """Re-rank candidates with exact entity match boosting and section diversity."""
        if not candidates:
            return []

        query_terms = set(re.findall(r"\b\w{3,}\b", query.lower()))
        scored_candidates: List[tuple[float, SearchResult]] = []

        for c in candidates:
            final_score = c.score

            # Entity boost
            text_upper = (c.title + " " + c.text).upper()
            for ent in entities:
                if ent in text_upper or ent == c.source_id.upper():
                    final_score += 0.25

            # Lexical term overlap boost
            content_lower = (c.title + " " + c.raw_text).lower()
            overlap_count = sum(1 for term in query_terms if term in content_lower)
            if query_terms:
                term_ratio = overlap_count / len(query_terms)
                final_score += term_ratio * 0.15

            scored_candidates.append((final_score, c))

        # Sort descending by re-ranked score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Select top_k with section diversity
        selected: List[SearchResult] = []
        seen_sections: set[str] = set()

        # First pass: pick highest scoring distinct sections
        for score, cand in scored_candidates:
            sec_key = f"{cand.doc_id}:{cand.section_title}"
            if sec_key not in seen_sections:
                seen_sections.add(sec_key)
                cand.score = score
                selected.append(cand)
                if len(selected) >= top_k:
                    break

        # Second pass: fill remainder if needed
        if len(selected) < top_k:
            for score, cand in scored_candidates:
                if cand not in selected:
                    cand.score = score
                    selected.append(cand)
                    if len(selected) >= top_k:
                        break

        return selected

    def _format_prompt_context(self, chunks: List[RetrievedChunk]) -> str:
        """Format retrieved chunks into a prompt-ready context block with clear source delimiters."""
        if not chunks:
            return "No relevant context found in knowledge base."

        blocks = []
        for c in chunks:
            sec_str = " > ".join(c.section_path) if c.section_path else c.section_title
            url_str = f" ({c.url})" if c.url else ""
            block = (
                f"--- [Source {c.citation_index}] {c.source_type.upper()} [{c.source_id}]: {c.title}{url_str} ---\n"
                f"Section: {sec_str}\n\n"
                f"{c.raw_text}"
            )
            blocks.append(block)

        return "\n\n".join(blocks)
