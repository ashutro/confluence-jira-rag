"""Unit tests for Confluence Connector, HTML cleaner, and configuration."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import responses
from rag_assistant.config import Settings
from rag_assistant.connectors.confluence import (
    ConfluenceConnector,
    ConfluenceDocument,
    MockConfluenceConnector,
)
from rag_assistant.connectors.html_cleaner import clean_confluence_html


# -----------------------------------------------------------------------------
# HTML Cleaner Tests
# -----------------------------------------------------------------------------

def test_clean_confluence_html_headings_and_paragraphs():
    html = """
    <h1>Main Title</h1>
    <p>This is the first paragraph with <strong>bold</strong> and <em>italic</em> text.</p>
    <h2>Subheading</h2>
    <p>Second paragraph with inline <code>variable_name</code>.</p>
    """
    md, plain = clean_confluence_html(html)
    assert "# Main Title" in md
    assert "## Subheading" in md
    assert "**bold**" in md
    assert "*italic*" in md
    assert "`variable_name`" in md
    assert "Main Title" in plain
    assert "bold" in plain


def test_clean_confluence_html_code_macros():
    html = """
    <p>Here is a code block:</p>
    <ac:structured-macro ac:name="code">
        <ac:parameter ac:name="language">python</ac:parameter>
        <ac:plain-text-body><![CDATA[def hello():\n    print("world")]]></ac:plain-text-body>
    </ac:structured-macro>
    """
    md, plain = clean_confluence_html(html)
    assert "```python" in md
    assert 'def hello():\n    print("world")' in md
    assert "```" in md
    assert "def hello():" in plain


def test_clean_confluence_html_tables():
    html = """
    <table>
        <tr><th>Metric</th><th>Threshold</th></tr>
        <tr><td>Latency</td><td>100ms</td></tr>
        <tr><td>Availability</td><td>99.99%</td></tr>
    </table>
    """
    md, plain = clean_confluence_html(html)
    assert "| Metric | Threshold |" in md
    assert "| --- | --- |" in md
    assert "| Latency | 100ms |" in md
    assert "Latency" in plain
    assert "100ms" in plain


def test_clean_confluence_html_lists_and_links():
    html = """
    <ul>
        <li>First item with <a href="https://example.com/docs">Documentation Link</a></li>
        <li>Second item</li>
    </ul>
    <ol>
        <li>Step one</li>
        <li>Step two</li>
    </ol>
    """
    md, plain = clean_confluence_html(html)
    assert "- First item with [Documentation Link](https://example.com/docs)" in md
    assert "- Second item" in md
    assert "1. Step one" in md
    assert "2. Step two" in md


def test_clean_confluence_html_empty_input():
    md, plain = clean_confluence_html("")
    assert md == ""
    assert plain == ""


# -----------------------------------------------------------------------------
# Configuration Settings Tests
# -----------------------------------------------------------------------------

def test_settings_validation():
    s = Settings(
        confluence_base_url="",
        confluence_email="",
        confluence_api_token="",
    )
    with pytest.raises(ValueError, match="Missing required Confluence settings"):
        s.validate_confluence()

    valid_settings = Settings(
        confluence_base_url="https://test.atlassian.net/wiki",
        confluence_email="test@example.com",
        confluence_api_token="dummy-token",
        confluence_space_key="ENG",
    )
    valid_settings.validate_confluence()
    assert valid_settings.confluence_space_key == "ENG"


# -----------------------------------------------------------------------------
# Confluence REST API Connector Tests (Mocked HTTP Responses)
# -----------------------------------------------------------------------------

@responses.activate
def test_fetch_space_id():
    base_url = "https://test.atlassian.net/wiki"
    connector = ConfluenceConnector(
        base_url=base_url,
        email="test@example.com",
        api_token="token-123",
        space_key="ENG",
    )

    responses.add(
        responses.GET,
        f"{base_url}/api/v2/spaces?keys=ENG&limit=1",
        json={"results": [{"id": "98765", "key": "ENG", "name": "Engineering"}]},
        status=200,
    )

    space_id = connector.get_space_id_by_key("ENG")
    assert space_id == "98765"


@responses.activate
def test_fetch_all_pages_with_pagination():
    base_url = "https://test.atlassian.net/wiki"
    connector = ConfluenceConnector(
        base_url=base_url,
        email="test@example.com",
        api_token="token-123",
    )

    # Mock Page 1 response
    page_1_data = {
        "results": [
            {
                "id": "1001",
                "title": "Page One",
                "spaceId": "501",
                "version": {"number": 2, "createdAt": "2026-08-01T10:00:00Z", "authorId": "user1"},
                "createdAt": "2026-07-01T10:00:00Z",
                "_links": {"webui": "/spaces/ENG/pages/1001"},
                "body": {
                    "storage": {
                        "value": "<h1>Welcome</h1><p>This is page one content.</p>"
                    }
                },
            }
        ],
        "_links": {
            "next": "/api/v2/pages?cursor=cursor_token_xyz&limit=25"
        },
    }

    # Mock Page 2 response
    page_2_data = {
        "results": [
            {
                "id": "1002",
                "title": "Page Two",
                "spaceId": "501",
                "version": {"number": 1, "createdAt": "2026-08-05T12:00:00Z", "authorId": "user2"},
                "createdAt": "2026-08-05T12:00:00Z",
                "_links": {"webui": "/spaces/ENG/pages/1002"},
                "body": {
                    "storage": {
                        "value": "<p>This is page two content.</p>"
                    }
                },
            }
        ],
        "_links": {},
    }

    # Mock Labels
    responses.add(
        responses.GET,
        f"{base_url}/api/v2/pages/1001/labels",
        json={"results": [{"name": "architecture"}, {"name": "core"}]},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{base_url}/api/v2/pages/1002/labels",
        json={"results": [{"name": "runbook"}]},
        status=200,
    )

    # Mock GET /api/v2/pages (initial call)
    responses.add(
        responses.GET,
        f"{base_url}/api/v2/pages",
        json=page_1_data,
        status=200,
    )

    # Mock GET /api/v2/pages with cursor
    responses.add(
        responses.GET,
        f"{base_url}/api/v2/pages",
        json=page_2_data,
        status=200,
    )

    docs = connector.fetch_all_pages()
    assert len(docs) == 2
    assert docs[0].id == "1001"
    assert docs[0].title == "Page One"
    assert docs[0].version == 2
    assert "architecture" in docs[0].labels
    assert "# Welcome" in docs[0].body_markdown
    assert docs[1].id == "1002"
    assert docs[1].title == "Page Two"
    assert "runbook" in docs[1].labels


@responses.activate
def test_rate_limiting_retry():
    base_url = "https://test.atlassian.net/wiki"
    connector = ConfluenceConnector(
        base_url=base_url,
        email="test@example.com",
        api_token="token-123",
        max_retries=2,
    )

    # First call returns 429, second call succeeds
    responses.add(
        responses.GET,
        f"{base_url}/api/v2/pages/1001?body-format=storage",
        headers={"Retry-After": "0"},
        status=429,
    )
    responses.add(
        responses.GET,
        f"{base_url}/api/v2/pages/1001?body-format=storage",
        json={
            "id": "1001",
            "title": "Retried Page",
            "body": {"storage": {"value": "<p>Content after retry</p>"}},
        },
        status=200,
    )
    responses.add(
        responses.GET,
        f"{base_url}/api/v2/pages/1001/labels",
        json={"results": []},
        status=200,
    )

    doc = connector.fetch_page_by_id("1001")
    assert doc.id == "1001"
    assert doc.title == "Retried Page"


@responses.activate
def test_unauthorized_error():
    base_url = "https://test.atlassian.net/wiki"
    connector = ConfluenceConnector(
        base_url=base_url,
        email="invalid@example.com",
        api_token="bad-token",
    )
    responses.add(
        responses.GET,
        f"{base_url}/api/v2/pages/1001?body-format=storage",
        status=401,
    )

    with pytest.raises(PermissionError, match="Confluence authentication failed"):
        connector.fetch_page_by_id("1001")


# -----------------------------------------------------------------------------
# Mock Connector & JSON Output Tests
# -----------------------------------------------------------------------------

def test_mock_confluence_connector(tmp_path: Path):
    mock_connector = MockConfluenceConnector()
    docs = mock_connector.fetch_all_pages(space_key="ENG")
    assert len(docs) == 5

    # Check first doc
    doc_1 = docs[0]
    assert doc_1.id == "ENG-PAGE-01"
    assert doc_1.space_key == "ENG"
    assert "architecture" in doc_1.labels
    assert len(doc_1.body_markdown) > 50

    # Test single page fetch
    single_doc = mock_connector.fetch_page_by_id("ENG-PAGE-02")
    assert single_doc.id == "ENG-PAGE-02"
    assert "Incident Response" in single_doc.title

    # Test save to JSON
    output_file = tmp_path / "confluence_output.json"
    saved_path = mock_connector.save_pages_to_json(docs, output_file)
    assert saved_path.exists()

    with open(saved_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 5
    assert data[0]["id"] == "ENG-PAGE-01"
    assert data[0]["title"] == "Architecture Overview & Service Topology"
