"""Document ingestion utilities for the academic RAG pipeline."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, List

import docx2txt
from pypdf import PdfReader

from .schemas import RawDocument


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _generate_document_id(path: Path) -> str:
    """Generate a deterministic identifier for the given file path."""

    absolute = str(path.resolve()).encode("utf-8")
    return hashlib.sha1(absolute).hexdigest()


def _read_pdf(path: Path) -> str:
    """Extract text from a PDF file."""

    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _read_docx(path: Path) -> str:
    """Extract text from a DOCX file."""

    return docx2txt.process(str(path)) or ""


def _read_txt(path: Path) -> str:
    """Read text from a plain text file."""

    return path.read_text(encoding="utf-8", errors="ignore")


READERS = {
    ".pdf": _read_pdf,
    ".docx": _read_docx,
    ".txt": _read_txt,
}


def load_document(path: str | os.PathLike[str]) -> RawDocument:
    """Load a document from disk and return a :class:`RawDocument`."""

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"El archivo {file_path} no existe")

    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Tipo de archivo no soportado: {extension}")

    reader = READERS[extension]
    text = reader(file_path)
    doc_id = _generate_document_id(file_path)
    metadata = {
        "source": str(file_path.resolve()),
        "file_name": file_path.name,
        "extension": extension,
    }
    return RawDocument(doc_id=doc_id, text=text, metadata=metadata)


def load_documents(paths: Iterable[str | os.PathLike[str]]) -> List[RawDocument]:
    """Load multiple documents from disk."""

    documents: List[RawDocument] = []
    for path in paths:
        documents.append(load_document(path))
    return documents
