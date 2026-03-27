"""Evaluation metrics for the RAG retrieval pipeline.
- **Precision@K**, **Recall@K****F1@K****MRR (Mean Reciprocal Rank)****MAP (Mean Average Precision)**
- **NDCG@K (Normalized Discounted Cumulative Gain)**
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RetrievalEvalExample:
    """A single retrieval evaluation test case."""
    query: str
    relevant_doc_ids: List[str]
    description: str = ""


def precision_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Fraction of top-k retrieved documents that are relevant."""
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant_ids)
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / len(top_k)


def recall_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Fraction of relevant documents found in top-k results."""
    if not relevant_ids:
        return 1.0  # vacuously true
    top_k = retrieved_ids[:k]
    relevant_set = set(relevant_ids)
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / len(relevant_set)


def f1_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Harmonic mean of Precision@K and Recall@K."""
    p = precision_at_k(retrieved_ids, relevant_ids, k)
    r = recall_at_k(retrieved_ids, relevant_ids, k)
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def average_precision(retrieved_ids: List[str], relevant_ids: List[str]) -> float:
    """Average Precision for a single query."""
    if not relevant_ids:
        return 1.0
    relevant_set = set(relevant_ids)
    hits = 0
    sum_precision = 0.0
    for i, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_set:
            hits += 1
            sum_precision += hits / (i + 1)
    if hits == 0:
        return 0.0
    return sum_precision / len(relevant_set)


def mean_average_precision(
    results: List[Tuple[List[str], List[str]]],
) -> float:
    """Mean Average Precision across multiple queries."""
    if not results:
        return 0.0
    return sum(average_precision(r, rel) for r, rel in results) / len(results)


def mean_reciprocal_rank(retrieved_ids: List[str], relevant_ids: List[str]) -> float:
    """Reciprocal rank of the first relevant result."""
    relevant_set = set(relevant_ids)
    for i, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_set:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain at k."""
    if not relevant_ids or k <= 0:
        return 0.0

    relevant_set = set(relevant_ids)
    top_k = retrieved_ids[:k]

    # DCG: sum of relevance / log2(rank + 1)
    dcg = 0.0
    for i, doc_id in enumerate(top_k):
        rel = 1.0 if doc_id in relevant_set else 0.0
        dcg += rel / math.log2(i + 2)  # +2 because rank is 1-indexed

    # Ideal DCG: all relevant docs ranked at the top
    ideal_count = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))

    if idcg == 0.0:
        return 0.0
    return dcg / idcg


@dataclass
class EvaluationSuite:
    """Comprehensive retrieval evaluation suite."""
    retriever: Any
    examples: List[RetrievalEvalExample]
    k_values: List[int] = field(default_factory=lambda: [1, 3, 5, 10])

    def run(self) -> Dict[str, Any]:
        """Execute evaluation and compute all metrics."""
        per_query_results = []
        all_retrieved_relevant_pairs = []

        for example in self.examples:
            results = self.retriever.query(example.query, top_k=max(self.k_values))
            # Deduplicate doc_ids preserving order (multiple chunks from same doc
            # should only count once for document-level retrieval metrics)
            seen = set()
            retrieved_ids = []
            for r in results:
                doc_id = r.get("doc_id", "")
                if doc_id not in seen:
                    seen.add(doc_id)
                    retrieved_ids.append(doc_id)

            query_metrics = {
                "query": example.query,
                "description": example.description,
                "relevant_doc_ids": example.relevant_doc_ids,
                "retrieved_doc_ids": retrieved_ids,
            }

            # Compute metrics at each K
            for k in self.k_values:
                query_metrics[f"precision@{k}"] = precision_at_k(retrieved_ids, example.relevant_doc_ids, k)
                query_metrics[f"recall@{k}"] = recall_at_k(retrieved_ids, example.relevant_doc_ids, k)
                query_metrics[f"f1@{k}"] = f1_at_k(retrieved_ids, example.relevant_doc_ids, k)
                query_metrics[f"ndcg@{k}"] = ndcg_at_k(retrieved_ids, example.relevant_doc_ids, k)

            query_metrics["mrr"] = mean_reciprocal_rank(retrieved_ids, example.relevant_doc_ids)
            query_metrics["ap"] = average_precision(retrieved_ids, example.relevant_doc_ids)

            per_query_results.append(query_metrics)
            all_retrieved_relevant_pairs.append((retrieved_ids, example.relevant_doc_ids))

        # Aggregate metrics
        n = len(self.examples)
        aggregate = {}
        for k in self.k_values:
            aggregate[f"mean_precision@{k}"] = sum(q[f"precision@{k}"] for q in per_query_results) / n if n else 0
            aggregate[f"mean_recall@{k}"] = sum(q[f"recall@{k}"] for q in per_query_results) / n if n else 0
            aggregate[f"mean_f1@{k}"] = sum(q[f"f1@{k}"] for q in per_query_results) / n if n else 0
            aggregate[f"mean_ndcg@{k}"] = sum(q[f"ndcg@{k}"] for q in per_query_results) / n if n else 0

        aggregate["mean_mrr"] = sum(q["mrr"] for q in per_query_results) / n if n else 0
        aggregate["map"] = mean_average_precision(all_retrieved_relevant_pairs)
        aggregate["num_queries"] = n
        aggregate["k_values"] = self.k_values

        return {
            "aggregate": aggregate,
            "per_query": per_query_results,
        }

    def print_report(self, report: Optional[Dict[str, Any]] = None) -> None:
        """Print a formatted evaluation report to stdout."""
        if report is None:
            report = self.run()

        agg = report["aggregate"]
        print("\n" + "=" * 70)
        print("  RAG RETRIEVAL EVALUATION REPORT")
        print("=" * 70)

        # Aggregate metrics table
        print(f"\n  Queries evaluated: {agg['num_queries']}")
        print(f"  MAP:               {agg['map']:.4f}")
        print(f"  Mean MRR:          {agg['mean_mrr']:.4f}")

        print(f"\n  {'K':>4}  {'P@K':>8}  {'R@K':>8}  {'F1@K':>8}  {'NDCG@K':>8}")
        print(f"  {'':->4}  {'':->8}  {'':->8}  {'':->8}  {'':->8}")
        for k in agg["k_values"]:
            print(f"  {k:>4}  {agg[f'mean_precision@{k}']:>8.4f}  "
                  f"{agg[f'mean_recall@{k}']:>8.4f}  "
                  f"{agg[f'mean_f1@{k}']:>8.4f}  "
                  f"{agg[f'mean_ndcg@{k}']:>8.4f}")

        # Per-query breakdown
        print(f"\n  Per-Query Breakdown:")
        print(f"  {'-' * 66}")
        for pq in report["per_query"]:
            k = max(agg["k_values"])
            status = "PASS" if pq.get(f"recall@{k}", 0) >= 0.5 else "FAIL"
            print(f"  [{status}] {pq['query'][:55]}...")
            if pq["description"]:
                print(f"         {pq['description']}")
            print(f"         Expected: {pq['relevant_doc_ids']}")
            print(f"         Got:      {pq['retrieved_doc_ids'][:5]}")
            print(f"         MRR={pq['mrr']:.3f}  AP={pq['ap']:.3f}  "
                  f"P@3={pq.get('precision@3', 0):.3f}  R@3={pq.get('recall@3', 0):.3f}")
            print()

    def run_and_print(self) -> Dict[str, Any]:
        """Convenience method: run evaluation and print the report."""
        report = self.run()
        self.print_report(report)
        return report


# Legacy interface for backwards compatibility
def evaluate_retrieval(
    queries: List[Dict[str, Any]],
    retriever,
    k: int = 5,
) -> Dict[str, Any]:
    """Run retrieval evaluation over a set of labeled queries."""
    examples = [
        RetrievalEvalExample(
            query=q["query"],
            relevant_doc_ids=q["relevant_doc_ids"],
            description=q.get("description", ""),
        )
        for q in queries
    ]

    suite = EvaluationSuite(retriever=retriever, examples=examples, k_values=[k])
    report = suite.run()

    # Reshape into legacy format
    agg = report["aggregate"]
    per_query = []
    for pq in report["per_query"]:
        per_query.append({
            "query": pq["query"],
            "relevant_doc_ids": pq["relevant_doc_ids"],
            "retrieved_doc_ids": pq["retrieved_doc_ids"],
            "precision@k": pq.get(f"precision@{k}", 0),
            "recall@k": pq.get(f"recall@{k}", 0),
            "f1@k": pq.get(f"f1@{k}", 0),
            "mrr": pq["mrr"],
            "ndcg@k": pq.get(f"ndcg@{k}", 0),
        })

    return {
        "k": k,
        "num_queries": agg["num_queries"],
        "mean_precision@k": agg.get(f"mean_precision@{k}", 0),
        "mean_recall@k": agg.get(f"mean_recall@{k}", 0),
        "mean_f1@k": agg.get(f"mean_f1@{k}", 0),
        "mean_mrr": agg["mean_mrr"],
        "mean_ndcg@k": agg.get(f"mean_ndcg@{k}", 0),
        "map": agg["map"],
        "per_query": per_query,
    }
