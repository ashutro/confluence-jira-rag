"""Core data models for Unified Documents and Text Chunks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

SourceType = Literal["confluence", "jira", "other"]


@dataclass
class UnifiedDocument:
    """Standardized document format bridging Confluence pages and Jira tickets."""

    doc_id: str  # e.g., "confluence:ENG-PAGE-01" or "jira:PAY-101"
    source_type: SourceType  # "confluence" or "jira"
    source_id: str  # e.g., "ENG-PAGE-01" or "PAY-101"
    title: str  # Page title or Jira ticket summary
    url: str  # Web link
    author: str  # Author / Reporter name or email
    created_at: str  # ISO timestamp
    updated_at: str  # ISO timestamp
    tags: List[str]  # Combined labels, components, tags
    metadata: Dict[str, Any]  # Source-specific metadata
    text_content: str  # Full cleaned markdown / plain text representation

    def to_dict(self) -> Dict[str, Any]:
        """Convert document to JSON dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UnifiedDocument:
        """Create document from dictionary."""
        return cls(
            doc_id=data["doc_id"],
            source_type=data["source_type"],
            source_id=data["source_id"],
            title=data["title"],
            url=data.get("url", ""),
            author=data.get("author", "unknown"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            text_content=data.get("text_content", ""),
        )


@dataclass
class Chunk:
    """Standard chunk representation ready for vector embedding and retrieval."""

    chunk_id: str  # e.g., "confluence:ENG-PAGE-01:chunk_0"
    doc_id: str  # Parent UnifiedDocument doc_id
    source_type: SourceType
    source_id: str  # e.g., "ENG-PAGE-01" or "PAY-101"
    title: str  # Parent document title
    section_title: str  # Immediate section heading
    section_path: List[str]  # Breadcrumb of parent headings
    chunk_index: int  # Sequence index in document
    text: str  # Enriched chunk text with context breadcrumb
    raw_text: str  # Raw body text without breadcrumb header
    char_count: int = field(init=False)
    word_count: int = field(init=False)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)
        self.word_count = len(self.text.split())

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to JSON dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Chunk:
        """Create chunk from dictionary."""
        chunk = cls(
            chunk_id=data["chunk_id"],
            doc_id=data["doc_id"],
            source_type=data["source_type"],
            source_id=data["source_id"],
            title=data["title"],
            section_title=data.get("section_title", ""),
            section_path=data.get("section_path", []),
            chunk_index=int(data.get("chunk_index", 0)),
            text=data["text"],
            raw_text=data.get("raw_text", data["text"]),
            metadata=data.get("metadata", {}),
        )
        return chunk
