"""Evaluation metrics for the RAG retrieval pipeline.

Measures how well the retriever finds the right document chunks
for a given code + task query.

Key metrics:
- Precision@K: fraction of retrieved docs that are relevant
- Recall@K: fraction of relevant docs that were retrieved
- MRR (Mean Reciprocal Rank): average 1/rank of first relevant result
- NDCG@K: normalized discounted cumulative gain
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def precision_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Fraction of top-k retrieved documents that are relevant.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs.
        relevant_ids: Set of ground-truth relevant document IDs.
        k: Number of top results to consider.

    Returns:
        Precision score between 0.0 and 1.0.
    """
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant_ids)
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / len(top_k)


def recall_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Fraction of relevant documents found in top-k results.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs.
        relevant_ids: Set of ground-truth relevant document IDs.
        k: Number of top results to consider.

    Returns:
        Recall score between 0.0 and 1.0.
    """
    if not relevant_ids:
        return 1.0  # vacuously true
    top_k = retrieved_ids[:k]
    relevant_set = set(relevant_ids)
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / len(relevant_set)


def mean_reciprocal_rank(retrieved_ids: List[str], relevant_ids: List[str]) -> float:
    """Reciprocal rank of the first relevant result.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs.
        relevant_ids: Set of ground-truth relevant document IDs.

    Returns:
        1/rank of first relevant result, or 0.0 if none found.
    """
    relevant_set = set(relevant_ids)
    for i, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_set:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain at k.

    Uses binary relevance (1 if relevant, 0 otherwise).

    Args:
        retrieved_ids: Ordered list of retrieved document IDs.
        relevant_ids: Set of ground-truth relevant document IDs.
        k: Number of top results to consider.

    Returns:
        NDCG score between 0.0 and 1.0.
    """
    if not relevant_ids or k <= 0:
        return 0.0

    relevant_set = set(relevant_ids)
    top_k = retrieved_ids[:k]

    # DCG: sum of relevance / log2(rank + 1)
    dcg = 0.0
    for i, doc_id in enumerate(top_k):
        rel = 1.0 if doc_id in relevant_set else 0.0
        dcg += rel / math.log2(i + 2)  # +2 because rank is 1-indexed

    # Ideal DCG: all relevant docs at the top
    ideal_count = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))

    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def evaluate_retrieval(
    queries: List[Dict[str, Any]],
    retriever,
    k: int = 5,
) -> Dict[str, Any]:
    """Run retrieval evaluation over a set of labeled queries.

    Each query dict must have:
        - "query": str — the search query
        - "relevant_doc_ids": List[str] — ground truth relevant doc IDs

    Args:
        queries: List of labeled query dicts.
        retriever: A Retriever instance with documents already ingested.
        k: Number of results to evaluate at.

    Returns:
        Dict with per-query results and aggregate metrics.
    """
    all_precision = []
    all_recall = []
    all_mrr = []
    all_ndcg = []
    per_query = []

    for q in queries:
        query_text = q["query"]
        relevant = q["relevant_doc_ids"]
        results = retriever.query(query_text, top_k=k)
        retrieved = [r["doc_id"] for r in results]

        p = precision_at_k(retrieved, relevant, k)
        r = recall_at_k(retrieved, relevant, k)
        mrr = mean_reciprocal_rank(retrieved, relevant)
        n = ndcg_at_k(retrieved, relevant, k)

        all_precision.append(p)
        all_recall.append(r)
        all_mrr.append(mrr)
        all_ndcg.append(n)

        per_query.append({
            "query": query_text,
            "relevant_doc_ids": relevant,
            "retrieved_doc_ids": retrieved,
            "precision@k": p,
            "recall@k": r,
            "mrr": mrr,
            "ndcg@k": n,
        })

    n_queries = len(queries)
    return {
        "k": k,
        "num_queries": n_queries,
        "mean_precision@k": sum(all_precision) / n_queries if n_queries else 0.0,
        "mean_recall@k": sum(all_recall) / n_queries if n_queries else 0.0,
        "mean_mrr": sum(all_mrr) / n_queries if n_queries else 0.0,
        "mean_ndcg@k": sum(all_ndcg) / n_queries if n_queries else 0.0,
        "per_query": per_query,
    }
