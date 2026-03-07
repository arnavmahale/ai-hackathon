"""Evaluation metrics for LLM compliance verdict accuracy.

Compares LLM-generated compliance verdicts against a labeled dataset
of code + expected violations.

Key metrics:
- Accuracy: fraction of correct verdicts (compliant vs non-compliant)
- Precision: true positives / (true positives + false positives)
- Recall: true positives / (true positives + false negatives)
- F1 Score: harmonic mean of precision and recall
- Confusion matrix: TP, FP, TN, FN counts
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def confusion_matrix(
    predictions: List[bool],
    ground_truth: List[bool],
) -> Dict[str, int]:
    """Compute confusion matrix for binary classification.

    True = violation detected (non-compliant)
    False = compliant

    Args:
        predictions: LLM predicted verdicts (True = violation).
        ground_truth: Expected verdicts (True = violation).

    Returns:
        Dict with TP, FP, TN, FN counts.
    """
    tp = fp = tn = fn = 0
    for pred, truth in zip(predictions, ground_truth):
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif not pred and not truth:
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def accuracy(predictions: List[bool], ground_truth: List[bool]) -> float:
    """Fraction of correct predictions."""
    if not predictions:
        return 0.0
    correct = sum(1 for p, g in zip(predictions, ground_truth) if p == g)
    return correct / len(predictions)


def precision(predictions: List[bool], ground_truth: List[bool]) -> float:
    """Precision: TP / (TP + FP). Returns 0.0 if no positive predictions."""
    cm = confusion_matrix(predictions, ground_truth)
    denom = cm["tp"] + cm["fp"]
    return cm["tp"] / denom if denom > 0 else 0.0


def recall(predictions: List[bool], ground_truth: List[bool]) -> float:
    """Recall: TP / (TP + FN). Returns 0.0 if no true positives exist."""
    cm = confusion_matrix(predictions, ground_truth)
    denom = cm["tp"] + cm["fn"]
    return cm["tp"] / denom if denom > 0 else 0.0


def f1_score(predictions: List[bool], ground_truth: List[bool]) -> float:
    """F1 score: harmonic mean of precision and recall."""
    p = precision(predictions, ground_truth)
    r = recall(predictions, ground_truth)
    if p + r == 0:
        return 0.0
    return 2 * (p * r) / (p + r)


def evaluate_llm_verdicts(
    test_cases: List[Dict[str, Any]],
    validator_fn,
) -> Dict[str, Any]:
    """Run LLM evaluation over labeled test cases.

    Each test case dict must have:
        - "code": str — source code to evaluate
        - "file_path": str — relative file path
        - "task": dict — task definition (id, title, description, etc.)
        - "expected_compliant": bool — ground truth compliance status

    Args:
        test_cases: List of labeled test case dicts.
        validator_fn: Callable(task_payloads, file_rel, code) -> List[dict]
            that returns AI task results with 'compliant' field.

    Returns:
        Dict with aggregate metrics and per-case results.
    """
    predictions = []
    ground_truth = []
    per_case = []

    for case in test_cases:
        code = case["code"]
        file_path = case["file_path"]
        task = case["task"]
        expected = case["expected_compliant"]

        task_payload = {
            "internalRef": 0,
            "name": task.get("title", task.get("name", "task")),
            "description": task.get("description", ""),
            **{k: v for k, v in task.items() if k not in ("title", "name", "description")},
        }

        try:
            results = validator_fn([task_payload], file_path, code)
            if results and isinstance(results, list):
                predicted_compliant = bool(results[0].get("compliant", True))
            else:
                predicted_compliant = True  # default to compliant if no result
        except Exception as exc:
            predicted_compliant = True  # assume compliant on error
            per_case.append({
                "file_path": file_path,
                "task": task.get("title", task.get("id")),
                "expected_compliant": expected,
                "predicted_compliant": None,
                "correct": False,
                "error": str(exc),
            })
            # For metrics, treat as violation not detected
            predictions.append(False)
            ground_truth.append(not expected)
            continue

        # Convert: violation detected = True
        pred_violation = not predicted_compliant
        true_violation = not expected

        predictions.append(pred_violation)
        ground_truth.append(true_violation)

        per_case.append({
            "file_path": file_path,
            "task": task.get("title", task.get("id")),
            "expected_compliant": expected,
            "predicted_compliant": predicted_compliant,
            "correct": predicted_compliant == expected,
        })

    cm = confusion_matrix(predictions, ground_truth)
    return {
        "num_cases": len(test_cases),
        "accuracy": accuracy(predictions, ground_truth),
        "precision": precision(predictions, ground_truth),
        "recall": recall(predictions, ground_truth),
        "f1_score": f1_score(predictions, ground_truth),
        "confusion_matrix": cm,
        "per_case": per_case,
    }
