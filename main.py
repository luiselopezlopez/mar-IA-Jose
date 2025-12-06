"""Command-line entry points for the academic RAG pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from rag_pipeline.config import PipelineConfig
from rag_pipeline.pipeline import RAGPipeline


def _load_config(config_path: str | None) -> PipelineConfig:
    if not config_path:
        return PipelineConfig()

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {config_path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return PipelineConfig(**data)


def run_ingest(pipeline: RAGPipeline, files: Iterable[str]) -> None:
    file_list = list(files)
    pipeline.ingest(file_list)
    print(f"Ingesta completada para {len(file_list)} archivos.")


def run_query(pipeline: RAGPipeline, question: str) -> None:
    response = pipeline.answer(question)
    print("Respuesta:")
    print(response.answer)
    print("\nReferencias:")
    for reference in response.references:
        print(f"- {reference}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline RAG académico")
    parser.add_argument("command", choices={"ingest", "query"}, help="Acción a ejecutar")
    parser.add_argument("files", nargs="*", help="Rutas de documentos para ingestar")
    parser.add_argument("--question", help="Pregunta para realizar al sistema")
    parser.add_argument("--config", help="Ruta a un archivo JSON con la configuración del pipeline")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    config = _load_config(args.config)
    pipeline = RAGPipeline(config=config)

    if args.command == "ingest":
        if not args.files:
            raise SystemExit("Debes proporcionar al menos un archivo para ingestar.")
        run_ingest(pipeline, args.files)
    elif args.command == "query":
        if not args.question:
            raise SystemExit("Debes proporcionar una pregunta con --question.")
        run_query(pipeline, args.question)


if __name__ == "__main__":
    main()
