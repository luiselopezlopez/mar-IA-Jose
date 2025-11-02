"""Prompt construction utilities for the LLM stage."""

from __future__ import annotations

from textwrap import dedent
from typing import Iterable, List

from .config import PromptConfig
from .schemas import RetrievedChunk


def build_prompt(question: str, chunks: Iterable[RetrievedChunk], config: PromptConfig) -> str:
    """Construct a prompt that includes the question and supporting context."""

    chunk_lines: List[str] = []
    for index, chunk in enumerate(chunks, start=1):
        source = chunk.metadata.get("source", "desconocido")
        section = chunk.metadata.get("section", chunk.metadata.get("section_index", "N/A"))
        chunk_lines.append(
            f"[Fuente {index}] ({source}, sección {section})\n{chunk.text.strip()}"
        )

    chunks_block = "\n\n".join(chunk_lines) if chunk_lines else "No se encontraron fragmentos relevantes."
    instruction = config.system_instruction if config.cite_sources else ""

    prompt = dedent(
        f"""
        {instruction}

        Pregunta del usuario:
        {question}

        Contexto disponible:
        {chunks_block}

        Instrucciones:
        - Responde únicamente con la información del contexto.
        - Usa el formato [Fuente X] para citar cada afirmación.
        - Si faltan datos, indica las limitaciones.
        """
    ).strip()

    return prompt
