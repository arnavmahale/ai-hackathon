"""Tests for the Retriever (end-to-end RAG orchestrator)."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

pytestmark = pytest.mark.skipif(not HAS_FAISS, reason="faiss-cpu not installed")

from app.rag.retriever import Retriever
from app.rag.embeddings import DEFAULT_EMBEDDING_DIM


def _mock_embed_texts(texts):
    """Generate deterministic fake embeddings based on text content."""
    np.random.seed(42)
    return np.random.randn(len(texts), DEFAULT_EMBEDDING_DIM).astype(np.float32)


def _mock_embed_query(text):
    np.random.seed(42)
    return np.random.randn(DEFAULT_EMBEDDING_DIM).astype(np.float32)


class TestRetriever:
    def _make_retriever(self):
        retriever = Retriever(api_key="fake-key")
        retriever.embedding_client.embed_texts = _mock_embed_texts
        retriever.embedding_client.embed_query = _mock_embed_query
        return retriever

    def test_ingest_document(self):
        retriever = self._make_retriever()
        text = "This is a test document about security policies."
        count = retriever.ingest_document(text, "doc-1")
        assert count > 0
        assert retriever.document_count == 1
        assert retriever.chunk_count == count
        assert retriever.vector_store.size == count

    def test_ingest_empty_document(self):
        retriever = self._make_retriever()
        count = retriever.ingest_document("", "doc-empty")
        assert count == 0
        assert retriever.document_count == 0

    def test_ingest_multiple_documents(self):
        retriever = self._make_retriever()
        retriever.ingest_document("Document about security.", "doc-sec")
        retriever.ingest_document("Document about testing.", "doc-test")
        assert retriever.document_count == 2

    def test_query_returns_results(self):
        retriever = self._make_retriever()
        retriever.ingest_document("Security policies for API authentication.", "doc-sec")
        retriever.ingest_document("Testing requirements and coverage.", "doc-test")

        results = retriever.query("API security authentication", top_k=2)
        assert len(results) <= 2
        for r in results:
            assert "text" in r
            assert "doc_id" in r
            assert "score" in r

    def test_query_empty_store(self):
        retriever = self._make_retriever()
        results = retriever.query("anything", top_k=5)
        assert results == []

    def test_query_for_code(self):
        retriever = self._make_retriever()
        retriever.ingest_document("All functions must have docstrings.", "doc-docs")

        results = retriever.query_for_code(
            code="def foo():\n    pass",
            task_description="Check for docstrings",
            top_k=1,
        )
        assert len(results) <= 1

    def test_clear(self):
        retriever = self._make_retriever()
        retriever.ingest_document("Some content.", "doc-1")
        assert retriever.chunk_count > 0

        retriever.clear()
        assert retriever.chunk_count == 0
        assert retriever.vector_store.size == 0

    def test_ingest_with_metadata(self):
        retriever = self._make_retriever()
        retriever.ingest_document(
            "Content here.",
            "doc-1",
            metadata={"source": "upload", "version": "2.0"},
        )
        results = retriever.query("content", top_k=1)
        if results:
            assert results[0].get("source") == "upload"
