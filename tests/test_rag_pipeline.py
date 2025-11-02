"""Unit tests for the academic RAG pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence

import pytest

from rag_pipeline.config import (
    EmbeddingConfig,
    PipelineConfig,
    PromptConfig,
    RetrievalConfig,
    SegmenterConfig,
    VectorStoreConfig,
)
from rag_pipeline.ingestion import load_document
from rag_pipeline.llm import build_pipeline_response
from rag_pipeline.pipeline import RAGPipeline
from rag_pipeline.preprocess import preprocess_document
from rag_pipeline.prompt import build_prompt
from rag_pipeline.schemas import RetrievedChunk, Segment
from rag_pipeline.segment import DocumentSegmenter
from rag_pipeline.vector_store import AcademicVectorStore


class DummyEmbeddingGenerator:
    """Deterministic embedding generator for tests."""

    def __init__(self, dimension: int = 4) -> None:
        self.dimension = dimension

    def _embed_text(self, text: str) -> List[float]:
        tokens = text.split()
        length = len(text)
        avg_len = sum(len(token) for token in tokens) / max(len(tokens), 1)
        digits = sum(char.isdigit() for char in text)
        vocab_sum = sum(ord(char) for char in text) % 1000
        return [length / 1000, avg_len / 10, digits / 10, vocab_sum / 1000]

    def embed_segments(self, segments: Iterable[Segment]) -> List[tuple[Segment, Sequence[float]]]:
        return [(segment, self._embed_text(segment.text)) for segment in segments]

    def embed_query(self, query: str) -> List[float]:
        return self._embed_text(query)


class DummyLLMClient:
    """LLM stub that mirrors the prompt and chunk count."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    def generate(self, prompt: str, chunks: List[RetrievedChunk]) -> str:
        self.calls.append(prompt)
        return f"Respuesta de prueba con {len(chunks)} fragmentos."


@pytest.fixture()
def sample_text(tmp_path: Path) -> Path:
    content = (
        "CAPITULO 1: Introducción\n"
        "Universidad Ejemplo\n"
        "Página 1\n"
        "El aprendizaje automático es un campo de la inteligencia artificial.\n"
        "Este texto contiene definiciones importantes y números como 2025.\n"
        "CAPITULO 2: Marco teórico\n"
        "La regresión logística es un modelo estadístico clásico.\n"
    )
    file_path = tmp_path / "documento.txt"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_load_document(sample_text: Path) -> None:
    document = load_document(sample_text)
    assert document.text
    assert document.metadata["file_name"].endswith(".txt")


def test_preprocess_document_removes_headers(sample_text: Path) -> None:
    document = load_document(sample_text)
    config = SegmenterConfig()
    processed = preprocess_document(document, config)
    assert "Universidad Ejemplo" not in processed.text
    assert processed.metadata["preprocessed"] is True


def test_segmenter_creates_segments(sample_text: Path) -> None:
    document = load_document(sample_text)
    config = SegmenterConfig(max_words=40, overlap_ratio=0.2)
    processed = preprocess_document(document, config)
    segmenter = DocumentSegmenter(config, spacy_model="__dummy__")
    segments = segmenter.segment(processed)
    assert segments
    assert segments[0].metadata["data_type"] in {"text", "table", "formula", "list"}


def test_vector_store_memory_similarity(sample_text: Path) -> None:
    document = load_document(sample_text)
    config = SegmenterConfig(max_words=40, overlap_ratio=0.2)
    processed = preprocess_document(document, config)
    segmenter = DocumentSegmenter(config, spacy_model="__dummy__")
    segments = segmenter.segment(processed)

    vector_config = VectorStoreConfig(provider="memory", dim=4)
    store = AcademicVectorStore(vector_config)
    embeddings = DummyEmbeddingGenerator().embed_segments(segments)
    store.add_embeddings(embeddings)

    query_vector = DummyEmbeddingGenerator().embed_query("¿Qué es la regresión logística?")
    results = store.similarity_search(query_vector, top_k=2)
    assert len(results) <= 2
    assert any("regresión logística" in chunk.text for chunk in results)


def test_prompt_builder_formats_sources(sample_text: Path) -> None:
    document = load_document(sample_text)
    config = SegmenterConfig(max_words=40, overlap_ratio=0.2)
    processed = preprocess_document(document, config)
    segmenter = DocumentSegmenter(config, spacy_model="__dummy__")
    segments = segmenter.segment(processed)[:2]
    chunks = [
        RetrievedChunk(text=segment.text, score=1.0, metadata=segment.metadata)
        for segment in segments
    ]
    prompt = build_prompt("¿Qué es el aprendizaje automático?", chunks, PromptConfig())
    assert "Fuente 1" in prompt
    assert "contexto" in prompt.lower()


def test_pipeline_end_to_end(sample_text: Path) -> None:
    pipeline_config = PipelineConfig(
        embedding=EmbeddingConfig(),
        vector_store=VectorStoreConfig(provider="memory", dim=4),
        segmenter=SegmenterConfig(max_words=40, overlap_ratio=0.2),
        retrieval=RetrievalConfig(top_k_semantic=3, top_k_lexical=3, top_k_final=2),
        prompt=PromptConfig(),
    )

    dummy_embeddings = DummyEmbeddingGenerator()
    dummy_llm = DummyLLMClient()
    segmenter = DocumentSegmenter(pipeline_config.segmenter, spacy_model="__dummy__")
    pipeline = RAGPipeline(
        config=pipeline_config,
        embedding_generator=dummy_embeddings,
        llm_client=dummy_llm,
        segmenter=segmenter,
    )

    pipeline.ingest([sample_text])
    response = pipeline.answer("¿Qué es la regresión logística?")

    assert "Respuesta de prueba" in response.answer
    assert response.references
    assert dummy_llm.calls, "LLM debe ser invocado"


def test_build_pipeline_response() -> None:
    chunks = [
        RetrievedChunk(
            text="Ejemplo",
            score=0.9,
            metadata={"source": "doc", "section_index": 1, "data_type": "text"},
        )
    ]
    response = build_pipeline_response("respuesta", "prompt", chunks)
    assert response.answer == "respuesta"
    assert response.references[0]["label"] == "Fuente 1"
