"""LLM client abstraction for GPT-5 generation."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from .schemas import PipelineResponse, RetrievedChunk


class LLMClient:
    """Wrapper around the OpenAI GPT-5 completion API."""

    def __init__(self, model: str = "gpt-5", temperature: float = 0.2) -> None:
        self.model = model
        self.temperature = temperature
        self.client = OpenAI()

    def generate(self, prompt: str, chunks: list[RetrievedChunk]) -> str:
        """Generate an answer leveraging GPT-5."""

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": "Eres un asistente confiable y preciso."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content.strip()


def build_pipeline_response(answer: str, prompt: str, chunks: list[RetrievedChunk]) -> PipelineResponse:
    """Create a :class:`PipelineResponse` object with references."""

    references = []
    for index, chunk in enumerate(chunks, start=1):
        references.append(
            {
                "label": f"Fuente {index}",
                "source": chunk.metadata.get("source"),
                "section": chunk.metadata.get("section_index"),
                "data_type": chunk.metadata.get("data_type"),
            }
        )
    return PipelineResponse(answer=answer, prompt=prompt, references=references)
