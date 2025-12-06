"""Utilities for building a modular Retrieval-Augmented Generation (RAG) pipeline.

The package exposes the main pipeline object and configuration helpers so that
other modules in the project can orchestrate ingestion and question answering
workflows programmatically.
"""

from .config import EmbeddingConfig, PipelineConfig, VectorStoreConfig
from .pipeline import RAGPipeline
from .schemas import PipelineResponse, RetrievedChunk, Segment

__all__ = [
    "EmbeddingConfig",
    "PipelineConfig",
    "VectorStoreConfig",
    "RAGPipeline",
    "PipelineResponse",
    "RetrievedChunk",
    "Segment",
]
