"""Shared dataclasses used across the RAG pipeline modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class RawDocument:
    """Represents a source document before any preprocessing."""

    doc_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Segment:
    """Represents a processed textual segment ready for embedding."""

    segment_id: str
    text: str
    metadata: Dict[str, Any]
    source_document_id: str


@dataclass(slots=True)
class RetrievedChunk:
    """Container for a chunk returned by the retriever."""

    text: str
    score: float
    metadata: Dict[str, Any]


@dataclass(slots=True)
class PipelineResponse:
    """Final answer returned by the RAG pipeline query stage."""

    answer: str
    prompt: str
    references: List[Dict[str, Any]]
