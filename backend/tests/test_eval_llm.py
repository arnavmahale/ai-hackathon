"""Tests for LLM compliance verdict evaluation metrics."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.eval_llm import (
    confusion_matrix,
    accuracy,
    precision,
    recall,
    f1_score,
    evaluate_llm_verdicts,
)


class TestConfusionMatrix:
    def test_all_true_positives(self):
        cm = confusion_matrix([True, True], [True, True])
        assert cm == {"tp": 2, "fp": 0, "tn": 0, "fn": 0}

    def test_all_true_negatives(self):
        cm = confusion_matrix([False, False], [False, False])
        assert cm == {"tp": 0, "fp": 0, "tn": 2, "fn": 0}

    def test_all_false_positives(self):
        cm = confusion_matrix([True, True], [False, False])
        assert cm == {"tp": 0, "fp": 2, "tn": 0, "fn": 0}

    def test_all_false_negatives(self):
        cm = confusion_matrix([False, False], [True, True])
        assert cm == {"tp": 0, "fp": 0, "tn": 0, "fn": 2}

    def test_mixed(self):
        preds = [True, False, True, False]
        truth = [True, True, False, False]
        cm = confusion_matrix(preds, truth)
        assert cm == {"tp": 1, "fp": 1, "tn": 1, "fn": 1}


class TestAccuracy:
    def test_perfect(self):
        assert accuracy([True, False], [True, False]) == 1.0

    def test_zero(self):
        assert accuracy([True, True], [False, False]) == 0.0

    def test_half(self):
        assert accuracy([True, False], [False, True]) == 0.0

    def test_empty(self):
        assert accuracy([], []) == 0.0


class TestPrecision:
    def test_perfect(self):
        assert precision([True, True], [True, True]) == 1.0

    def test_zero(self):
        assert precision([True, True], [False, False]) == 0.0

    def test_no_positive_predictions(self):
        assert precision([False, False], [True, True]) == 0.0

    def test_half(self):
        assert precision([True, True], [True, False]) == 0.5


class TestRecall:
    def test_perfect(self):
        assert recall([True, True], [True, True]) == 1.0

    def test_zero(self):
        assert recall([False, False], [True, True]) == 0.0

    def test_no_true_positives_exist(self):
        assert recall([True, True], [False, False]) == 0.0

    def test_half(self):
        assert recall([True, False], [True, True]) == 0.5


class TestF1Score:
    def test_perfect(self):
        assert f1_score([True, True], [True, True]) == 1.0

    def test_zero(self):
        assert f1_score([False, False], [True, True]) == 0.0

    def test_balanced(self):
        # Precision = 0.5, Recall = 1.0 => F1 = 2/3
        preds = [True, True]
        truth = [True, False]
        p = precision(preds, truth)  # 0.5
        r = recall(preds, truth)     # 1.0
        expected = 2 * p * r / (p + r)
        assert f1_score(preds, truth) == pytest.approx(expected)


class TestEvaluateLLMVerdicts:
    def test_with_mock_validator(self):
        """Test evaluation pipeline with a mock validator function."""
        test_cases = [
            {
                "code": "def foo():\n    pass",
                "file_path": "test.py",
                "task": {"id": "t1", "title": "Check docstrings", "description": "Must have docstrings"},
                "expected_compliant": False,
            },
            {
                "code": 'def foo():\n    """Docstring."""\n    pass',
                "file_path": "test.py",
                "task": {"id": "t1", "title": "Check docstrings", "description": "Must have docstrings"},
                "expected_compliant": True,
            },
        ]

        # Mock validator that always says non-compliant
        def mock_validator(payloads, file_rel, code, rag_context=None):
            return [{"internalRef": 0, "compliant": False, "violations": []}]

        results = evaluate_llm_verdicts(test_cases, mock_validator)
        assert results["num_cases"] == 2
        assert "accuracy" in results
        assert "precision" in results
        assert "recall" in results
        assert "f1_score" in results
        assert "confusion_matrix" in results
        assert len(results["per_case"]) == 2

    def test_validator_error_handled(self):
        """Test that validator errors are handled gracefully."""
        test_cases = [
            {
                "code": "x = 1",
                "file_path": "test.py",
                "task": {"id": "t1", "title": "Test", "description": "Test"},
                "expected_compliant": True,
            },
        ]

        def error_validator(payloads, file_rel, code, rag_context=None):
            raise RuntimeError("API error")

        results = evaluate_llm_verdicts(test_cases, error_validator)
        assert results["num_cases"] == 1
        assert results["per_case"][0].get("error") is not None
