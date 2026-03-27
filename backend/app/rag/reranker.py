"""Cross-encoder reranker for RAG pipeline"""


from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_model = None


def _load_model():
    """Lazy-load the cross-encoder model on first use."""
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        logger.info("Loaded cross-encoder reranker model")
    return _model


def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 3,
    text_key: str = "text",
) -> List[Dict[str, Any]]:
    """Rerank candidate chunks using a cross-encoder model.

    Takes the query and a list of candidate chunks (from FAISS + linked chunks),
    scores each (query, chunk_text) pair with the cross-encoder, and returns
    the top-k by relevance.
    """
    if not candidates:
        return []

    if len(candidates) <= top_k:
        # Not enough candidates to warrant reranking, but still score them
        if len(candidates) == 0:
            return []

    model = _load_model()

    # Build (query, document) pairs for the cross-encoder
    pairs = [(query, c[text_key]) for c in candidates if c.get(text_key)]

    if not pairs:
        return candidates[:top_k]

    # Cross-encoder scores each pair — higher = more relevant
    scores = model.predict(pairs)

    # Attach scores and sort
    scored = []
    pair_idx = 0
    for candidate in candidates:
        if candidate.get(text_key):
            scored.append({
                **candidate,
                "rerank_score": float(scores[pair_idx]),
            })
            pair_idx += 1
        else:
            scored.append({**candidate, "rerank_score": -999.0})

    scored.sort(key=lambda x: x["rerank_score"], reverse=True)

    return scored[:top_k]
