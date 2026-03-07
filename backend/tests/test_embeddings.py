"""Tests for the embedding client module."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.embeddings import EmbeddingClient, DEFAULT_EMBEDDING_DIM


class TestEmbeddingClient:
    def test_init_defaults(self):
        client = EmbeddingClient(api_key="test-key")
        assert client.model == "text-embedding-3-small"
        assert client.dimensions == DEFAULT_EMBEDDING_DIM

    def test_init_custom_model(self):
        client = EmbeddingClient(api_key="k", model="text-embedding-3-large", dimensions=3072)
        assert client.model == "text-embedding-3-large"
        assert client.dimensions == 3072

    def test_embed_texts_empty_returns_empty_array(self):
        client = EmbeddingClient(api_key="test-key")
        result = client.embed_texts([])
        assert result.shape == (0, DEFAULT_EMBEDDING_DIM)

    def test_no_api_key_raises(self):
        client = EmbeddingClient(api_key=None)
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                client.embed_texts(["hello"])

    def test_embed_texts_calls_api(self):
        """Test that embed_texts correctly calls the API and parses response."""
        fake_embedding = [0.1] * DEFAULT_EMBEDDING_DIM
        fake_response = {
            "data": [
                {"index": 0, "embedding": fake_embedding},
                {"index": 1, "embedding": fake_embedding},
            ]
        }
        response_bytes = json.dumps(fake_response).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_bytes
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        client = EmbeddingClient(api_key="test-key")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.embed_texts(["hello", "world"])

        assert result.shape == (2, DEFAULT_EMBEDDING_DIM)
        assert result.dtype == np.float32

    def test_embed_query_returns_1d(self):
        """Test that embed_query returns a 1D array."""
        fake_embedding = [0.5] * DEFAULT_EMBEDDING_DIM
        fake_response = {
            "data": [{"index": 0, "embedding": fake_embedding}]
        }
        response_bytes = json.dumps(fake_response).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_bytes
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        client = EmbeddingClient(api_key="test-key")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.embed_query("test query")

        assert result.shape == (DEFAULT_EMBEDDING_DIM,)

    def test_batching_large_input(self):
        """Test that large inputs are batched correctly."""
        fake_embedding = [0.1] * DEFAULT_EMBEDDING_DIM
        call_count = 0

        def mock_urlopen(req, timeout=None):
            nonlocal call_count
            # Parse the request to see how many texts were sent
            body = json.loads(req.data.decode("utf-8"))
            n = len(body["input"])
            call_count += 1
            fake_response = {
                "data": [{"index": i, "embedding": fake_embedding} for i in range(n)]
            }
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        client = EmbeddingClient(api_key="test-key")
        # 600 texts should require 2 batches (batch_size=512)
        texts = [f"text_{i}" for i in range(600)]
        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            result = client.embed_texts(texts)

        assert result.shape == (600, DEFAULT_EMBEDDING_DIM)
        assert call_count == 2  # 512 + 88
