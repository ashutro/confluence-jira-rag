"""Retrieval benchmark evaluator calculating Hit Rate and MRR on evaluation queries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from rag_assistant.retrieval.retriever import RAGRetriever
from rag_assistant.sample_data import BenchmarkQuery, load_benchmark_queries


@dataclass
class QueryEvalResult:
    """Evaluation result for a single benchmark query."""

    query_id: str
    category: str
    question: str
    target_sources: List[str]
    retrieved_sources: List[str]
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    reciprocal_rank: float


@dataclass
class BenchmarkReport:
    """Aggregated benchmark evaluation report."""

    total_queries: int
    hit_rate_at_1: float
    hit_rate_at_3: float
    hit_rate_at_5: float
    mrr: float
    query_results: List[QueryEvalResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            "hit_rate_at_1": round(self.hit_rate_at_1, 4),
            "hit_rate_at_3": round(self.hit_rate_at_3, 4),
            "hit_rate_at_5": round(self.hit_rate_at_5, 4),
            "mrr": round(self.mrr, 4),
            "query_results": [
                {
                    "query_id": q.query_id,
                    "category": q.category,
                    "question": q.question,
                    "target_sources": q.target_sources,
                    "retrieved_sources": q.retrieved_sources,
                    "hit_at_1": q.hit_at_1,
                    "hit_at_3": q.hit_at_3,
                    "hit_at_5": q.hit_at_5,
                    "reciprocal_rank": round(q.reciprocal_rank, 4),
                }
                for q in self.query_results
            ],
        }


class RetrievalEvaluator:
    """Evaluates RAGRetriever against curated benchmark queries."""

    def __init__(self, retriever: RAGRetriever) -> None:
        self.retriever = retriever

    def evaluate(
        self,
        queries: Optional[List[BenchmarkQuery]] = None,
        queries_file: Optional[Path | str] = None,
    ) -> BenchmarkReport:
        """Run evaluation on benchmark queries and compute Information Retrieval metrics."""
        if queries is None:
            queries = load_benchmark_queries(queries_file)

        eval_results: List[QueryEvalResult] = []

        for q in queries:
            ctx = self.retriever.retrieve(query=q.question, top_k=5)
            retrieved_source_ids = [c.source_id for c in ctx.chunks]

            target_set = set(q.target_sources)

            # Check hits at 1, 3, 5
            hit_1 = bool(target_set.intersection(retrieved_source_ids[:1]))
            hit_3 = bool(target_set.intersection(retrieved_source_ids[:3]))
            hit_5 = bool(target_set.intersection(retrieved_source_ids[:5]))

            # Compute Reciprocal Rank
            rr = 0.0
            for rank, s_id in enumerate(retrieved_source_ids, start=1):
                if s_id in target_set:
                    rr = 1.0 / rank
                    break

            eval_results.append(
                QueryEvalResult(
                    query_id=q.id,
                    category=getattr(q, "category", "General"),
                    question=q.question,
                    target_sources=q.target_sources,
                    retrieved_sources=retrieved_source_ids,
                    hit_at_1=hit_1,
                    hit_at_3=hit_3,
                    hit_at_5=hit_5,
                    reciprocal_rank=rr,
                )
            )

        n = len(eval_results) or 1
        return BenchmarkReport(
            total_queries=len(eval_results),
            hit_rate_at_1=sum(1 for r in eval_results if r.hit_at_1) / n,
            hit_rate_at_3=sum(1 for r in eval_results if r.hit_at_3) / n,
            hit_rate_at_5=sum(1 for r in eval_results if r.hit_at_5) / n,
            mrr=sum(r.reciprocal_rank for r in eval_results) / n,
            query_results=eval_results,
        )
