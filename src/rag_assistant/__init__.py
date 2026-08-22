"""Confluence + Jira RAG assistant package."""

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
    "ConfluencePage",
    "JiraIssue",
    "BenchmarkQuery",
    "load_sample_confluence_pages",
    "load_sample_jira_issues",
    "load_benchmark_queries",
]
