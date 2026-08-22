"""Unit tests for Jira Connector, ADF cleaner, and configuration."""

import json
from pathlib import Path

import pytest
import responses
from rag_assistant.config import Settings
from rag_assistant.connectors.adf_cleaner import clean_adf_to_markdown
from rag_assistant.connectors.jira import (
    JiraConnector,
    JiraDocument,
    MockJiraConnector,
)


# -----------------------------------------------------------------------------
# ADF Cleaner Tests
# -----------------------------------------------------------------------------

def test_clean_adf_headings_and_paragraphs():
    adf_doc = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": "Root Cause"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "The worker experienced "},
                    {
                        "type": "text",
                        "text": "out-of-memory",
                        "marks": [{"type": "strong"}],
                    },
                    {"type": "text", "text": " errors during "},
                    {"type": "text", "text": "high traffic", "marks": [{"type": "em"}]},
                    {"type": "text", "text": "."},
                ],
            },
        ],
    }

    md, plain = clean_adf_to_markdown(adf_doc)
    assert "## Root Cause" in md
    assert "**out-of-memory**" in md
    assert "*high traffic*" in md
    assert "Root Cause" in plain
    assert "out-of-memory" in plain


def test_clean_adf_code_blocks_and_lists():
    adf_doc = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "codeBlock",
                "attrs": {"language": "bash"},
                "content": [{"type": "text", "text": "kubectl get pods -n payments"}],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "First bullet"}],
                            }
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Link to docs",
                                        "marks": [
                                            {
                                                "type": "link",
                                                "attrs": {"href": "https://example.com"},
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
        ],
    }

    md, plain = clean_adf_to_markdown(adf_doc)
    assert "```bash" in md
    assert "kubectl get pods -n payments" in md
    assert "- First bullet" in md
    assert "- [Link to docs](https://example.com)" in md


def test_clean_adf_tables():
    adf_doc = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "table",
                "content": [
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableHeader",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "Service"}],
                                    }
                                ],
                            },
                            {
                                "type": "tableHeader",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "Status"}],
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "type": "tableRow",
                        "content": [
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "pay-webhook"}],
                                    }
                                ],
                            },
                            {
                                "type": "tableCell",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "Degraded"}],
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ],
    }

    md, plain = clean_adf_to_markdown(adf_doc)
    assert "| Service | Status |" in md
    assert "| --- | --- |" in md
    assert "| pay-webhook | Degraded |" in md


def test_clean_adf_string_fallback():
    plain_input = "This is a plain text description from Jira v2."
    md, plain = clean_adf_to_markdown(plain_input)
    assert md == plain_input
    assert plain == plain_input

    md_empty, plain_empty = clean_adf_to_markdown(None)
    assert md_empty == ""
    assert plain_empty == ""


# -----------------------------------------------------------------------------
# Configuration Settings Tests for Jira
# -----------------------------------------------------------------------------

def test_jira_settings_validation():
    s = Settings(
        confluence_base_url="https://test.atlassian.net/wiki",
        confluence_email="test@example.com",
        confluence_api_token="token",
        jira_base_url=None,
        jira_email=None,
        jira_api_token=None,
    )
    with pytest.raises(ValueError, match="Missing required Jira settings"):
        s.validate_jira()

    valid_s = Settings(
        confluence_base_url="https://test.atlassian.net/wiki",
        confluence_email="test@example.com",
        confluence_api_token="token",
        jira_base_url="https://test.atlassian.net",
        jira_email="test@example.com",
        jira_api_token="token-jira",
        jira_project_key="PAY",
    )
    valid_s.validate_jira()
    assert valid_s.jira_project_key == "PAY"


# -----------------------------------------------------------------------------
# Jira REST API Connector Tests (Mocked Responses)
# -----------------------------------------------------------------------------

@responses.activate
def test_jira_single_issue_fetch():
    base_url = "https://test.atlassian.net"
    connector = JiraConnector(
        base_url=base_url,
        email="test@example.com",
        api_token="token-123",
        project_key="PAY",
    )

    issue_data = {
        "id": "10050",
        "key": "PAY-101",
        "fields": {
            "project": {"key": "PAY", "name": "Core Payments"},
            "summary": "Next-Gen Webhook Reliability",
            "issuetype": {"name": "Epic"},
            "status": {"name": "In Progress"},
            "priority": {"name": "High"},
            "reporter": {"displayName": "Alex Morgan", "emailAddress": "alex@example.com"},
            "assignee": {"displayName": "David Kim", "emailAddress": "david@example.com"},
            "components": [{"name": "Webhook Dispatcher"}],
            "labels": ["epic", "q3-goals"],
            "created": "2026-07-15T10:00:00Z",
            "updated": "2026-08-19T14:20:00Z",
            "description": "Redesign merchant webhook delivery.",
            "comment": {
                "comments": [
                    {
                        "author": {"displayName": "Alex Morgan"},
                        "created": "2026-07-20T11:00:00Z",
                        "body": "Phase 1 architecture review approved.",
                    }
                ]
            },
            "issuelinks": [],
        },
    }

    responses.add(
        responses.GET,
        f"{base_url}/rest/api/3/issue/PAY-101",
        json=issue_data,
        status=200,
    )

    doc = connector.fetch_issue_by_key("PAY-101")
    assert doc.key == "PAY-101"
    assert doc.summary == "Next-Gen Webhook Reliability"
    assert doc.issue_type == "Epic"
    assert doc.status == "In Progress"
    assert doc.priority == "High"
    assert doc.reporter["display_name"] == "Alex Morgan"
    assert doc.assignee["display_name"] == "David Kim"
    assert "Webhook Dispatcher" in doc.components
    assert len(doc.comments) == 1
    assert doc.comments[0]["author"] == "Alex Morgan"


@responses.activate
def test_jira_search_and_pagination():
    base_url = "https://test.atlassian.net"
    connector = JiraConnector(
        base_url=base_url,
        email="test@example.com",
        api_token="token-123",
        project_key="PAY",
    )

    page1_response = {
        "startAt": 0,
        "maxResults": 1,
        "total": 2,
        "issues": [
            {
                "id": "10001",
                "key": "PAY-101",
                "fields": {
                    "project": {"key": "PAY", "name": "Core Payments"},
                    "summary": "Issue One",
                    "issuetype": {"name": "Bug"},
                    "status": {"name": "Closed"},
                    "priority": {"name": "Highest"},
                    "description": "Bug description 1",
                },
            }
        ],
    }

    page2_response = {
        "startAt": 1,
        "maxResults": 1,
        "total": 2,
        "issues": [
            {
                "id": "10002",
                "key": "PAY-102",
                "fields": {
                    "project": {"key": "PAY", "name": "Core Payments"},
                    "summary": "Issue Two",
                    "issuetype": {"name": "Story"},
                    "status": {"name": "In Progress"},
                    "priority": {"name": "Medium"},
                    "description": "Story description 2",
                },
            }
        ],
    }

    responses.add(
        responses.GET,
        f"{base_url}/rest/api/3/search",
        json=page1_response,
        status=200,
    )
    responses.add(
        responses.GET,
        f"{base_url}/rest/api/3/search",
        json=page2_response,
        status=200,
    )

    issues = connector.fetch_all_issues(project_key="PAY")
    assert len(issues) == 2
    assert issues[0].key == "PAY-101"
    assert issues[1].key == "PAY-102"


@responses.activate
def test_jira_rate_limiting_retry():
    base_url = "https://test.atlassian.net"
    connector = JiraConnector(
        base_url=base_url,
        email="test@example.com",
        api_token="token-123",
        max_retries=2,
    )

    responses.add(
        responses.GET,
        f"{base_url}/rest/api/3/issue/PAY-101",
        headers={"Retry-After": "0"},
        status=429,
    )
    responses.add(
        responses.GET,
        f"{base_url}/rest/api/3/issue/PAY-101",
        json={
            "id": "10050",
            "key": "PAY-101",
            "fields": {
                "summary": "Recovered Issue",
                "issuetype": {"name": "Task"},
                "status": {"name": "Open"},
                "priority": {"name": "Low"},
                "description": "Recovered description",
            },
        },
        status=200,
    )

    doc = connector.fetch_issue_by_key("PAY-101")
    assert doc.key == "PAY-101"
    assert doc.summary == "Recovered Issue"


@responses.activate
def test_jira_unauthorized_error():
    base_url = "https://test.atlassian.net"
    connector = JiraConnector(
        base_url=base_url,
        email="bad@example.com",
        api_token="wrong-token",
    )
    responses.add(
        responses.GET,
        f"{base_url}/rest/api/3/issue/PAY-101",
        status=401,
    )

    with pytest.raises(PermissionError, match="Jira authentication failed"):
        connector.fetch_issue_by_key("PAY-101")


# -----------------------------------------------------------------------------
# Mock Jira Connector Tests
# -----------------------------------------------------------------------------

def test_mock_jira_connector(tmp_path: Path):
    mock_connector = MockJiraConnector()
    issues = mock_connector.fetch_all_issues(project_key="PAY")
    assert len(issues) == 8

    # Verify first issue
    doc_1 = issues[0]
    assert doc_1.key == "PAY-101"
    assert doc_1.issue_type == "Epic"
    assert doc_1.priority == "High"
    assert "Webhook Dispatcher" in doc_1.components
    assert len(doc_1.linked_confluence_pages) == 2

    # Fetch single issue
    single_issue = mock_connector.fetch_issue_by_key("PAY-106")
    assert single_issue.key == "PAY-106"
    assert single_issue.issue_type == "Incident"
    assert "Postmortem" in single_issue.summary

    # Test saving to JSON
    output_file = tmp_path / "jira_output.json"
    saved_path = mock_connector.save_issues_to_json(issues, output_file)
    assert saved_path.exists()

    with open(saved_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 8
    assert data[0]["key"] == "PAY-101"
