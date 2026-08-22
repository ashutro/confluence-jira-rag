"""Command Line Interface for Confluence + Jira RAG Assistant."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from rag_assistant.assistant import RAGAssistant
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
from rag_assistant.sample_data import load_benchmark_queries
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

    print("\nNormalizing records into Unified Documents...")
    normalized_docs = DocumentNormalizer.normalize_all(confluence_raw, jira_raw)
    DocumentNormalizer.save_documents_to_json(normalized_docs, docs_out)
    print(f"Saved {len(normalized_docs)} UnifiedDocument(s) to: {docs_out.resolve()}")

    print(f"\nChunking documents (size={chunk_size}, overlap={chunk_overlap})...")
    chunker = MarkdownChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = chunker.chunk_documents(normalized_docs)
    MarkdownChunker.save_chunks_to_json(chunks, chunks_out)
    print(f"Generated {len(chunks)} Chunk(s) saved to: {chunks_out.resolve()}\n")

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


def ask_command(args: argparse.Namespace) -> int:
    """Execute end-to-end RAG Q&A query."""
    question = args.question
    provider = args.provider
    model = args.model
    top_k = args.top_k
    source_filter = args.source
    db_path = args.db_path
    collection = args.collection
    use_mock = args.mock

    print("=" * 60)
    print("Enterprise RAG Assistant (Milestone 8)")
    print("=" * 60)
    print(f"Question: \"{question}\"")
    if source_filter:
        print(f"Filter:   {source_filter.upper()} only")
    print("=" * 60)

    try:
        assistant = RAGAssistant.create(
            db_path=db_path,
            collection_name=collection,
            use_mock=use_mock,
            provider_name=provider,
            model_name=model,
        )
        answer = assistant.ask(
            question=question,
            top_k=top_k,
            filter_source=source_filter,
        )

        if args.format == "json":
            print(json.dumps(answer.to_dict(), indent=2))
            return 0

        print(f"\n{answer.answer}\n")
        print("-" * 60)
        print(f"Provider: {answer.provider} ({answer.model_name}) | Latency: {answer.execution_time_ms:.1f}ms")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n[Error] Generation failed: {e}", file=sys.stderr)
        return 1


def chat_command(args: argparse.Namespace) -> int:
    """Launch interactive CLI chat session with the RAG assistant."""
    db_path = args.db_path
    collection = args.collection
    provider = args.provider
    model = args.model
    use_mock = args.mock

    print("=" * 60)
    print("🤖 Confluence + Jira RAG Interactive Assistant")
    print("=" * 60)
    print("Ask any question about documentation, runbooks, or tickets.")
    print("Type 'exit', 'quit', or 'q' to stop.")
    print("=" * 60 + "\n")

    try:
        assistant = RAGAssistant.create(
            db_path=db_path,
            collection_name=collection,
            use_mock=use_mock,
            provider_name=provider,
            model_name=model,
        )

        while True:
            try:
                question = input("❓ Question: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not question:
                continue
            if question.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            print("\nSearching knowledge base & synthesizing answer...")
            answer = assistant.ask(question=question, top_k=3)
            print("\n" + "=" * 60)
            print(answer.answer)
            print("=" * 60)
            print(f"[{answer.provider} | {answer.execution_time_ms:.1f}ms]\n")

        return 0

    except Exception as e:
        print(f"\n[Error] Chat session error: {e}", file=sys.stderr)
        return 1


def evaluate_qa_command(args: argparse.Namespace) -> int:
    """Execute end-to-end benchmark Q&A evaluation."""
    queries_file = Path(args.queries)
    db_path = args.db_path
    collection = args.collection
    use_mock = args.mock

    print("=" * 60)
    print("End-to-End RAG Q&A Benchmark Evaluation (Milestone 8)")
    print("=" * 60)
    print(f"Benchmark Queries: {queries_file}\n")

    queries = load_benchmark_queries(queries_file)
    assistant = RAGAssistant.create(
        db_path=db_path,
        collection_name=collection,
        use_mock=use_mock,
    )

    passed_count = 0
    total_time_ms = 0.0

    print("Evaluating Generated Answers:")
    print("-" * 60)
    for q in queries:
        ans = assistant.ask(question=q.question, top_k=3)
        total_time_ms += ans.execution_time_ms

        retrieved_ids = {c.source_id for c in ans.context.chunks}
        target_set = set(q.target_sources)
        hit_target = bool(target_set.intersection(retrieved_ids))

        # Check keyword inclusion
        ans_lower = ans.answer.lower()
        keywords = getattr(q, "expected_answer_keywords", getattr(q, "expected_keywords", []))
        keyword_hits = sum(1 for kw in keywords if kw.lower() in ans_lower)
        keyword_coverage = (keyword_hits / len(keywords)) if keywords else 1.0

        is_passed = hit_target and keyword_coverage >= 0.3
        if is_passed:
            passed_count += 1

        status_icon = "PASS" if is_passed else "FAIL"
        print(f"[{status_icon}] [{q.id}]")
        print(f"  Q: \"{q.question}\"")
        print(f"  Target Sources: {q.target_sources} -> Retrieved: {list(retrieved_ids)}")
        print(f"  Keyword Coverage: {keyword_coverage * 100:.0f}% ({keyword_hits}/{len(keywords)})")
        print(f"  Answer Snippet: {ans.answer[:120].replace(chr(10), ' ')}...\n")

    n = len(queries) or 1
    accuracy = (passed_count / n) * 100.0
    avg_latency = total_time_ms / n

    print("=" * 60)
    print("Benchmark Q&A Summary:")
    print("=" * 60)
    print(f"  Total Queries:      {n}")
    print(f"  Passed Queries:     {passed_count} ({accuracy:.1f}%)")
    print(f"  Average Latency:    {avg_latency:.1f}ms")
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

    # retrieve subcommand
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

    # evaluate-retrieval subcommand
    eval_ret_parser = subparsers.add_parser(
        "evaluate-retrieval",
        help="Evaluate retrieval performance against benchmark queries.",
    )
    eval_ret_parser.add_argument(
        "--queries",
        "-q",
        type=str,
        default="data/sample/queries.json",
        help="Path to evaluation benchmark queries JSON file.",
    )
    eval_ret_parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default="knowledge_base",
        help="Qdrant collection name.",
    )
    eval_ret_parser.add_argument(
        "--db-path",
        type=str,
        default="data/qdrant_db",
        help="Local Qdrant database directory.",
    )
    eval_ret_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use offline mock embedder.",
    )

    # ask subcommand (Milestone 8)
    ask_parser = subparsers.add_parser(
        "ask",
        help="Ask a question and receive a grounded synthesized answer with citations.",
    )
    ask_parser.add_argument(
        "question",
        type=str,
        help="Question to ask the assistant.",
    )
    ask_parser.add_argument(
        "--provider",
        type=str,
        choices=["openai", "anthropic", "gemini", "ollama", "mock"],
        default=None,
        help="LLM provider name.",
    )
    ask_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Specific model name (e.g. gpt-4o, claude-3-5-sonnet).",
    )
    ask_parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=3,
        help="Number of retrieved chunks for context.",
    )
    ask_parser.add_argument(
        "--source",
        type=str,
        choices=["confluence", "jira"],
        default=None,
        help="Filter context by source type.",
    )
    ask_parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default="knowledge_base",
        help="Qdrant collection name.",
    )
    ask_parser.add_argument(
        "--db-path",
        type=str,
        default="data/qdrant_db",
        help="Local Qdrant database directory.",
    )
    ask_parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["pretty", "json"],
        default="pretty",
        help="Output display format.",
    )
    ask_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use offline mock mode (MockEmbedder + MockLLMProvider).",
    )

    # chat subcommand (Milestone 8)
    chat_parser = subparsers.add_parser(
        "chat",
        help="Start an interactive chat session with the RAG assistant.",
    )
    chat_parser.add_argument(
        "--provider",
        type=str,
        choices=["openai", "anthropic", "gemini", "ollama", "mock"],
        default=None,
        help="LLM provider name.",
    )
    chat_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name.",
    )
    chat_parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default="knowledge_base",
        help="Qdrant collection name.",
    )
    chat_parser.add_argument(
        "--db-path",
        type=str,
        default="data/qdrant_db",
        help="Local Qdrant database directory.",
    )
    chat_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use offline mock mode.",
    )

    # evaluate-qa subcommand (Milestone 8)
    eval_qa_parser = subparsers.add_parser(
        "evaluate-qa",
        help="Evaluate end-to-end question answering against benchmark dataset.",
    )
    eval_qa_parser.add_argument(
        "--queries",
        "-q",
        type=str,
        default="data/sample/queries.json",
        help="Path to evaluation benchmark queries JSON file.",
    )
    eval_qa_parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default="knowledge_base",
        help="Qdrant collection name.",
    )
    eval_qa_parser.add_argument(
        "--db-path",
        type=str,
        default="data/qdrant_db",
        help="Local Qdrant database directory.",
    )
    eval_qa_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use offline mock mode.",
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
    elif args.command == "ask":
        exit_code = ask_command(args)
        sys.exit(exit_code)
    elif args.command == "chat":
        exit_code = chat_command(args)
        sys.exit(exit_code)
    elif args.command == "evaluate-qa":
        exit_code = evaluate_qa_command(args)
        sys.exit(exit_code)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
