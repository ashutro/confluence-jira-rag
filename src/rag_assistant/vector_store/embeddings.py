"""Embedding layer supporting FastEmbed and deterministic MockEmbedder for testing."""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import List, Optional


class BaseEmbedder(ABC):
    """Abstract base class for text embedding models."""

    dimension: int

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for a single string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a batch of strings."""
        pass


class MockEmbedder(BaseEmbedder):
    """Deterministic, zero-dependency embedder using hashed n-grams and L2 normalization.

    Ensures that semantically related texts share high cosine similarity,
    enabling fast, deterministic offline testing and CI/CD without model downloads.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _text_to_vector(self, text: str) -> List[float]:
        """Map text to a deterministic unit-normalized dense vector."""
        vec = [0.0] * self.dimension
        if not text or not text.strip():
            return vec

        # Extract words & sub-word n-grams
        words = re.findall(r"\b\w+\b", text.lower())
        if not words:
            return vec

        # Compute term frequency vector
        for word in words:
            # Word hash
            h_val = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h_val % self.dimension
            vec[idx] += 1.0

            # Character 3-grams
            if len(word) >= 3:
                for i in range(len(word) - 2):
                    ngram = word[i : i + 3]
                    h_ng = int(hashlib.md5(ngram.encode("utf-8")).hexdigest(), 16)
                    idx_ng = h_ng % self.dimension
                    vec[idx_ng] += 0.3

        # L2 Normalize vector
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]

        return vec

    def embed_text(self, text: str) -> List[float]:
        return self._text_to_vector(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._text_to_vector(t) for t in texts]


class FastEmbedder(BaseEmbedder):
    """Fast local text embeddings using FastEmbed (ONNX runtime)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        try:
            from fastembed import TextEmbedding

            self.model_name = model_name
            self._model = TextEmbedding(model_name=model_name)
            # Default dimension for bge-small-en-v1.5 and all-MiniLM-L6-v2 is 384
            self.dimension = 384
        except ImportError:
            raise ImportError(
                "fastembed is not installed. Please install it with `pip install fastembed` "
                "or use MockEmbedder with `--mock`."
            )

    def embed_text(self, text: str) -> List[float]:
        embeddings = list(self._model.embed([text]))
        return [float(x) for x in embeddings[0]]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = list(self._model.embed(texts))
        return [[float(x) for x in emb] for emb in embeddings]


def get_embedder(model_name: Optional[str] = None, use_mock: bool = False) -> BaseEmbedder:
    """Factory function to get an embedding provider."""
    if use_mock:
        return MockEmbedder(dimension=384)

    try:
        return FastEmbedder(model_name=model_name or "BAAI/bge-small-en-v1.5")
    except Exception:
        # Fallback to MockEmbedder if fastembed fails to load (e.g. offline environment)
        return MockEmbedder(dimension=384)
