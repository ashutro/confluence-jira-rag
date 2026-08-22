"""Hierarchical context-aware Markdown and text chunker for RAG."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from rag_assistant.core.models import Chunk, UnifiedDocument


@dataclass
class SectionNode:
    """Represents a section in a Markdown document."""

    level: int
    title: str
    content_lines: List[str]
    path: List[str]


class MarkdownChunker:
    """Hierarchical Markdown chunker that preserves header hierarchy and injects contextual breadcrumbs."""

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        min_chunk_size: int = 50,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_document(self, doc: UnifiedDocument) -> List[Chunk]:
        """Split a UnifiedDocument into structured, context-enriched Chunks."""
        sections = self._parse_markdown_sections(doc.text_content, doc_title=doc.title)
        chunks: List[Chunk] = []
        chunk_index = 0

        for section in sections:
            section_raw_text = "\n".join(section.content_lines).strip()
            if not section_raw_text:
                continue

            # Split section text if it exceeds target chunk_size
            sub_texts = self._split_text(section_raw_text)

            section_chunks: List[Chunk] = []
            for sub_text in sub_texts:
                clean_sub = sub_text.strip()
                if not clean_sub:
                    continue

                enriched_text = self._build_enriched_text(
                    doc=doc,
                    section_path=section.path,
                    raw_text=clean_sub,
                )

                chunk = Chunk(
                    chunk_id=f"{doc.doc_id}:chunk_{chunk_index}",
                    doc_id=doc.doc_id,
                    source_type=doc.source_type,
                    source_id=doc.source_id,
                    title=doc.title,
                    section_title=section.title,
                    section_path=section.path,
                    chunk_index=chunk_index,
                    text=enriched_text,
                    raw_text=clean_sub,
                    metadata={
                        **doc.metadata,
                        "url": doc.url,
                        "author": doc.author,
                        "tags": doc.tags,
                        "updated_at": doc.updated_at,
                    },
                )
                section_chunks.append(chunk)
                chunk_index += 1

            chunks.extend(section_chunks)

        return chunks

    def chunk_documents(self, documents: List[UnifiedDocument]) -> List[Chunk]:
        """Chunk a collection of UnifiedDocuments."""
        all_chunks: List[Chunk] = []
        for doc in documents:
            all_chunks.extend(self.chunk_document(doc))
        return all_chunks

    def _build_enriched_text(
        self,
        doc: UnifiedDocument,
        section_path: List[str],
        raw_text: str,
    ) -> str:
        """Construct chunk text prepended with document and section hierarchy breadcrumb."""
        path_str = " > ".join(section_path) if section_path else doc.title
        header = f"[Document: {doc.title} | Source: {doc.source_type.upper()} ({doc.source_id})]\n[Section: {path_str}]\n\n"
        return header + raw_text

    def _parse_markdown_sections(self, markdown_text: str, doc_title: str) -> List[SectionNode]:
        """Parse markdown into hierarchical section nodes."""
        lines = markdown_text.splitlines()
        sections: List[SectionNode] = []

        current_hierarchy: List[tuple[int, str]] = []  # [(level, title)]
        current_lines: List[str] = []
        current_title = "Overview"
        current_level = 1

        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        for line in lines:
            match = heading_pattern.match(line)
            if match:
                # Flush previous section
                if current_lines:
                    path = [t for _, t in current_hierarchy] or [doc_title]
                    sections.append(
                        SectionNode(
                            level=current_level,
                            title=current_title,
                            content_lines=list(current_lines),
                            path=path,
                        )
                    )
                    current_lines.clear()

                level = len(match.group(1))
                title = match.group(2).strip()

                # Update hierarchy stack
                while current_hierarchy and current_hierarchy[-1][0] >= level:
                    current_hierarchy.pop()
                current_hierarchy.append((level, title))

                current_level = level
                current_title = title
            else:
                current_lines.append(line)

        # Flush final section
        if current_lines:
            path = [t for _, t in current_hierarchy] or [doc_title]
            sections.append(
                SectionNode(
                    level=current_level,
                    title=current_title,
                    content_lines=list(current_lines),
                    path=path,
                )
            )

        return sections

    def _split_text(self, text: str) -> List[str]:
        """Split a block of text into chunks respecting paragraphs, code blocks, sentences, and overlap."""
        if len(text) <= self.chunk_size:
            return [text]

        # Break text into atomic blocks (paragraphs, tables, code blocks)
        blocks = self._extract_atomic_blocks(text)
        chunks: List[str] = []
        current_chunk_blocks: List[str] = []
        current_length = 0

        for block in blocks:
            block_len = len(block)
            if current_length + block_len <= self.chunk_size:
                current_chunk_blocks.append(block)
                current_length += block_len + 2  # account for \n\n
            else:
                if current_chunk_blocks:
                    chunks.append("\n\n".join(current_chunk_blocks).strip())
                    # Overlap: keep the last block if it fits within overlap limit
                    last_block = current_chunk_blocks[-1]
                    if len(last_block) <= self.chunk_overlap:
                        current_chunk_blocks = [last_block]
                        current_length = len(last_block)
                    else:
                        current_chunk_blocks = []
                        current_length = 0

                # Now process the current block
                if len(block) <= self.chunk_size:
                    current_chunk_blocks.append(block)
                    current_length += len(block) + 2
                else:
                    # Single large block (e.g. long paragraph or large table)
                    sub_slices = self._hard_split_block(block)
                    for slice_item in sub_slices[:-1]:
                        chunks.append(slice_item)
                    if sub_slices:
                        current_chunk_blocks = [sub_slices[-1]]
                        current_length = len(sub_slices[-1])

        if current_chunk_blocks:
            chunks.append("\n\n".join(current_chunk_blocks).strip())

        return [c for c in chunks if c.strip()]

    def _extract_atomic_blocks(self, text: str) -> List[str]:
        """Split text on paragraph boundaries while keeping fenced code blocks and tables together."""
        raw_paragraphs = re.split(r"\n\s*\n", text)
        merged_blocks: List[str] = []
        inside_code_block = False
        code_buffer: List[str] = []

        for p in raw_paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue

            backticks = p_strip.count("```")
            if inside_code_block:
                code_buffer.append(p_strip)
                if backticks % 2 == 1:
                    merged_blocks.append("\n\n".join(code_buffer))
                    code_buffer.clear()
                    inside_code_block = False
            else:
                if backticks % 2 == 1:
                    inside_code_block = True
                    code_buffer.append(p_strip)
                else:
                    merged_blocks.append(p_strip)

        if code_buffer:
            merged_blocks.append("\n\n".join(code_buffer))

        return merged_blocks

    def _hard_split_block(self, block: str) -> List[str]:
        """Split a long paragraph or block by sentences or words when it exceeds chunk_size."""
        # Split by sentences (lookbehind for . ! ? followed by space)
        sentences = re.split(r"(?<=[.!?])\s+", block)
        if len(sentences) <= 1:
            # Fallback to word splitting
            words = block.split()
            chunks: List[str] = []
            curr_words: List[str] = []
            curr_len = 0
            for w in words:
                if curr_len + len(w) + 1 <= self.chunk_size:
                    curr_words.append(w)
                    curr_len += len(w) + 1
                else:
                    if curr_words:
                        chunks.append(" ".join(curr_words))
                    curr_words = [w]
                    curr_len = len(w)
            if curr_words:
                chunks.append(" ".join(curr_words))
            return chunks

        chunks = []
        current: List[str] = []
        curr_len = 0

        for s in sentences:
            if curr_len + len(s) + 1 <= self.chunk_size:
                current.append(s)
                curr_len += len(s) + 1
            else:
                if current:
                    chunks.append(" ".join(current).strip())
                current = [s]
                curr_len = len(s)

        if current:
            chunks.append(" ".join(current).strip())

        return chunks or [block]

    @staticmethod
    def save_chunks_to_json(
        chunks: List[Chunk],
        output_path: Path | str,
    ) -> Path:
        """Save chunks list to structured JSON."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = [c.to_dict() for c in chunks]
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return target
