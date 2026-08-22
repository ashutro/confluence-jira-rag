"""Unit tests for Document Normalizer and Hierarchical Markdown Chunker."""

import json
from pathlib import Path

import pytest
from rag_assistant.connectors.confluence import ConfluenceDocument
from rag_assistant.connectors.jira import JiraDocument
from rag_assistant.core.models import Chunk, UnifiedDocument
from rag_assistant.processing.chunker import MarkdownChunker
from rag_assistant.processing.normalizer import (
    DocumentNormalizer,
    normalize_confluence_page,
    normalize_jira_issue,
)
from rag_assistant.sample_data import (
    load_sample_confluence_pages,
    load_sample_jira_issues,
)


# -----------------------------------------------------------------------------
# Normalizer Tests
# -----------------------------------------------------------------------------

def test_normalize_confluence_page():
    conf_doc = ConfluenceDocument(
        id="ENG-PAGE-01",
        title="Architecture Overview",
        space_key="ENG",
        space_id="101",
        url="https://example.atlassian.net/wiki/spaces/ENG/pages/101",
        version=4,
        author="alex@example.com",
        created_at="2026-08-01T10:00:00Z",
        last_updated="2026-08-15T10:00:00Z",
        labels=["architecture", "redis"],
        body_storage="<p>Storage</p>",
        body_markdown="## 1. Overview\n\nPlatform architecture details.",
        body_text="Overview Platform architecture details.",
        summary="Summary of architecture",
        metadata={"status": "current"},
    )

    norm = normalize_confluence_page(conf_doc)
    assert norm.doc_id == "confluence:ENG-PAGE-01"
    assert norm.source_type == "confluence"
    assert norm.source_id == "ENG-PAGE-01"
    assert norm.title == "Architecture Overview"
    assert norm.author == "alex@example.com"
    assert "confluence" in norm.tags
    assert "eng" in norm.tags
    assert "architecture" in norm.tags
    assert "## 1. Overview" in norm.text_content
    assert norm.metadata["space_key"] == "ENG"


def test_normalize_jira_issue():
    jira_doc = JiraDocument(
        id="10050",
        key="PAY-102",
        project_key="PAY",
        project_name="Core Payments",
        issue_type="Bug",
        summary="Worker OOM Crash",
        description_markdown="Worker crashed during billing run.",
        description_text="Worker crashed during billing run.",
        status="Closed",
        priority="Highest",
        reporter={"name": "sam@example.com", "display_name": "Sam Patel"},
        assignee={"name": "david@example.com", "display_name": "David Kim"},
        components=["Webhook Dispatcher"],
        labels=["bug", "oom"],
        created_at="2026-08-01T10:00:00Z",
        updated_at="2026-08-05T10:00:00Z",
        resolved_at="2026-08-05T10:00:00Z",
        resolution="Fixed",
        url="https://example.atlassian.net/browse/PAY-102",
        comments=[
            {
                "author": "David Kim",
                "created_at": "2026-08-05T09:00:00Z",
                "body_markdown": "Fixed memory buffer leak.",
                "body_text": "Fixed memory buffer leak.",
            }
        ],
        linked_issues=[{"relationship": "part of", "key": "PAY-101", "summary": "Epic", "status": "In Progress"}],
        linked_confluence_pages=[{"id": "ENG-PAGE-02", "title": "Runbook"}],
    )

    norm = normalize_jira_issue(jira_doc)
    assert norm.doc_id == "jira:PAY-102"
    assert norm.source_type == "jira"
    assert norm.source_id == "PAY-102"
    assert norm.title == "[PAY-102] Worker OOM Crash"
    assert norm.author == "Sam Patel"
    assert "jira" in norm.tags
    assert "pay" in norm.tags
    assert "bug" in norm.tags
    assert "webhook dispatcher" in norm.tags
    assert "## Description" in norm.text_content
    assert "## Comments" in norm.text_content
    assert "Fixed memory buffer leak." in norm.text_content
    assert "## Relationships & Linked Documents" in norm.text_content


def test_document_normalizer_batch(tmp_path: Path):
    sample_conf = load_sample_confluence_pages()
    sample_jira = load_sample_jira_issues()

    conf_dicts = [p.__dict__ for p in sample_conf]
    jira_dicts = [i.__dict__ for i in sample_jira]

    normalized = DocumentNormalizer.normalize_all(conf_dicts, jira_dicts)
    assert len(normalized) == len(sample_conf) + len(sample_jira)

    out_file = tmp_path / "normalized.json"
    saved = DocumentNormalizer.save_documents_to_json(normalized, out_file)
    assert saved.exists()

    with open(saved, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 13


# -----------------------------------------------------------------------------
# Markdown Chunker Tests
# -----------------------------------------------------------------------------

def test_markdown_chunker_basic():
    doc = UnifiedDocument(
        doc_id="confluence:TEST-01",
        source_type="confluence",
        source_id="TEST-01",
        title="Test Document",
        url="https://example.com",
        author="Tester",
        created_at="2026-08-01",
        updated_at="2026-08-01",
        tags=["test"],
        metadata={"space": "TEST"},
        text_content="""# Test Document

## 1. Introduction
This is the introduction section explaining the basics.

## 2. Deep Dive
Here is detailed content about algorithms and architecture.

### 2.1 Microservices
Microservices talk over gRPC and Kafka.
""",
    )

    chunker = MarkdownChunker(chunk_size=500, chunk_overlap=50)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) >= 3
    for chunk in chunks:
        assert chunk.doc_id == "confluence:TEST-01"
        assert chunk.title == "Test Document"
        assert len(chunk.section_path) > 0
        assert "[Document: Test Document" in chunk.text
        assert "[Section:" in chunk.text
        assert chunk.char_count == len(chunk.text)
        assert chunk.word_count > 0


def test_markdown_chunker_large_section_split():
    long_paragraph = "This is a sentence describing a component. " * 30  # ~1300 chars
    doc = UnifiedDocument(
        doc_id="jira:PAY-101",
        source_type="jira",
        source_id="PAY-101",
        title="[PAY-101] Epic",
        url="https://example.com/PAY-101",
        author="Alex",
        created_at="2026-08-01",
        updated_at="2026-08-01",
        tags=["epic"],
        metadata={"priority": "High"},
        text_content=f"""# [PAY-101] Epic

## Description
{long_paragraph}
""",
    )

    chunker = MarkdownChunker(chunk_size=400, chunk_overlap=50)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) >= 3
    # Check that chunk indexes are sequential
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert c.source_type == "jira"
        assert c.source_id == "PAY-101"


def test_markdown_chunker_code_block_preservation():
    code_block = """```python
def process_payment(amount: float, currency: str) -> bool:
    if amount <= 0:
        raise ValueError("Invalid amount")
    return True
```"""
    doc = UnifiedDocument(
        doc_id="confluence:PAGE-CODE",
        source_type="confluence",
        source_id="PAGE-CODE",
        title="Payment Code Example",
        url="https://example.com",
        author="Dev",
        created_at="2026-08-01",
        updated_at="2026-08-01",
        tags=["code"],
        metadata={},
        text_content=f"""# Payment Code Example

## 1. Python Snippet
Here is how to process payments:

{code_block}
""",
    )

    chunker = MarkdownChunker(chunk_size=800, chunk_overlap=100)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 1
    assert "def process_payment" in chunks[0].text
    assert "```python" in chunks[0].text
