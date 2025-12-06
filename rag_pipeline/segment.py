"""Segmentation logic combining structural and semantic cues."""

from __future__ import annotations

import itertools
import re
import uuid
from typing import Iterable, List

from importlib import import_module

from langchain.text_splitter import RecursiveCharacterTextSplitter

from .config import SegmenterConfig
from .schemas import RawDocument, Segment

_HEADING_PATTERN = re.compile(r"^(cap(í|i)tulo|chapter|sección|section)\s+[0-9ivxlcdm]+", re.IGNORECASE)
_SUBHEADING_PATTERN = re.compile(r"^(\d+(\.\d+)+|[ivxlcdm]+\.?)\s+.+")
_TABLE_PATTERN = re.compile(r"\|.+\|")
_FORMULA_PATTERN = re.compile(r"[=<>±∑√πΩμ]{1,}")


def _detect_data_type(text: str) -> str:
    """Return a coarse data type label for the provided text."""

    stripped = text.strip()
    if not stripped:
        return "empty"
    if _TABLE_PATTERN.search(stripped):
        return "table"
    if _FORMULA_PATTERN.search(stripped) or any(symbol in stripped for symbol in {"∫", "λ", "→"}):
        return "formula"
    if len(stripped.splitlines()) > 1 and all(len(line.strip()) <= 12 for line in stripped.splitlines()):
        return "list"
    return "text"


def _structure_split(text: str) -> List[str]:
    """Split by detected structural boundaries (chapters, headings)."""

    lines = text.splitlines()
    segments: List[str] = []
    current: List[str] = []

    for line in lines:
        if _HEADING_PATTERN.match(line) or _SUBHEADING_PATTERN.match(line):
            if current:
                segments.append("\n".join(current).strip())
                current = []
        current.append(line)

    if current:
        segments.append("\n".join(current).strip())

    return [seg for seg in segments if seg.strip()]


class DocumentSegmenter:
    """Segment documents using structural, statistical, and NER-driven rules."""

    def __init__(self, config: SegmenterConfig, spacy_model: str | None = None):
        self.config = config
        self.nlp = None
        if spacy_model != "__dummy__":
            model_name = spacy_model or "es_core_news_sm"
            try:
                spacy_module = import_module("spacy")
                self.nlp = spacy_module.load(model_name)
            except OSError as exc:
                raise RuntimeError(
                    "No se pudo cargar el modelo de spaCy. Ejecuta 'python -m spacy download "
                    f"{model_name}' antes de usar el segmentador."
                ) from exc
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "spaCy no está instalado. Añade 'spacy' a tu entorno antes de usar el segmentador."
                ) from exc

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.max_words * 5,
            chunk_overlap=int(config.max_words * config.overlap_ratio),
            length_function=lambda text: len(text.split()),
        )

    def _apply_sliding_windows(self, text: str) -> List[str]:
        chunks = self.text_splitter.split_text(text)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def _ensure_entity_integrity(self, text: str) -> List[str]:
        if not self.nlp:
            return [text]

        doc = self.nlp(text)
        sentences: List[str] = []
        buffer = []
        for sent in doc.sents:
            buffer.append(sent.text.strip())
            if len(" ".join(buffer).split()) >= self.config.max_words:
                sentences.append(" ".join(buffer))
                buffer = []
        if buffer:
            sentences.append(" ".join(buffer))
        return sentences

    def segment(self, document: RawDocument) -> List[Segment]:
        """Return a list of :class:`Segment` objects for the provided document."""

        structural_parts = _structure_split(document.text)
        if not structural_parts:
            structural_parts = [document.text]

        segments: List[Segment] = []
        for part_index, part in enumerate(structural_parts):
            sentences = self._ensure_entity_integrity(part)
            if not sentences:
                sentences = [part]

            windows = list(itertools.chain.from_iterable(self._apply_sliding_windows(sentence) for sentence in sentences))
            for window_index, window in enumerate(windows):
                if not window.strip():
                    continue

                data_type = _detect_data_type(window)
                segment_metadata = {
                    **document.metadata,
                    "section_index": part_index,
                    "chunk_index": window_index,
                    "data_type": data_type,
                    "language": self.config.language,
                }
                segment_id = f"{document.doc_id}::{uuid.uuid4().hex}"
                segments.append(
                    Segment(
                        segment_id=segment_id,
                        text=window.strip(),
                        metadata=segment_metadata,
                        source_document_id=document.doc_id,
                    )
                )

        return segments
