"""Configuration objects for the academic RAG pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence


VectorProvider = Literal["pinecone", "weaviate", "memory"]


@dataclass
class EmbeddingConfig:
    """Settings for the embedding stage."""

    model_name: str = "text-embedding-ada-002"
    batch_size: int = 32
    max_retries: int = 3


@dataclass
class VectorStoreConfig:
    """Settings required to connect to the vector store."""

    provider: VectorProvider = "pinecone"
    index_name: str = "academic-rag-index"
    namespace: str = "default"
    dim: Optional[int] = None
    environment: Optional[str] = field(
        default=None,
        metadata={"description": "Pinecone environment or Weaviate cluster URL"},
    )
    api_key_env: str = "PINECONE_API_KEY"
    text_field: str = "text"

    def api_key(self) -> Optional[str]:
        """Return the API key defined in the configured environment variable."""

        return os.getenv(self.api_key_env)


@dataclass
class SegmenterConfig:
    """Parameters for the segmentation stage."""

    overlap_ratio: float = 0.18
    max_words: int = 280
    language: str = "es"
    abbreviation_map: Sequence[tuple[str, str]] = (
        ("p.ej.", "por ejemplo"),
        ("ej.", "ejemplo"),
        ("aprox.", "aproximadamente"),
        ("etc.", "etcetera"),
    )


@dataclass
class RetrievalConfig:
    """Parameters for hybrid retrieval and re-ranking."""

    top_k_semantic: int = 12
    top_k_lexical: int = 12
    top_k_final: int = 6
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@dataclass
class PromptConfig:
    """Settings for prompt construction."""

    cite_sources: bool = True
    system_instruction: str = (
        "Eres un asistente experto en documentación académica. Responde únicamente "
        "con la información proporcionada en el contexto y cita las fuentes con "
        "el formato [Fuente X]."
    )


@dataclass
class PipelineConfig:
    """Aggregate configuration for the full pipeline."""

    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)
    segmenter: SegmenterConfig = field(default_factory=SegmenterConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
    lexical_corpus_path: str = "data/lexical_corpus.json"
    default_metadata: dict[str, str] = field(
        default_factory=lambda: {
            "source": "unknown",
            "document_type": "academic",
        }
    )
