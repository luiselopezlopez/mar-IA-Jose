"""Hybrid retrieval and re-ranking utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from langchain.retrievers import BM25Retriever
from langchain.schema import Document

from .config import RetrievalConfig
from .embeddings import EmbeddingGenerator
from .schemas import RetrievedChunk
from .vector_store import AcademicVectorStore

try:  # pragma: no cover - optional dependency
    from sentence_transformers import CrossEncoder
except Exception:  # pragma: no cover - optional
    CrossEncoder = None  # type: ignore[assignment]


@dataclass
class RetrievedDocument:
    document: Document
    score: float


class HybridRetriever:
    """Combine semantic, lexical, and cross-encoder ranking for retrieval."""

    def __init__(
        self,
        config: RetrievalConfig,
        vector_store: AcademicVectorStore,
        embedding_generator: EmbeddingGenerator,
    ) -> None:
        self.config = config
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator

        documents = vector_store.documents if vector_store.config.provider == "memory" else []
        self.lexical_retriever = (
            BM25Retriever.from_documents(documents) if documents else None
        )
        if self.lexical_retriever:
            self.lexical_retriever.k = config.top_k_lexical
        self.reranker = CrossEncoder(config.reranker_model) if CrossEncoder else None

    def refresh_lexical_corpus(self, documents: Iterable[Document]) -> None:
        """Rebuild the BM25 index with the provided documents."""

        docs = list(documents)
        self.lexical_retriever = BM25Retriever.from_documents(docs) if docs else None
        if self.lexical_retriever:
            self.lexical_retriever.k = self.config.top_k_lexical

    def _lexical_search(self, query: str) -> List[RetrievedChunk]:
        if not self.lexical_retriever:
            return []
        docs = self.lexical_retriever.get_relevant_documents(query)
        return [RetrievedChunk(text=doc.page_content, score=1.0, metadata=doc.metadata) for doc in docs]

    def _semantic_search(self, query: str) -> List[RetrievedChunk]:
        query_vector = self.embedding_generator.embed_query(query)
        return self.vector_store.similarity_search(query_vector, top_k=self.config.top_k_semantic)

    def _rerank(self, query: str, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        if not self.reranker or not chunks:
            return chunks[: self.config.top_k_final]

        pairs = [[query, chunk.text] for chunk in chunks]
        scores = self.reranker.predict(pairs)
        reranked = sorted(zip(chunks, scores, strict=True), key=lambda item: item[1], reverse=True)
        return [chunk for chunk, _ in reranked[: self.config.top_k_final]]

    def retrieve(self, query: str) -> List[RetrievedChunk]:
        """Return the top-ranked chunks for the provided query."""

        semantic_results = self._semantic_search(query)
        lexical_results = self._lexical_search(query)
        combined = {chunk.metadata.get("segment_id", chunk.text): chunk for chunk in semantic_results}

        for chunk in lexical_results:
            key = chunk.metadata.get("segment_id", chunk.text)
            if key not in combined:
                combined[key] = chunk

        combined_list = list(combined.values())
        return self._rerank(query, combined_list)
