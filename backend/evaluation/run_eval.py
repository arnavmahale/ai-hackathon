"""End-to-end evaluation runner.

Run with: python -m evaluation.run_eval
from the backend/ directory.

Evaluates both RAG retrieval quality and LLM verdict accuracy.
Uses the EvaluationSuite for comprehensive multi-K retrieval metrics
(Precision, Recall, F1, NDCG at K=1,3,5,10 plus MAP and MRR).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.eval_retrieval import (
    EvaluationSuite,
    RetrievalEvalExample,
    evaluate_retrieval,
)
from evaluation.eval_llm import (
    evaluate_llm_verdicts,
    accuracy,
    precision,
    recall,
    f1_score,
)
from evaluation.eval_data import (
    SAMPLE_DOCUMENTS,
    RETRIEVAL_TEST_QUERIES,
    COMPLIANCE_TEST_CASES,
)


def run_retrieval_eval() -> dict:
    """Evaluate RAG retrieval pipeline using labeled queries."""
    print("\n" + "=" * 60)
    print("RAG RETRIEVAL EVALUATION")
    print("=" * 60)

    from app.rag import Retriever

    retriever = Retriever()

    # Ingest sample documents
    for doc_id, content in SAMPLE_DOCUMENTS.items():
        n = retriever.ingest_document(content, doc_id, metadata={"filename": f"{doc_id}.md"})
        print(f"  Ingested '{doc_id}': {n} chunks")

    print(f"\n  Total vectors in index: {retriever.vector_store.size}")

    # Build evaluation examples
    examples = [
        RetrievalEvalExample(
            query=q["query"],
            relevant_doc_ids=q["relevant_doc_ids"],
            description=q.get("description", ""),
        )
        for q in RETRIEVAL_TEST_QUERIES
    ]

    # Run comprehensive multi-K evaluation
    suite = EvaluationSuite(
        retriever=retriever,
        examples=examples,
        k_values=[1, 3, 5, 10],
    )
    report = suite.run_and_print()

    return report


def run_llm_eval() -> dict:
    """Evaluate LLM compliance verdicts using labeled test cases."""
    print("\n" + "=" * 60)
    print("LLM COMPLIANCE VERDICT EVALUATION")
    print("=" * 60)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  SKIPPED: OPENAI_API_KEY not set")
        return {}

    from validate_code import evaluate_tasks_with_ai

    print(f"  Running {len(COMPLIANCE_TEST_CASES)} test cases...\n")

    results = evaluate_llm_verdicts(COMPLIANCE_TEST_CASES, evaluate_tasks_with_ai)

    print(f"  Accuracy:  {results['accuracy']:.3f}")
    print(f"  Precision: {results['precision']:.3f}")
    print(f"  Recall:    {results['recall']:.3f}")
    print(f"  F1 Score:  {results['f1_score']:.3f}")

    cm = results["confusion_matrix"]
    print(f"\n  Confusion Matrix:")
    print(f"                 Predicted")
    print(f"                 Violation  Compliant")
    print(f"    Actual Viol   TP={cm['tp']:3d}    FN={cm['fn']:3d}")
    print(f"    Actual Comp   FP={cm['fp']:3d}    TN={cm['tn']:3d}")

    print("\n  Per-case breakdown:")
    for pc in results["per_case"]:
        status = "PASS" if pc["correct"] else "FAIL"
        print(f"    [{status}] {pc['task']} on {pc['file_path']}")
        if not pc["correct"]:
            print(f"         Expected: compliant={pc['expected_compliant']}")
            print(f"         Got:      compliant={pc['predicted_compliant']}")
            if pc.get("error"):
                print(f"         Error:    {pc['error']}")

    return results


def main():
    # Load .env file for API keys
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        from validate_code import load_env_file, refresh_openai_settings
        load_env_file(env_path)
        refresh_openai_settings()

    print("Code Guardian Evaluation Suite")
    print("=" * 60)

    retrieval_results = run_retrieval_eval()

    llm_results = run_llm_eval()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if retrieval_results:
        agg = retrieval_results.get("aggregate", {})
        print(f"  RAG Retrieval:  MAP={agg.get('map', 0):.3f}, "
              f"MRR={agg.get('mean_mrr', 0):.3f}, "
              f"NDCG@3={agg.get('mean_ndcg@3', 0):.3f}")
    if llm_results:
        print(f"  LLM Verdicts:   F1={llm_results['f1_score']:.3f}, "
              f"Accuracy={llm_results['accuracy']:.3f}")

    # Save results to file
    output = {
        "retrieval": retrieval_results.get("aggregate", {}) if retrieval_results else {},
        "llm": {k: v for k, v in llm_results.items() if k != "per_case"} if llm_results else {},
    }
    output_path = Path(__file__).parent / "eval_results.json"
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\n  Results saved to {output_path}")


if __name__ == "__main__":
    main()
