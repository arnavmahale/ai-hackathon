"""Embedding client for generating vector representations of text.

Uses OpenAI's text-embedding-3-small model by default.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIM = 1536
OPENAI_EMBEDDING_URL = "https://api.openai.com/v1/embeddings"


class EmbeddingClient:
    """Generates embeddings via OpenAI API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimensions: int = DEFAULT_EMBEDDING_DIM,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embed a batch of texts into vectors.

        Args:
            texts: List of strings to embed.

        Returns:
            numpy array of shape (len(texts), dimensions).
        """
        if not texts:
            return np.array([]).reshape(0, self.dimensions)

        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for generating embeddings.")

        # OpenAI batch limit is 2048 texts; split if needed
        all_embeddings = []
        batch_size = 512
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = self._call_api(batch)
            all_embeddings.extend(embeddings)

        return np.array(all_embeddings, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string.

        Returns:
            1D numpy array of shape (dimensions,).
        """
        result = self.embed_texts([query])
        return result[0]

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        payload = {
            "model": self.model,
            "input": texts,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            OPENAI_EMBEDDING_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")
            raise RuntimeError(f"Embedding API error {exc.code}: {detail}") from exc

        # Sort by index to maintain order
        data_items = sorted(body["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in data_items]
