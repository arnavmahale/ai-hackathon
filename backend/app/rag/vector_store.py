"""FAISS-based vector store for document chunk retrieval.

Stores embeddings in a flat L2 index with metadata for each vector.
Supports save/load to disk for persistence.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import faiss
except ImportError:
    faiss = None


class VectorStore:
    """In-memory vector store backed by FAISS for similarity search."""

    def __init__(self, dimension: int = 1536):
        if faiss is None:
            raise ImportError(
                "faiss-cpu is required for the vector store. "
                "Install it with: pip install faiss-cpu"
            )
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self.metadata: List[Dict[str, Any]] = []

    @property
    def size(self) -> int:
        return self.index.ntotal

    def add(self, embeddings: np.ndarray, metadatas: List[Dict[str, Any]]) -> None:
        """Add vectors with associated metadata.

        Args:
            embeddings: Array of shape (n, dimension).
            metadatas: List of metadata dicts, one per vector.
        """
        if len(embeddings) == 0:
            return
        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension {embeddings.shape[1]} != store dimension {self.dimension}"
            )
        if len(embeddings) != len(metadatas):
            raise ValueError("Number of embeddings must match number of metadata entries")

        vectors = np.ascontiguousarray(embeddings, dtype=np.float32)
        self.index.add(vectors)
        self.metadata.extend(metadatas)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Find the top_k most similar vectors.

        Args:
            query_vector: 1D array of shape (dimension,).
            top_k: Number of results to return.
            score_threshold: Maximum L2 distance to include (lower = more similar).

        Returns:
            List of dicts with keys: score, rank, and all metadata fields.
        """
        if self.size == 0:
            return []

        query = np.ascontiguousarray(
            query_vector.reshape(1, -1), dtype=np.float32
        )
        k = min(top_k, self.size)
        distances, indices = self.index.search(query, k)

        results = []
        for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:
                continue
            if score_threshold is not None and dist > score_threshold:
                continue
            result = {
                **self.metadata[idx],
                "score": float(dist),
                "rank": rank,
            }
            results.append(result)

        return results

    def save(self, directory: Path) -> None:
        """Persist index and metadata to disk."""
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(directory / "index.faiss"))
        with open(directory / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        logger.info("Saved vector store with %d vectors to %s", self.size, directory)

    def load(self, directory: Path) -> None:
        """Load index and metadata from disk."""
        index_path = directory / "index.faiss"
        meta_path = directory / "metadata.json"
        if not index_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Vector store files not found in {directory}")

        self.index = faiss.read_index(str(index_path))
        self.dimension = self.index.d
        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
        logger.info("Loaded vector store with %d vectors from %s", self.size, directory)

    def clear(self) -> None:
        """Remove all vectors and metadata."""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []
