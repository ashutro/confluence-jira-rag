"""Confluence + Jira RAG assistant package."""

from rag_assistant.config import Settings, get_project_root
from rag_assistant.connectors.confluence import (
    ConfluenceConnector,
    ConfluenceDocument,
    MockConfluenceConnector,
)
from rag_assistant.connectors.html_cleaner import clean_confluence_html
from rag_assistant.sample_data import (
    BenchmarkQuery,
    ConfluencePage,
    JiraIssue,
    load_benchmark_queries,
    load_sample_confluence_pages,
    load_sample_jira_issues,
)

__version__ = "0.1.0"
__all__ = [
    "Settings",
    "get_project_root",
    "ConfluenceConnector",
    "ConfluenceDocument",
    "MockConfluenceConnector",
    "clean_confluence_html",
    "ConfluencePage",
    "JiraIssue",
    "BenchmarkQuery",
    "load_sample_confluence_pages",
    "load_sample_jira_issues",
    "load_benchmark_queries",
]
