"""Vector store adapters for Pinecone, Weaviate, and in-memory usage."""

from __future__ import annotations

from importlib import import_module
from typing import Iterable, List, Sequence

import numpy as np
from langchain.docstore.document import Document

from .config import VectorStoreConfig
from .schemas import RetrievedChunk, Segment

try:  # pragma: no cover - optional dependency
    from langchain.vectorstores import Pinecone as PineconeVectorStore
except Exception:  # pragma: no cover - optional
    PineconeVectorStore = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from langchain.vectorstores import Weaviate as WeaviateVectorStore
except Exception:  # pragma: no cover - optional
    WeaviateVectorStore = None  # type: ignore[assignment]
class AcademicVectorStore:
    """Abstraction layer over different vector store providers."""

    def __init__(self, config: VectorStoreConfig, embedding_function=None):
        self.config = config
        self._memory_vectors: np.ndarray | None = None
        self._memory_documents: List[Document] = []
        self._vector_store = None
        self._embedding_function = embedding_function

        if config.provider == "pinecone":
            if PineconeVectorStore is None:
                raise RuntimeError("Pinecone no está disponible en el entorno actual")
            pinecone_module = import_module("pinecone")
            self._vector_store = PineconeVectorStore.from_existing_index(
                index_name=config.index_name,
                namespace=config.namespace,
                embedding=embedding_function,
                pinecone_api_key=config.api_key(),
                pinecone_environment=config.environment,
            )
        elif config.provider == "weaviate":
            if WeaviateVectorStore is None:
                raise RuntimeError("Weaviate no está disponible en el entorno actual")
            weaviate_module = import_module("weaviate")
            client = weaviate_module.Client(
                url=config.environment,
                auth_client_secret=weaviate_module.AuthApiKey(api_key=config.api_key()),
            )
            self._vector_store = WeaviateVectorStore(
                client,
                index_name=config.index_name,
                text_key=config.text_field,
                embedding=embedding_function,
            )
        elif config.provider == "memory":
            self._memory_vectors = np.zeros((0, config.dim or 1536), dtype="float32")
        else:  # pragma: no cover - guard
            raise ValueError(f"Proveedor desconocido: {config.provider}")

    def add_embeddings(self, items: Iterable[tuple[Segment, Sequence[float]]]) -> None:
        """Persist embeddings and metadata in the configured store."""

        if self.config.provider == "memory":
            self._add_memory(items)
        else:
            texts = []
            metadatas = []
            ids = []
            for segment, _vector in items:
                texts.append(segment.text)
                metadatas.append(
                    {
                        **segment.metadata,
                        "segment_id": segment.segment_id,
                        "source_document_id": segment.source_document_id,
                    }
                )
                ids.append(segment.segment_id)
            self._vector_store.add_texts(texts, metadatas=metadatas, ids=ids)

    def _add_memory(self, items: Iterable[tuple[Segment, Sequence[float]]]) -> None:
        items_list = list(items)
        if not items_list:
            return

        vectors = np.array([vector for _, vector in items_list], dtype="float32")
        documents = [
            Document(
                page_content=segment.text,
                metadata={
                    **segment.metadata,
                    "segment_id": segment.segment_id,
                    "source_document_id": segment.source_document_id,
                },
            )
            for segment, _ in items_list
        ]

        if self._memory_vectors is None or self._memory_vectors.size == 0:
            self._memory_vectors = vectors
        else:
            self._memory_vectors = np.vstack([self._memory_vectors, vectors])
        self._memory_documents.extend(documents)

    def similarity_search(self, query_embedding: Sequence[float], top_k: int) -> List[RetrievedChunk]:
        """Return the top-k semantically similar chunks."""

        if self.config.provider == "memory":
            if self._memory_vectors is None or not len(self._memory_documents):
                return []
            query_vec = np.array(query_embedding, dtype="float32")
            doc_matrix = self._memory_vectors
            norms = np.linalg.norm(doc_matrix, axis=1) * (np.linalg.norm(query_vec) + 1e-12)
            similarities = (doc_matrix @ query_vec) / norms
            top_indices = np.argsort(similarities)[::-1][:top_k]
            results = []
            for idx in top_indices:
                doc = self._memory_documents[idx]
                score = float(similarities[idx])
                results.append(RetrievedChunk(text=doc.page_content, score=score, metadata=doc.metadata))
            return results

        docs = self._vector_store.similarity_search_by_vector(query_embedding, k=top_k)
        return [RetrievedChunk(text=doc.page_content, score=doc.metadata.get("score", 0.0), metadata=doc.metadata) for doc in docs]

    @property
    def documents(self) -> List[Document]:
        """Return stored documents (used by lexical retrievers)."""

        if self.config.provider == "memory":
            return list(self._memory_documents)
        else:
            raise NotImplementedError("Solo soportado en modo de memoria")
