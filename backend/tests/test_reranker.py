"""Tests for the cross-encoder reranker module."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.reranker import rerank


@pytest.fixture(autouse=True)
def mock_cross_encoder():
    """Mock the CrossEncoder to avoid downloading the model in tests."""
    mock_model = MagicMock()

    def fake_predict(pairs):
        # Return scores based on simple word overlap as a proxy
        scores = []
        for query, doc in pairs:
            q_words = set(query.lower().split())
            d_words = set(doc.lower().split())
            overlap = len(q_words & d_words)
            scores.append(float(overlap))
        return np.array(scores)

    mock_model.predict = fake_predict

    with patch("app.rag.reranker._model", mock_model):
        yield mock_model


class TestRerank:
    def test_empty_candidates(self):
        result = rerank("some query", [], top_k=3)
        assert result == []

    def test_reranks_by_relevance(self):
        candidates = [
            {"text": "unrelated document about cooking recipes", "doc_id": "a"},
            {"text": "JWT authentication security for API endpoints", "doc_id": "b"},
            {"text": "another unrelated topic about gardening", "doc_id": "c"},
        ]
        result = rerank("JWT authentication API security", candidates, top_k=2)
        assert len(result) == 2
        # The JWT doc should rank first (highest word overlap with query)
        assert result[0]["doc_id"] == "b"

    def test_top_k_limits_output(self):
        candidates = [
            {"text": f"document number {i}", "doc_id": f"doc_{i}"}
            for i in range(10)
        ]
        result = rerank("document", candidates, top_k=3)
        assert len(result) == 3

    def test_preserves_metadata(self):
        candidates = [
            {"text": "security auth JWT", "doc_id": "sec", "source": "faiss", "extra": 42},
        ]
        result = rerank("security JWT", candidates, top_k=1)
        assert result[0]["doc_id"] == "sec"
        assert result[0]["source"] == "faiss"
        assert result[0]["extra"] == 42

    def test_adds_rerank_score(self):
        candidates = [
            {"text": "some content here", "doc_id": "a"},
        ]
        result = rerank("some query", candidates, top_k=1)
        assert "rerank_score" in result[0]
        assert isinstance(result[0]["rerank_score"], float)

    def test_fewer_candidates_than_top_k(self):
        candidates = [
            {"text": "only one document", "doc_id": "a"},
        ]
        result = rerank("query", candidates, top_k=5)
        assert len(result) == 1

    def test_candidates_without_text_handled(self):
        candidates = [
            {"text": "valid document about security", "doc_id": "a"},
            {"doc_id": "b"},  # no text key
            {"text": "", "doc_id": "c"},  # empty text
            {"text": "another valid doc about security", "doc_id": "d"},
        ]
        result = rerank("security", candidates, top_k=3)
        # Should not crash, valid docs should be returned
        assert len(result) >= 1
        valid_ids = [r["doc_id"] for r in result if r.get("rerank_score", -999) > -999]
        assert len(valid_ids) >= 1

    def test_mixed_sources_reranked_together(self):
        """Linked chunks and FAISS results should be reranked as one pool."""
        candidates = [
            {"text": "error handling logging requirements", "doc_id": "linked", "source": "linked_chunk"},
            {"text": "JWT auth security endpoint protection", "doc_id": "faiss1", "source": "faiss_retrieval"},
            {"text": "error handling try catch must log errors", "doc_id": "faiss2", "source": "faiss_retrieval"},
        ]
        result = rerank("error handling logging try catch", candidates, top_k=2)
        assert len(result) == 2
        # Both error-handling docs should rank above the JWT doc
        result_ids = [r["doc_id"] for r in result]
        assert "faiss1" not in result_ids

    def test_deterministic_ordering(self):
        """Same input should produce same output."""
        candidates = [
            {"text": "alpha beta gamma", "doc_id": "a"},
            {"text": "delta epsilon zeta", "doc_id": "b"},
            {"text": "alpha gamma delta", "doc_id": "c"},
        ]
        result1 = rerank("alpha gamma", candidates, top_k=3)
        result2 = rerank("alpha gamma", candidates, top_k=3)
        assert [r["doc_id"] for r in result1] == [r["doc_id"] for r in result2]
