"""Tests for the FAISS vector store module."""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

pytestmark = pytest.mark.skipif(not HAS_FAISS, reason="faiss-cpu not installed")

from app.rag.vector_store import VectorStore


class TestVectorStore:
    def test_empty_store(self):
        store = VectorStore(dimension=4)
        assert store.size == 0

    def test_add_and_search(self):
        store = VectorStore(dimension=4)
        embeddings = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ], dtype=np.float32)
        metadatas = [
            {"text": "doc about security", "doc_id": "sec"},
            {"text": "doc about testing", "doc_id": "test"},
            {"text": "doc about naming", "doc_id": "name"},
        ]
        store.add(embeddings, metadatas)
        assert store.size == 3

        # Query closest to first vector
        query = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)
        results = store.search(query, top_k=2)
        assert len(results) == 2
        assert results[0]["doc_id"] == "sec"  # closest to [1,0,0,0]

    def test_search_empty_store_returns_empty(self):
        store = VectorStore(dimension=4)
        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = store.search(query, top_k=5)
        assert results == []

    def test_search_score_threshold(self):
        store = VectorStore(dimension=4)
        embeddings = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float32)
        metadatas = [{"doc_id": "close"}, {"doc_id": "far"}]
        store.add(embeddings, metadatas)

        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        # Very tight threshold — should only return exact match
        results = store.search(query, top_k=5, score_threshold=0.01)
        assert len(results) == 1
        assert results[0]["doc_id"] == "close"

    def test_top_k_limits_results(self):
        store = VectorStore(dimension=4)
        embeddings = np.random.randn(10, 4).astype(np.float32)
        metadatas = [{"doc_id": f"doc_{i}"} for i in range(10)]
        store.add(embeddings, metadatas)

        query = np.random.randn(4).astype(np.float32)
        results = store.search(query, top_k=3)
        assert len(results) == 3

    def test_results_have_score_and_rank(self):
        store = VectorStore(dimension=4)
        embeddings = np.eye(4, dtype=np.float32)
        metadatas = [{"doc_id": f"doc_{i}"} for i in range(4)]
        store.add(embeddings, metadatas)

        query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = store.search(query, top_k=4)
        for r in results:
            assert "score" in r
            assert "rank" in r
        # Scores should be non-decreasing (L2 distance)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores)

    def test_dimension_mismatch_raises(self):
        store = VectorStore(dimension=4)
        wrong_dim = np.random.randn(2, 8).astype(np.float32)
        with pytest.raises(ValueError, match="dimension"):
            store.add(wrong_dim, [{"doc_id": "a"}, {"doc_id": "b"}])

    def test_metadata_count_mismatch_raises(self):
        store = VectorStore(dimension=4)
        embeddings = np.random.randn(3, 4).astype(np.float32)
        with pytest.raises(ValueError, match="must match"):
            store.add(embeddings, [{"doc_id": "a"}])

    def test_add_empty_is_noop(self):
        store = VectorStore(dimension=4)
        store.add(np.array([]).reshape(0, 4), [])
        assert store.size == 0

    def test_save_and_load(self):
        store = VectorStore(dimension=4)
        embeddings = np.array([[1.0, 2.0, 3.0, 4.0]], dtype=np.float32)
        metadatas = [{"doc_id": "test", "text": "hello"}]
        store.add(embeddings, metadatas)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_dir = Path(tmpdir)
            store.save(save_dir)

            # Load into new store
            store2 = VectorStore(dimension=4)
            store2.load(save_dir)
            assert store2.size == 1
            assert store2.metadata[0]["doc_id"] == "test"

            # Search should work on loaded store
            query = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
            results = store2.search(query, top_k=1)
            assert len(results) == 1
            assert results[0]["doc_id"] == "test"

    def test_load_missing_files_raises(self):
        store = VectorStore(dimension=4)
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                store.load(Path(tmpdir))

    def test_clear(self):
        store = VectorStore(dimension=4)
        embeddings = np.random.randn(5, 4).astype(np.float32)
        metadatas = [{"doc_id": f"doc_{i}"} for i in range(5)]
        store.add(embeddings, metadatas)
        assert store.size == 5

        store.clear()
        assert store.size == 0
        assert store.metadata == []
