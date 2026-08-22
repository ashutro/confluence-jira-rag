"""Command Line Interface for Confluence + Jira RAG Assistant."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rag_assistant.config import Settings
from rag_assistant.connectors.confluence import (
    ConfluenceConnector,
    MockConfluenceConnector,
)
from rag_assistant.connectors.jira import (
    JiraConnector,
    MockJiraConnector,
)
from rag_assistant.core.models import UnifiedDocument
from rag_assistant.processing.chunker import MarkdownChunker
from rag_assistant.processing.normalizer import DocumentNormalizer


def fetch_confluence_command(args: argparse.Namespace) -> int:
    """Execute Confluence fetch and JSON export."""
    output_path = Path(args.output)
    space_key = args.space

    print("=" * 60)
    print("Confluence Data Retrieval Pipeline (Milestone 3)")
    print("=" * 60)

    if args.mock:
        print("Mode: Offline Mock Connector")
        connector = MockConfluenceConnector()
    else:
        try:
            settings = Settings.from_env()
            settings.validate_confluence()
            print(f"Mode: Live Confluence API ({settings.confluence_base_url})")
            connector = ConfluenceConnector.from_settings(settings)
        except ValueError as e:
            print(f"\n[Error] {e}")
            print("\nTip: Run with `--mock` to test using local sample datasets without credentials.")
            return 1

    print(f"Target Space: {space_key or 'All configured spaces'}")
    print(f"Output Destination: {output_path}")
    print("\nRetrieving Confluence pages...")

    try:
        pages = connector.fetch_all_pages(space_key=space_key)
        print(f"Successfully retrieved {len(pages)} page(s).\n")

        for idx, page in enumerate(pages, start=1):
            print(f"  {idx}. [{page.id}] {page.title}")
            print(f"     Space: {page.space_key} | Version: {page.version} | Labels: {page.labels}")

        connector.save_pages_to_json(pages, output_path)
        print(f"\nExported structured JSON to: {output_path.resolve()}")
        return 0

    except Exception as err:
        print(f"\n[Error] Retrieval failed: {err}", file=sys.stderr)
        return 1


def fetch_jira_command(args: argparse.Namespace) -> int:
    """Execute Jira issue search/fetch and JSON export."""
    output_path = Path(args.output)
    project_key = args.project
    jql = args.jql

    print("=" * 60)
    print("Jira Data Retrieval Pipeline (Milestone 4)")
    print("=" * 60)

    if args.mock:
        print("Mode: Offline Mock Connector")
        connector = MockJiraConnector()
    else:
        try:
            settings = Settings.from_env()
            settings.validate_jira()
            print(f"Mode: Live Jira API ({settings.jira_base_url})")
            connector = JiraConnector.from_settings(settings)
        except ValueError as e:
            print(f"\n[Error] {e}")
            print("\nTip: Run with `--mock` to test using local sample datasets without credentials.")
            return 1

    print(f"Target Project: {project_key or 'Default from config'}")
    if jql:
        print(f"Custom JQL: {jql}")
    print(f"Output Destination: {output_path}")
    print("\nRetrieving Jira issues...")

    try:
        issues = connector.fetch_all_issues(project_key=project_key, jql=jql)
        print(f"Successfully retrieved {len(issues)} issue(s).\n")

        for idx, issue in enumerate(issues, start=1):
            print(f"  {idx}. [{issue.key}] ({issue.issue_type} - {issue.priority}) {issue.summary}")
            print(f"     Status: {issue.status} | Components: {issue.components} | Labels: {issue.labels}")

        connector.save_issues_to_json(issues, output_path)
        print(f"\nExported structured JSON to: {output_path.resolve()}")
        return 0

    except Exception as err:
        print(f"\n[Error] Retrieval failed: {err}", file=sys.stderr)
        return 1


def normalize_and_chunk_command(args: argparse.Namespace) -> int:
    """Execute Document Normalization and Hierarchical Chunking pipeline."""
    conf_in = Path(args.input_confluence)
    jira_in = Path(args.input_jira)
    chunks_out = Path(args.output_chunks)
    docs_out = Path(args.output_docs)
    chunk_size = args.chunk_size
    chunk_overlap = args.chunk_overlap

    print("=" * 60)
    print("Data Normalization & Chunking Pipeline (Milestone 5)")
    print("=" * 60)

    # 1. Load or Mock Raw Confluence Pages
    confluence_raw = []
    if conf_in.exists():
        with open(conf_in, "r", encoding="utf-8") as f:
            confluence_raw = json.load(f)
        print(f"Loaded {len(confluence_raw)} Confluence page(s) from {conf_in}")
    elif args.mock:
        print(f"Confluence raw file '{conf_in}' not found. Auto-generating via Mock connector...")
        mock_conf = MockConfluenceConnector()
        pages = mock_conf.fetch_all_pages()
        mock_conf.save_pages_to_json(pages, conf_in)
        confluence_raw = [p.to_dict() for p in pages]
    else:
        print(f"[Error] Confluence input file '{conf_in}' not found. Run `fetch-confluence` first or pass `--mock`.", file=sys.stderr)
        return 1

    # 2. Load or Mock Raw Jira Issues
    jira_raw = []
    if jira_in.exists():
        with open(jira_in, "r", encoding="utf-8") as f:
            jira_raw = json.load(f)
        print(f"Loaded {len(jira_raw)} Jira issue(s) from {jira_in}")
    elif args.mock:
        print(f"Jira raw file '{jira_in}' not found. Auto-generating via Mock connector...")
        mock_jira = MockJiraConnector()
        issues = mock_jira.fetch_all_issues()
        mock_jira.save_issues_to_json(issues, jira_in)
        jira_raw = [i.to_dict() for i in issues]
    else:
        print(f"[Error] Jira input file '{jira_in}' not found. Run `fetch-jira` first or pass `--mock`.", file=sys.stderr)
        return 1

    # 3. Normalize into UnifiedDocuments
    print("\nNormalizing records into Unified Documents...")
    normalized_docs = DocumentNormalizer.normalize_all(confluence_raw, jira_raw)
    DocumentNormalizer.save_documents_to_json(normalized_docs, docs_out)
    print(f"Saved {len(normalized_docs)} UnifiedDocument(s) to: {docs_out.resolve()}")

    # 4. Chunk with Hierarchical Markdown Chunker
    print(f"\nChunking documents (size={chunk_size}, overlap={chunk_overlap})...")
    chunker = MarkdownChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = chunker.chunk_documents(normalized_docs)
    MarkdownChunker.save_chunks_to_json(chunks, chunks_out)
    print(f"Generated {len(chunks)} Chunk(s) saved to: {chunks_out.resolve()}\n")

    # 5. Display Pipeline Statistics
    conf_chunks = [c for c in chunks if c.source_type == "confluence"]
    jira_chunks = [c for c in chunks if c.source_type == "jira"]
    avg_chars = sum(c.char_count for c in chunks) / len(chunks) if chunks else 0
    avg_words = sum(c.word_count for c in chunks) / len(chunks) if chunks else 0

    print("Pipeline Summary Statistics:")
    print(f"  - Total Normalized Documents: {len(normalized_docs)}")
    print(f"  - Total Generated Chunks:     {len(chunks)}")
    print(f"  - Confluence Chunks:          {len(conf_chunks)} (from {len(confluence_raw)} pages)")
    print(f"  - Jira Chunks:                {len(jira_chunks)} (from {len(jira_raw)} issues)")
    print(f"  - Average Chunk Character Count: {avg_chars:.1f}")
    print(f"  - Average Chunk Word Count:      {avg_words:.1f}")

    print("\nSample Chunk Preview:")
    if chunks:
        sample = chunks[0]
        print(f"  Chunk ID: {sample.chunk_id}")
        print(f"  Section:  {sample.section_title} (Path: {' > '.join(sample.section_path)})")
        print(f"  Snippet:  {sample.text[:180]}...")

    return 0


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Confluence + Jira RAG Assistant CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # fetch-confluence subcommand
    fetch_conf_parser = subparsers.add_parser(
        "fetch-confluence",
        help="Fetch Confluence pages and export to structured JSON.",
    )
    fetch_conf_parser.add_argument(
        "--space",
        "-s",
        type=str,
        default=None,
        help="Confluence Space Key (e.g. ENG). If omitted, uses CONFLUENCE_SPACE_KEY from .env.",
    )
    fetch_conf_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="data/raw/confluence/pages.json",
        help="Output JSON file path.",
    )
    fetch_conf_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use offline mock connector for testing without credentials.",
    )

    # fetch-jira subcommand
    fetch_jira_parser = subparsers.add_parser(
        "fetch-jira",
        help="Fetch Jira issues and export to structured JSON.",
    )
    fetch_jira_parser.add_argument(
        "--project",
        "-p",
        type=str,
        default=None,
        help="Jira Project Key (e.g. PAY). If omitted, uses JIRA_PROJECT_KEY from .env.",
    )
    fetch_jira_parser.add_argument(
        "--jql",
        "-j",
        type=str,
        default=None,
        help="Custom JQL query string to filter issues.",
    )
    fetch_jira_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="data/raw/jira/issues.json",
        help="Output JSON file path.",
    )
    fetch_jira_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use offline mock connector for testing without credentials.",
    )

    # normalize-chunk subcommand
    norm_parser = subparsers.add_parser(
        "normalize-chunk",
        help="Normalize raw Confluence/Jira documents and generate text chunks.",
    )
    norm_parser.add_argument(
        "--input-confluence",
        type=str,
        default="data/raw/confluence/pages.json",
        help="Path to raw Confluence pages JSON.",
    )
    norm_parser.add_argument(
        "--input-jira",
        type=str,
        default="data/raw/jira/issues.json",
        help="Path to raw Jira issues JSON.",
    )
    norm_parser.add_argument(
        "--output-docs",
        type=str,
        default="data/processed/normalized_documents.json",
        help="Path to save normalized UnifiedDocuments JSON.",
    )
    norm_parser.add_argument(
        "--output-chunks",
        type=str,
        default="data/processed/chunks.json",
        help="Path to save generated Chunks JSON.",
    )
    norm_parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Target maximum character size per chunk.",
    )
    norm_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Character overlap between consecutive chunks in a section.",
    )
    norm_parser.add_argument(
        "--mock",
        action="store_true",
        help="Automatically generate mock raw files if missing.",
    )

    args = parser.parse_args()

    if args.command == "fetch-confluence":
        exit_code = fetch_confluence_command(args)
        sys.exit(exit_code)
    elif args.command == "fetch-jira":
        exit_code = fetch_jira_command(args)
        sys.exit(exit_code)
    elif args.command == "normalize-chunk":
        exit_code = normalize_and_chunk_command(args)
        sys.exit(exit_code)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
