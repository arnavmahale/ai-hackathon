"""Tests for RAG retrieval evaluation metrics."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.eval_retrieval import (
    precision_at_k,
    recall_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
)


class TestPrecisionAtK:
    def test_perfect_precision(self):
        retrieved = ["a", "b", "c"]
        relevant = ["a", "b", "c"]
        assert precision_at_k(retrieved, relevant, 3) == 1.0

    def test_zero_precision(self):
        retrieved = ["x", "y", "z"]
        relevant = ["a", "b", "c"]
        assert precision_at_k(retrieved, relevant, 3) == 0.0

    def test_partial_precision(self):
        retrieved = ["a", "x", "b"]
        relevant = ["a", "b"]
        assert precision_at_k(retrieved, relevant, 3) == pytest.approx(2 / 3)

    def test_k_less_than_retrieved(self):
        retrieved = ["a", "x", "b"]
        relevant = ["a", "b"]
        assert precision_at_k(retrieved, relevant, 1) == 1.0

    def test_k_zero(self):
        assert precision_at_k(["a"], ["a"], 0) == 0.0

    def test_empty_retrieved(self):
        assert precision_at_k([], ["a"], 3) == 0.0


class TestRecallAtK:
    def test_perfect_recall(self):
        retrieved = ["a", "b", "c"]
        relevant = ["a", "b"]
        assert recall_at_k(retrieved, relevant, 3) == 1.0

    def test_zero_recall(self):
        retrieved = ["x", "y", "z"]
        relevant = ["a", "b"]
        assert recall_at_k(retrieved, relevant, 3) == 0.0

    def test_partial_recall(self):
        retrieved = ["a", "x", "y"]
        relevant = ["a", "b"]
        assert recall_at_k(retrieved, relevant, 3) == 0.5

    def test_no_relevant_docs(self):
        # Vacuously true — all 0 relevant docs are "found"
        assert recall_at_k(["a"], [], 3) == 1.0

    def test_k_limits_search(self):
        retrieved = ["x", "a"]
        relevant = ["a"]
        assert recall_at_k(retrieved, relevant, 1) == 0.0  # "a" is at index 1, beyond k=1


class TestMRR:
    def test_first_result_relevant(self):
        assert mean_reciprocal_rank(["a", "b"], ["a"]) == 1.0

    def test_second_result_relevant(self):
        assert mean_reciprocal_rank(["x", "a"], ["a"]) == 0.5

    def test_third_result_relevant(self):
        assert mean_reciprocal_rank(["x", "y", "a"], ["a"]) == pytest.approx(1 / 3)

    def test_no_relevant_found(self):
        assert mean_reciprocal_rank(["x", "y"], ["a"]) == 0.0

    def test_multiple_relevant_uses_first(self):
        assert mean_reciprocal_rank(["x", "a", "b"], ["a", "b"]) == 0.5


class TestNDCG:
    def test_perfect_ranking(self):
        retrieved = ["a", "b"]
        relevant = ["a", "b"]
        assert ndcg_at_k(retrieved, relevant, 2) == pytest.approx(1.0)

    def test_zero_ndcg(self):
        retrieved = ["x", "y"]
        relevant = ["a", "b"]
        assert ndcg_at_k(retrieved, relevant, 2) == 0.0

    def test_partial_ndcg(self):
        retrieved = ["x", "a"]
        relevant = ["a"]
        result = ndcg_at_k(retrieved, relevant, 2)
        # "a" at position 2, ideal would be position 1
        # DCG = 1/log2(3), IDCG = 1/log2(2), NDCG = log2(2)/log2(3)
        assert 0.0 < result < 1.0

    def test_k_zero(self):
        assert ndcg_at_k(["a"], ["a"], 0) == 0.0

    def test_no_relevant(self):
        assert ndcg_at_k(["a"], [], 1) == 0.0


# Import pytest for approx
import pytest
