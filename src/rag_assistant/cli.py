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
from rag_assistant.core.models import Chunk, UnifiedDocument
from rag_assistant.processing.chunker import MarkdownChunker
from rag_assistant.processing.normalizer import DocumentNormalizer
from rag_assistant.retrieval.evaluator import RetrievalEvaluator
from rag_assistant.retrieval.retriever import RAGRetriever
from rag_assistant.vector_store.embeddings import get_embedder
from rag_assistant.vector_store.qdrant import QdrantVectorStore


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

    return 0


def index_qdrant_command(args: argparse.Namespace) -> int:
    """Embed chunks and index into Qdrant Vector Database."""
    input_file = Path(args.input)
    db_path = Path(args.db_path)
    collection = args.collection
    recreate = args.recreate

    print("=" * 60)
    print("Qdrant Vector Database Indexing (Milestone 6)")
    print("=" * 60)

    if not input_file.exists():
        if args.mock:
            print(f"Chunks file '{input_file}' not found. Auto-running normalize-chunk in mock mode...")
            norm_args = argparse.Namespace(
                input_confluence="data/raw/confluence/pages.json",
                input_jira="data/raw/jira/issues.json",
                output_docs="data/processed/normalized_documents.json",
                output_chunks=str(input_file),
                chunk_size=800,
                chunk_overlap=100,
                mock=True,
            )
            normalize_and_chunk_command(norm_args)
        else:
            print(f"[Error] Input chunks file '{input_file}' not found. Run `normalize-chunk` first.", file=sys.stderr)
            return 1

    with open(input_file, "r", encoding="utf-8") as f:
        raw_chunks = json.load(f)

    chunks = [Chunk.from_dict(c) for c in raw_chunks]
    print(f"Loaded {len(chunks)} chunk(s) from {input_file}")

    embedder = get_embedder(use_mock=args.mock)
    print(f"Embedder: {embedder.__class__.__name__} (dimension={embedder.dimension})")
    print(f"Qdrant Storage: Local on-disk ({db_path})")
    print(f"Target Collection: '{collection}'")

    vector_store = QdrantVectorStore(
        embedder=embedder,
        path=db_path,
        default_collection=collection,
    )

    if recreate:
        print(f"Recreating collection '{collection}'...")
        vector_store.init_collection(collection, recreate=True)

    print("\nGenerating embeddings and upserting points to Qdrant...")
    indexed_count = vector_store.index_chunks(chunks, collection_name=collection)
    print(f"Successfully indexed {indexed_count} vector points into Qdrant collection '{collection}'.")
    return 0


def search_qdrant_command(args: argparse.Namespace) -> int:
    """Perform semantic similarity search against Qdrant."""
    query = args.query
    collection = args.collection
    db_path = Path(args.db_path)
    limit = args.limit
    source_filter = args.source
    threshold = args.score_threshold

    print("=" * 60)
    print(f"Qdrant Semantic Search Query: \"{query}\"")
    print("=" * 60)

    embedder = get_embedder(use_mock=args.mock)
    vector_store = QdrantVectorStore(
        embedder=embedder,
        path=db_path,
        default_collection=collection,
    )

    results = vector_store.search(
        query=query,
        limit=limit,
        score_threshold=threshold,
        filter_source=source_filter,
        collection_name=collection,
    )

    if not results:
        print("\nNo matching documents found in Qdrant collection.")
        return 0

    print(f"\nFound {len(results)} relevant result(s):\n")
    for idx, hit in enumerate(results, start=1):
        print(f"--- [Rank {idx}] Score: {hit.score:.4f} | {hit.source_type.upper()} [{hit.source_id}] ---")
        print(f"Title:   {hit.title}")
        print(f"Section: {' > '.join(hit.section_path) if hit.section_path else hit.section_title}")
        print(f"Snippet:\n{hit.raw_text[:280]}...")
        print()

    return 0


def retrieve_command(args: argparse.Namespace) -> int:
    """Execute contextual retrieval with hybrid re-ranking and source citations."""
    query = args.query
    top_k = args.top_k
    source_filter = args.source
    db_path = Path(args.db_path)
    out_format = args.format

    print("=" * 60)
    print("Context-Grounded Retrieval Engine (Milestone 7)")
    print("=" * 60)
    print(f"User Query: \"{query}\"")
    if source_filter:
        print(f"Source Filter: {source_filter.upper()}")
    print(f"Top-K Chunks: {top_k}\n")

    embedder = get_embedder(use_mock=args.mock)
    vector_store = QdrantVectorStore(
        embedder=embedder,
        path=db_path,
        default_collection=args.collection,
    )
    retriever = RAGRetriever(vector_store=vector_store, default_top_k=top_k)

    context = retriever.retrieve(
        query=query,
        top_k=top_k,
        filter_source=source_filter,
    )

    if not context.chunks:
        print("No matching knowledge base records found.")
        return 0

    if out_format == "json":
        print(json.dumps(context.to_dict(), indent=2))
        return 0

    if out_format == "context":
        print("=== Formatted Prompt Context for LLM Synthesis ===")
        print(context.formatted_prompt_context)
        print("\n=== Sources ===")
        for s in context.sources:
            print(f"- [{s['source_type'].upper()} {s['source_id']}] {s['title']} (Citations: {s['citation_indices']})")
        return 0

    # Default table/cards view
    print(f"Retrieved {len(context.chunks)} top chunk(s) across {len(context.sources)} document source(s):\n")
    for chunk in context.chunks:
        print(f"--- {chunk.citation_tag} | Score: {chunk.score:.4f} ---")
        print(f"Section: {' > '.join(chunk.section_path) if chunk.section_path else chunk.section_title}")
        if chunk.url:
            print(f"URL:     {chunk.url}")
        print(f"Snippet:\n{chunk.raw_text[:240]}...\n")

    return 0


def evaluate_retrieval_command(args: argparse.Namespace) -> int:
    """Execute benchmark retrieval evaluation against curated queries."""
    queries_file = Path(args.queries)
    db_path = Path(args.db_path)
    collection = args.collection

    print("=" * 60)
    print("Retrieval Benchmark Evaluation (Milestone 7)")
    print("=" * 60)
    print(f"Benchmark File: {queries_file}")
    print(f"Vector Database: {db_path} ('{collection}')\n")

    embedder = get_embedder(use_mock=args.mock)
    vector_store = QdrantVectorStore(
        embedder=embedder,
        path=db_path,
        default_collection=collection,
    )
    retriever = RAGRetriever(vector_store=vector_store, default_top_k=5)
    evaluator = RetrievalEvaluator(retriever=retriever)

    report = evaluator.evaluate(queries_file=queries_file)

    print("Evaluation Results per Query:")
    print("-" * 60)
    for r in report.query_results:
        hit_icon = "PASS" if r.hit_at_3 else "FAIL"
        targets = ", ".join(r.target_sources)
        retrieved = ", ".join(r.retrieved_sources[:3])
        print(f"[{hit_icon}] [{r.query_id}] ({r.category})")
        print(f"  Q: \"{r.question}\"")
        print(f"  Target:    [{targets}]")
        print(f"  Retrieved: [{retrieved}]")
        print(f"  Hit@1: {r.hit_at_1} | Hit@3: {r.hit_at_3} | RR: {r.reciprocal_rank:.3f}\n")

    print("=" * 60)
    print("Aggregated Retrieval Metrics:")
    print("=" * 60)
    print(f"  Total Benchmark Queries:   {report.total_queries}")
    print(f"  Hit Rate @ 1:              {report.hit_rate_at_1 * 100:.1f}%")
    print(f"  Hit Rate @ 3:              {report.hit_rate_at_3 * 100:.1f}%")
    print(f"  Hit Rate @ 5:              {report.hit_rate_at_5 * 100:.1f}%")
    print(f"  Mean Reciprocal Rank (MRR): {report.mrr:.4f}")
    print("=" * 60)

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
        help="Confluence Space Key (e.g. ENG).",
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
        help="Jira Project Key (e.g. PAY).",
    )
    fetch_jira_parser.add_argument(
        "--jql",
        "-j",
        type=str,
        default=None,
        help="Custom JQL query string.",
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

    # index-qdrant subcommand
    index_parser = subparsers.add_parser(
        "index-qdrant",
        help="Embed chunks and index them into Qdrant Vector Database.",
    )
    index_parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="data/processed/chunks.json",
        help="Path to processed chunks.json.",
    )
    index_parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default="knowledge_base",
        help="Qdrant collection name.",
    )
    index_parser.add_argument(
        "--db-path",
        type=str,
        default="data/qdrant_db",
        help="Local on-disk Qdrant storage path.",
    )
    index_parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate the Qdrant collection if it already exists.",
    )
    index_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic offline MockEmbedder.",
    )

    # search-qdrant subcommand
    search_parser = subparsers.add_parser(
        "search-qdrant",
        help="Execute semantic search against Qdrant Vector Database.",
    )
    search_parser.add_argument(
        "query",
        type=str,
        help="Natural language question or search query.",
    )
    search_parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default="knowledge_base",
        help="Qdrant collection name.",
    )
    search_parser.add_argument(
        "--db-path",
        type=str,
        default="data/qdrant_db",
        help="Local on-disk Qdrant storage path.",
    )
    search_parser.add_argument(
        "--limit",
        "-k",
        type=int,
        default=5,
        help="Maximum number of top search results to return.",
    )
    search_parser.add_argument(
        "--source",
        type=str,
        choices=["confluence", "jira"],
        default=None,
        help="Filter search results by source type.",
    )
    search_parser.add_argument(
        "--score-threshold",
        type=float,
        default=None,
        help="Minimum similarity score threshold (0.0 to 1.0).",
    )
    search_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic offline MockEmbedder.",
    )

    # retrieve subcommand (Milestone 7)
    retrieve_parser = subparsers.add_parser(
        "retrieve",
        help="Retrieve grounded context chunks with source citations for a question.",
    )
    retrieve_parser.add_argument(
        "query",
        type=str,
        help="User question to retrieve context for.",
    )
    retrieve_parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=3,
        help="Number of context chunks to retrieve.",
    )
    retrieve_parser.add_argument(
        "--source",
        type=str,
        choices=["confluence", "jira"],
        default=None,
        help="Filter retrieval by source type.",
    )
    retrieve_parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default="knowledge_base",
        help="Qdrant collection name.",
    )
    retrieve_parser.add_argument(
        "--db-path",
        type=str,
        default="data/qdrant_db",
        help="Local Qdrant database directory.",
    )
    retrieve_parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["table", "context", "json"],
        default="table",
        help="Output display format.",
    )
    retrieve_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use offline mock embedder.",
    )

    # evaluate-retrieval subcommand (Milestone 7)
    eval_parser = subparsers.add_parser(
        "evaluate-retrieval",
        help="Evaluate retrieval performance against benchmark queries.",
    )
    eval_parser.add_argument(
        "--queries",
        "-q",
        type=str,
        default="data/sample/queries.json",
        help="Path to evaluation benchmark queries JSON file.",
    )
    eval_parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default="knowledge_base",
        help="Qdrant collection name.",
    )
    eval_parser.add_argument(
        "--db-path",
        type=str,
        default="data/qdrant_db",
        help="Local Qdrant database directory.",
    )
    eval_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use offline mock embedder.",
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
    elif args.command == "index-qdrant":
        exit_code = index_qdrant_command(args)
        sys.exit(exit_code)
    elif args.command == "search-qdrant":
        exit_code = search_qdrant_command(args)
        sys.exit(exit_code)
    elif args.command == "retrieve":
        exit_code = retrieve_command(args)
        sys.exit(exit_code)
    elif args.command == "evaluate-retrieval":
        exit_code = evaluate_retrieval_command(args)
        sys.exit(exit_code)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
