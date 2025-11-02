"""Embedding generation utilities."""

from __future__ import annotations

import time
from typing import Iterable, List

from langchain_openai import OpenAIEmbeddings

from .config import EmbeddingConfig
from .schemas import Segment


class EmbeddingGenerator:
    """Generate vector representations for document segments."""

    def __init__(self, config: EmbeddingConfig, embeddings: OpenAIEmbeddings | None = None):
        self.config = config
        self._client = embeddings or OpenAIEmbeddings(model=config.model_name)

    def embed_segments(self, segments: Iterable[Segment]) -> List[tuple[Segment, List[float]]]:
        """Return embeddings for the provided segments."""

        segment_list = list(segments)
        vectors: List[tuple[Segment, List[float]]] = []

        for start in range(0, len(segment_list), self.config.batch_size):
            batch = segment_list[start : start + self.config.batch_size]
            texts = [segment.text for segment in batch]
            attempt = 0
            while True:
                try:
                    embeddings = self._client.embed_documents(texts)
                    break
                except Exception:  # pragma: no cover - retries
                    attempt += 1
                    if attempt >= self.config.max_retries:
                        raise
                    time.sleep(2**attempt)
            for segment, vector in zip(batch, embeddings, strict=True):
                vectors.append((segment, vector))
        return vectors

    def embed_query(self, query: str) -> List[float]:
        """Return the embedding for a single query string."""

        attempt = 0
        while True:
            try:
                return self._client.embed_query(query)
            except Exception:  # pragma: no cover - retries
                attempt += 1
                if attempt >= self.config.max_retries:
                    raise
                time.sleep(2**attempt)
