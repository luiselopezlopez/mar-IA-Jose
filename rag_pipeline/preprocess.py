"""Text preprocessing helpers tailored for academic documents."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from .config import SegmenterConfig
from .schemas import RawDocument

CONTROL_CHAR_PATTERN = re.compile(r"[\u0000-\u001F\u007F]")
MULTISPACE_PATTERN = re.compile(r"\s+")
PUNCT_SPACE_PATTERN = re.compile(r"\s([,.;:!?])")
HEADER_FOOTER_THRESHOLD = 5


def _expand_abbreviations(text: str, abbreviation_pairs: Iterable[tuple[str, str]]) -> str:
    """Expand the supplied abbreviations using word boundaries."""

    result = text
    for short, expanded in abbreviation_pairs:
        pattern = re.compile(rf"\b{re.escape(short)}\b", re.IGNORECASE)
        result = pattern.sub(expanded, result)
    return result


def _strip_headers_and_footers(lines: list[str]) -> list[str]:
    """Remove lines that appear frequently as headers or footers."""

    normalized = [line.strip() for line in lines if line.strip()]
    if not normalized:
        return lines

    counts = Counter(normalized)
    repetitive = {
        line
        for line, count in counts.items()
        if count >= HEADER_FOOTER_THRESHOLD and len(line.split()) <= 12
    }

    if not repetitive:
        return lines

    filtered = [line for line in lines if line.strip() not in repetitive]
    return filtered


def preprocess_document(document: RawDocument, config: SegmenterConfig) -> RawDocument:
    """Return a cleaned :class:`RawDocument` applying linguistic normalization."""

    text = document.text
    text = CONTROL_CHAR_PATTERN.sub(" ", text)
    text = text.replace("\u00A0", " ")
    text = MULTISPACE_PATTERN.sub(" ", text)
    text = PUNCT_SPACE_PATTERN.sub(lambda match: match.group(1), text)
    text = _expand_abbreviations(text, config.abbreviation_map)

    lines = text.splitlines()
    lines = _strip_headers_and_footers(lines)
    text = "\n".join(lines)

    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = text.strip()

    metadata = dict(document.metadata)
    metadata.setdefault("language", config.language)
    metadata["preprocessed"] = True

    return RawDocument(doc_id=document.doc_id, text=text, metadata=metadata)