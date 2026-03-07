"""Retriever: orchestrates chunking, embedding, storage, and query.

This is the main entry point for the RAG pipeline. It handles:
1. Ingesting documents (chunk -> embed -> store)
2. Querying relevant context for code sections
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .chunker import Chunk, chunk_document, extract_sections
from .embeddings import EmbeddingClient
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """End-to-end RAG retriever for compliance document search."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
        dimension: int = 1536,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.embedding_client = EmbeddingClient(
            api_key=api_key,
            model=embedding_model,
            dimensions=dimension,
        )
        self.vector_store = VectorStore(dimension=dimension)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._chunks: List[Chunk] = []

    @property
    def document_count(self) -> int:
        return len(set(c.doc_id for c in self._chunks))

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def ingest_document(
        self,
        text: str,
        doc_id: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """Chunk and embed a document, adding it to the vector store.

        Args:
            text: Full document text.
            doc_id: Unique document identifier.
            metadata: Extra metadata for all chunks.

        Returns:
            Number of chunks created.
        """
        chunks = chunk_document(
            text=text,
            doc_id=doc_id,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            metadata=metadata,
        )
        if not chunks:
            logger.warning("No chunks produced for document %s", doc_id)
            return 0

        texts = [c.text for c in chunks]
        embeddings = self.embedding_client.embed_texts(texts)

        metadatas = [
            {
                "text": c.text,
                "doc_id": c.doc_id,
                "chunk_index": c.chunk_index,
                **c.metadata,
            }
            for c in chunks
        ]
        self.vector_store.add(embeddings, metadatas)
        self._chunks.extend(chunks)

        logger.info("Ingested %d chunks from document %s", len(chunks), doc_id)
        return len(chunks)

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve the most relevant document chunks for a query.

        Args:
            query_text: The search query (e.g., a code snippet or task description).
            top_k: Number of results to return.
            score_threshold: Maximum L2 distance threshold.

        Returns:
            List of result dicts with text, doc_id, score, etc.
        """
        if self.vector_store.size == 0:
            return []

        query_embedding = self.embedding_client.embed_query(query_text)
        results = self.vector_store.search(
            query_embedding,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        return results

    def query_for_code(
        self,
        code: str,
        task_description: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant compliance docs for a code + task combination.

        Constructs a combined query from the task description and a code summary,
        then retrieves the most relevant document chunks.

        Args:
            code: Source code to find relevant docs for.
            task_description: The compliance task being checked.
            top_k: Number of chunks to retrieve.

        Returns:
            List of relevant document chunks with metadata.
        """
        # Build a combined query that captures both the task and code context
        code_preview = code[:500] if len(code) > 500 else code
        combined_query = (
            f"Compliance requirement: {task_description}\n\n"
            f"Code context:\n{code_preview}"
        )
        return self.query(combined_query, top_k=top_k)

    def save(self, directory: Path) -> None:
        """Persist the vector store to disk."""
        self.vector_store.save(directory)

    def load(self, directory: Path) -> None:
        """Load a persisted vector store from disk."""
        self.vector_store.load(directory)

    def clear(self) -> None:
        """Remove all ingested documents."""
        self.vector_store.clear()
        self._chunks = []
