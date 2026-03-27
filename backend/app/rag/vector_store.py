"""FAISS-based vector store for document chunk retrieval.
Supports multiple index types with automatic selection based on size
- **Flat (brute-force)**: 
- **IVF (Inverted File Index)**
- **HNSW (Hierarchical Navigable Small World)**

"""
from __future__ import annotations

import json
import logging
import math
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import faiss
except ImportError:
    faiss = None


class IndexType(str, Enum):
    """FAISS index type selection."""
    FLAT = "flat"       # Exact search, O(n), no training
    IVF = "ivf"         # Cell-probe search, O(n/nlist), requires training
    HNSW = "hnsw"       # Graph-based ANN, O(log n), higher memory
    AUTO = "auto"       # Automatically pick based on corpus size


class VectorStore:
    """In-memory vector store backed by FAISS for similarity search.
    Supports flat, IVF, and HNSW index types with automatic selection.
   """

    # Thresholds for AUTO index type selection
    _IVF_THRESHOLD = 1000      # Switch from flat to IVF at this many vectors
    _HNSW_THRESHOLD = 100_000  # Switch from IVF to HNSW at this many vectors

    def __init__(
        self,
        dimension: int = 1536,
        index_type: IndexType = IndexType.AUTO,
        normalize_l2: bool = True,
        hnsw_m: int = 32,
        hnsw_ef_construction: int = 200,
        hnsw_ef_search: int = 64,
        ivf_nprobe: int = 8,
    ):
        if faiss is None:
            raise ImportError(
                "faiss-cpu is required for the vector store. "
                "Install it with: pip install faiss-cpu"
            )
        self.dimension = dimension
        self.index_type = index_type
        self.normalize_l2 = normalize_l2
        self.hnsw_m = hnsw_m
        self.hnsw_ef_construction = hnsw_ef_construction
        self.hnsw_ef_search = hnsw_ef_search
        self.ivf_nprobe = ivf_nprobe

        # Always start with a flat index; rebuild_index() upgrades later
        self._active_type = IndexType.FLAT
        self.index = faiss.IndexFlatL2(dimension)
        self.metadata: List[Dict[str, Any]] = []
        # Raw vectors kept for IVF training and index rebuilding
        self._raw_vectors: List[np.ndarray] = []

    @property
    def size(self) -> int:
        return self.index.ntotal

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        """L2-normalize vectors so ||v|| = 1. """
        if not self.normalize_l2:
            return vectors
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        # Avoid division by zero for zero vectors
        norms = np.maximum(norms, 1e-12)
        return vectors / norms

    def _build_index(self, index_type: IndexType, vectors: Optional[np.ndarray] = None) -> faiss.Index:
        """Construct a FAISS index of the specified type. """
        if index_type == IndexType.FLAT:
            return faiss.IndexFlatL2(self.dimension)

        elif index_type == IndexType.IVF:
            n_vectors = len(vectors) if vectors is not None else 0
            # nlist (number of clusters) = sqrt(n), clamped to reasonable range.
            # Too few clusters = no speedup; too many = poor recall.
            nlist = max(4, min(int(math.sqrt(n_vectors)), 4096))
            quantizer = faiss.IndexFlatL2(self.dimension)
            index = faiss.IndexIVFFlat(quantizer, self.dimension, nlist)
            index.nprobe = min(self.ivf_nprobe, nlist)
            if vectors is not None and len(vectors) >= nlist:
                logger.info(
                    "Training IVF index with nlist=%d on %d vectors",
                    nlist, len(vectors),
                )
                index.train(vectors)
            return index

        elif index_type == IndexType.HNSW:
            index = faiss.IndexHNSWFlat(self.dimension, self.hnsw_m)
            index.hnsw.efConstruction = self.hnsw_ef_construction
            index.hnsw.efSearch = self.hnsw_ef_search
            return index

        else:
            return faiss.IndexFlatL2(self.dimension)

    def _resolve_auto_type(self, n_vectors: int) -> IndexType:
        """Determine the best index type for a given size."""
        if n_vectors < self._IVF_THRESHOLD:
            return IndexType.FLAT
        elif n_vectors < self._HNSW_THRESHOLD:
            return IndexType.IVF
        else:
            return IndexType.HNSW

    def add(self, embeddings: np.ndarray, metadatas: List[Dict[str, Any]]) -> None:
        """Add vectors with associated metadata. """
        if len(embeddings) == 0:
            return
        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension {embeddings.shape[1]} != store dimension {self.dimension}"
            )
        if len(embeddings) != len(metadatas):
            raise ValueError("Number of embeddings must match number of metadata entries")

        vectors = np.ascontiguousarray(embeddings, dtype=np.float32)
        vectors = self._normalize(vectors)

        # Store raw vectors for potential index rebuilding
        self._raw_vectors.append(vectors.copy())

        self.index.add(vectors)
        self.metadata.extend(metadatas)

    def rebuild_index(self, target_type: Optional[IndexType] = None) -> IndexType:
        """Rebuild the FAISS index with a different index type."""
        if not self._raw_vectors:
            return self._active_type

        all_vectors = np.vstack(self._raw_vectors)
        n = len(all_vectors)

        if target_type is None or target_type == IndexType.AUTO:
            target_type = self._resolve_auto_type(n)

        if target_type == self._active_type and target_type != IndexType.IVF:
            logger.info("Index already using %s, skipping rebuild", target_type.value)
            return target_type

        logger.info(
            "Rebuilding index: %s -> %s (%d vectors)",
            self._active_type.value, target_type.value, n,
        )

        new_index = self._build_index(target_type, vectors=all_vectors)
        new_index.add(all_vectors)
        self.index = new_index
        self._active_type = target_type
        return target_type

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Find the top_k most similar vectors."""
        if self.size == 0:
            return []

        query = np.ascontiguousarray(
            query_vector.reshape(1, -1), dtype=np.float32
        )
        query = self._normalize(query)

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
        """Persist index, metadata, and configuration to disk."""
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(directory / "index.faiss"))
        with open(directory / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        # Save config for proper reconstruction on load
        config = {
            "dimension": self.dimension,
            "index_type": self._active_type.value,
            "normalize_l2": self.normalize_l2,
        }
        with open(directory / "config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.info("Saved vector store (%s, %d vectors) to %s",
                     self._active_type.value, self.size, directory)

    def load(self, directory: Path) -> None:
        """Load index, metadata, and configuration from disk."""
        index_path = directory / "index.faiss"
        meta_path = directory / "metadata.json"
        if not index_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Vector store files not found in {directory}")

        self.index = faiss.read_index(str(index_path))
        self.dimension = self.index.d
        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        # Load config if available
        config_path = directory / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self.normalize_l2 = config.get("normalize_l2", True)
            self._active_type = IndexType(config.get("index_type", "flat"))

        logger.info("Loaded vector store (%s, %d vectors) from %s",
                     self._active_type.value, self.size, directory)

    def clear(self) -> None:
        """Remove all vectors and metadata."""
        self.index = faiss.IndexFlatL2(self.dimension)
        self._active_type = IndexType.FLAT
        self.metadata = []
        self._raw_vectors = []
