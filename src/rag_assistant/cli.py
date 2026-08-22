"""Command Line Interface for Confluence + Jira RAG Assistant."""

from __future__ import annotations

import argparse
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
            print(f"     Markdown Length: {len(page.body_markdown)} chars | Text Length: {len(page.body_text)} chars")

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
            print(f"     Description Length: {len(issue.description_markdown)} chars | Comments: {len(issue.comments)}")

        connector.save_issues_to_json(issues, output_path)
        print(f"\nExported structured JSON to: {output_path.resolve()}")
        return 0

    except Exception as err:
        print(f"\n[Error] Retrieval failed: {err}", file=sys.stderr)
        return 1


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

    args = parser.parse_args()

    if args.command == "fetch-confluence":
        exit_code = fetch_confluence_command(args)
        sys.exit(exit_code)
    elif args.command == "fetch-jira":
        exit_code = fetch_jira_command(args)
        sys.exit(exit_code)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
