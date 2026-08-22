"""Utilities for loading and inspecting sample Confluence and Jira datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_project_root() -> Path:
    """Return the absolute path to the confluence-jira-rag root directory."""
    return Path(__file__).resolve().parent.parent.parent


def get_sample_data_dir() -> Path:
    """Return the path to the data/sample directory."""
    return get_project_root() / "data" / "sample"


@dataclass
class ConfluencePage:
    """Represents a sample Confluence page."""

    id: str
    title: str
    space_key: str
    space_name: str
    url: str
    author: str
    author_name: str
    version: int
    last_updated: str
    labels: List[str]
    summary: str
    file_path: str
    body_markdown: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConfluencePage:
        return cls(
            id=data["id"],
            title=data["title"],
            space_key=data["space_key"],
            space_name=data["space_name"],
            url=data["url"],
            author=data["author"],
            author_name=data["author_name"],
            version=data["version"],
            last_updated=data["last_updated"],
            labels=data.get("labels", []),
            summary=data.get("summary", ""),
            file_path=data.get("file_path", ""),
            body_markdown=data.get("body_markdown", ""),
        )


@dataclass
class JiraIssue:
    """Represents a sample Jira issue."""

    id: str
    key: str
    project_key: str
    project_name: str
    issue_type: str
    summary: str
    description: str
    status: str
    priority: str
    reporter: Dict[str, str]
    assignee: Optional[Dict[str, str]]
    components: List[str]
    labels: List[str]
    created_at: str
    updated_at: str
    resolved_at: Optional[str]
    resolution: Optional[str]
    linked_confluence_pages: List[Dict[str, str]] = field(default_factory=list)
    linked_issues: List[Dict[str, str]] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JiraIssue:
        return cls(
            id=data["id"],
            key=data["key"],
            project_key=data["project_key"],
            project_name=data["project_name"],
            issue_type=data["issue_type"],
            summary=data["summary"],
            description=data["description"],
            status=data["status"],
            priority=data["priority"],
            reporter=data.get("reporter", {}),
            assignee=data.get("assignee"),
            components=data.get("components", []),
            labels=data.get("labels", []),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            resolved_at=data.get("resolved_at"),
            resolution=data.get("resolution"),
            linked_confluence_pages=data.get("linked_confluence_pages", []),
            linked_issues=data.get("linked_issues", []),
            comments=data.get("comments", []),
        )


@dataclass
class BenchmarkQuery:
    """Represents an evaluation test query for the RAG assistant."""

    id: str
    question: str
    target_sources: List[str]
    expected_answer_keywords: List[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BenchmarkQuery:
        return cls(
            id=data["id"],
            question=data["question"],
            target_sources=data.get("target_sources", []),
            expected_answer_keywords=data.get("expected_answer_keywords", []),
        )


def load_sample_confluence_pages(sample_dir: Optional[Path] = None) -> List[ConfluencePage]:
    """Load all sample Confluence pages from data/sample/confluence/pages.json."""
    base_dir = sample_dir or get_sample_data_dir()
    pages_json_path = base_dir / "confluence" / "pages.json"
    if not pages_json_path.exists():
        raise FileNotFoundError(f"Confluence pages sample file not found: {pages_json_path}")

    with open(pages_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [ConfluencePage.from_dict(item) for item in data]


def load_sample_jira_issues(sample_dir: Optional[Path] = None) -> List[JiraIssue]:
    """Load all sample Jira issues from data/sample/jira/issues.json."""
    base_dir = sample_dir or get_sample_data_dir()
    issues_json_path = base_dir / "jira" / "issues.json"
    if not issues_json_path.exists():
        raise FileNotFoundError(f"Jira issues sample file not found: {issues_json_path}")

    with open(issues_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [JiraIssue.from_dict(item) for item in data]


def load_benchmark_queries(sample_dir: Optional[Path] = None) -> List[BenchmarkQuery]:
    """Load benchmark test questions from data/sample/queries.json."""
    base_dir = sample_dir or get_sample_data_dir()
    queries_json_path = base_dir / "queries.json"
    if not queries_json_path.exists():
        raise FileNotFoundError(f"Benchmark queries file not found: {queries_json_path}")

    with open(queries_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [BenchmarkQuery.from_dict(item) for item in data]
