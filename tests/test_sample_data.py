"""Unit tests for Milestone 2 sample dataset and loader utilities."""

from pathlib import Path

import pytest
from rag_assistant.sample_data import (
    get_project_root,
    get_sample_data_dir,
    load_benchmark_queries,
    load_sample_confluence_pages,
    load_sample_jira_issues,
)


def test_project_root_and_paths():
    root = get_project_root()
    assert (root / "pyproject.toml").exists()
    sample_dir = get_sample_data_dir()
    assert sample_dir.exists()
    assert (sample_dir / "confluence" / "pages.json").exists()
    assert (sample_dir / "jira" / "issues.json").exists()
    assert (sample_dir / "queries.json").exists()


def test_confluence_pages_loading():
    pages = load_sample_confluence_pages()
    assert len(pages) == 5

    page_ids = {p.id for p in pages}
    expected_ids = {
        "ENG-PAGE-01",
        "ENG-PAGE-02",
        "ENG-PAGE-03",
        "ENG-PAGE-04",
        "ENG-PAGE-05",
    }
    assert page_ids == expected_ids

    root = get_project_root()
    for page in pages:
        assert page.space_key == "ENG"
        assert len(page.title) > 0
        assert len(page.labels) > 0
        assert page.version >= 1
        assert len(page.body_markdown) > 50

        # Verify underlying markdown file exists on disk
        md_file = root / page.file_path
        assert md_file.exists(), f"Markdown file {page.file_path} not found"
        content = md_file.read_text(encoding="utf-8")
        assert len(content) > 50


def test_jira_issues_loading():
    issues = load_sample_jira_issues()
    assert len(issues) == 8

    issue_keys = {issue.key for issue in issues}
    expected_keys = {
        "PAY-101",
        "PAY-102",
        "PAY-103",
        "PAY-104",
        "PAY-105",
        "PAY-106",
        "PAY-107",
        "PAY-108",
    }
    assert issue_keys == expected_keys

    valid_statuses = {"Open", "To Do", "In Progress", "In Review", "Done", "Closed"}
    valid_priorities = {"Highest", "High", "Medium", "Low"}
    valid_types = {"Epic", "Bug", "Story", "Task", "Incident"}

    for issue in issues:
        assert issue.project_key == "PAY"
        assert issue.issue_type in valid_types
        assert issue.status in valid_statuses
        assert issue.priority in valid_priorities
        assert "name" in issue.reporter
        assert len(issue.components) > 0
        assert len(issue.description) > 30


def test_cross_reference_integrity():
    pages = load_sample_confluence_pages()
    issues = load_sample_jira_issues()

    page_id_map = {p.id: p for p in pages}
    issue_key_map = {i.key: i for i in issues}

    # Verify all linked confluence pages in Jira issues exist
    for issue in issues:
        for linked_page in issue.linked_confluence_pages:
            assert linked_page["id"] in page_id_map, (
                f"Issue {issue.key} links to unknown Confluence page {linked_page['id']}"
            )

        for linked_issue in issue.linked_issues:
            assert linked_issue["key"] in issue_key_map, (
                f"Issue {issue.key} links to unknown Jira issue {linked_issue['key']}"
            )


def test_benchmark_queries_loading():
    queries = load_benchmark_queries()
    assert len(queries) >= 5

    pages = load_sample_confluence_pages()
    issues = load_sample_jira_issues()
    valid_source_ids = {p.id for p in pages} | {i.key for i in issues}

    for query in queries:
        assert len(query.question) > 10
        assert len(query.target_sources) > 0
        assert len(query.expected_answer_keywords) > 0
        for src in query.target_sources:
            assert src in valid_source_ids, (
                f"Query {query.id} references invalid source ID {src}"
            )
