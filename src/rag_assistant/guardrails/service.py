"""Guardrails and citation verification service for hallucination prevention."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rag_assistant.retrieval.retriever import RetrievalContext

COMMON_STOPWORDS = {
    "what", "where", "when", "which", "who", "whom", "whose", "why", "how",
    "does", "have", "with", "from", "about", "this", "that", "there", "they",
    "will", "would", "should", "could", "best", "some", "more", "make", "tell",
    "give", "show", "find", "know", "help", "please", "into", "onto", "been",
    "the", "for", "and", "are", "was", "were", "can", "you", "your", "all",
    "any", "not", "our", "out", "one", "two", "has", "had", "its", "use",
}


@dataclass
class GuardrailResult:
    """Audit result from citation and grounding guardrail verification."""

    is_grounded: bool
    citations_valid: bool
    confidence_score: float
    cited_source_ids: List[str] = field(default_factory=list)
    available_source_ids: List[str] = field(default_factory=list)
    hallucinated_source_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_grounded": self.is_grounded,
            "citations_valid": self.citations_valid,
            "confidence_score": round(self.confidence_score, 4),
            "cited_source_ids": self.cited_source_ids,
            "available_source_ids": self.available_source_ids,
            "hallucinated_source_ids": self.hallucinated_source_ids,
        }


class GuardrailService:
    """Enforces retrieval score thresholds, citation integrity, and 'I don't know' fallbacks."""

    def __init__(self, default_threshold: float = 0.20) -> None:
        self.default_threshold = default_threshold

    def is_confident(
        self,
        context: RetrievalContext,
        score_threshold: Optional[float] = None,
    ) -> bool:
        """Check if retrieved context meets the minimum confidence threshold and domain grounding."""
        threshold = score_threshold if score_threshold is not None else self.default_threshold
        if not context.chunks:
            return False

        max_score = max(c.score for c in context.chunks)
        if max_score < threshold:
            return False

        # Domain concept whitelist for meta-questions (e.g. "how many jira details you have", "what docs exist")
        DOMAIN_TERMS = {
            "jira", "confluence", "ticket", "tickets", "issue", "issues",
            "page", "pages", "doc", "docs", "document", "documents",
            "detail", "details", "runbook", "runbooks", "summary", "summarize",
            "overview", "architecture", "payment", "payments", "service", "services",
            "kb", "database", "platform", "system", "infrastructure",
        }

        words = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", context.query.lower())
        if any(w in DOMAIN_TERMS for w in words):
            return True

        content_words = [w for w in words if w not in COMMON_STOPWORDS and len(w) >= 4]
        if content_words:
            all_context_text = " ".join(
                [c.source_type + " " + c.title + " " + c.raw_text + " " + c.source_id for c in context.chunks]
            ).lower()
            has_lexical_match = any(cw in all_context_text for cw in content_words)
            if not has_lexical_match:
                return False

        return True

    def format_fallback_response(self, query: str) -> str:
        """Generate an honest, standardized refusal for out-of-domain / ungrounded queries."""
        return f"""### Summary
I do not have enough information in the Confluence documentation or Jira records to answer this question.

- **Query**: *"{query}"*
- **Status**: No matching internal knowledge base articles or Jira issues met the confidence threshold.
- **Guidance**: Please verify your search terms or consult the relevant Confluence space (`ENG`) or Jira project (`PAY`)."""

    def verify_citations(
        self,
        answer: str,
        context: RetrievalContext,
    ) -> GuardrailResult:
        """Verify that all source document IDs cited in the answer exist in the retrieved context."""
        available_ids = {s["source_id"].upper() for s in context.sources}
        available_ids.update({c.source_id.upper() for c in context.chunks})

        # Match cited IDs e.g. ENG-PAGE-02, PAY-102
        cited_pattern = re.compile(r"\b(?:ENG-PAGE-\d+|PAY-\d+)\b", re.IGNORECASE)
        found_matches = cited_pattern.findall(answer)
        cited_ids = sorted(list(set(m.upper() for m in found_matches)))

        hallucinated = [cid for cid in cited_ids if cid not in available_ids]
        citations_valid = len(hallucinated) == 0

        max_score = max((c.score for c in context.chunks), default=0.0)
        is_grounded = bool(context.chunks) and citations_valid

        return GuardrailResult(
            is_grounded=is_grounded,
            citations_valid=citations_valid,
            confidence_score=max_score,
            cited_source_ids=cited_ids,
            available_source_ids=sorted(list(available_ids)),
            hallucinated_source_ids=hallucinated,
        )

    def append_source_links(
        self,
        answer: str,
        context: RetrievalContext,
    ) -> str:
        """Ensure full clickable source URLs and metadata are appended to the answer."""
        if not context.sources:
            return answer

        if "### Sources" in answer or "## Sources" in answer:
            return answer

        source_lines = ["\n\n### Sources & References"]
        for s in context.sources:
            url_str = f" - [View in {s['source_type'].capitalize()}]({s['url']})" if s.get("url") else ""
            source_lines.append(f"- **[{s['source_type'].upper()} {s['source_id']}]**: {s['title']}{url_str}")

        return answer + "\n".join(source_lines)
