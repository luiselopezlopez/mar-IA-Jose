"""Utility to convert PDF documents to plain text with basic layout preservation.

The script uses PyMuPDF (fitz) to detect text blocks and tables, keeping the
relative order of the content. Tables are rendered using simple pipe-separated
rows with padded columns so they remain readable in plain text outputs.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import fitz  # PyMuPDF

BBox = Tuple[float, float, float, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a PDF file to plain text while keeping basic layout",
    )
    parser.add_argument("input_pdf", help="Path to the PDF file to convert")
    parser.add_argument(
        "--output",
        "-o",
        help="Optional path for the output text file (defaults to <pdf>.txt)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Encoding to use for the generated text file (default: utf-8)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )
    return parser.parse_args()


def bbox_intersects(target: BBox, regions: Iterable[BBox]) -> bool:
    x0, y0, x1, y1 = target
    for rx0, ry0, rx1, ry1 in regions:
        if x1 <= rx0 or rx1 <= x0 or y1 <= ry0 or ry1 <= y0:
            continue
        return True
    return False


def block_to_text(block: dict) -> str:
    lines: List[str] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        line_text = "".join(span.get("text", "") for span in spans)
        if line_text.strip():
            lines.append(line_text.rstrip())
    return "\n".join(lines).strip()


def table_to_text(table) -> str:
    # table.extract returns a list of rows with cell contents.
    rows = table.extract()
    if not rows:
        return ""

    normalized: List[List[str]] = []
    max_cols = max(len(row) for row in rows)
    for row in rows:
        cells = [(cell or "").strip() for cell in row]
        if len(cells) < max_cols:
            cells.extend("" for _ in range(max_cols - len(cells)))
        normalized.append(cells)

    widths = [0] * max_cols
    for row in normalized:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    lines: List[str] = []
    for idx, row in enumerate(normalized):
        padded = [cell.ljust(widths[col]) for col, cell in enumerate(row)]
        lines.append(" | ".join(padded).rstrip())
        if idx == 0 and len(normalized) > 1:
            separator = ["-" * widths[col] for col in range(max_cols)]
            lines.append("-+-".join(separator).rstrip())

    return "\n".join(lines).strip()


def extract_page_elements(page) -> str:
    elements: List[Tuple[float, str]] = []

    tables = page.find_tables()
    table_rects: List[BBox] = []
    if tables:
        for table in tables.tables:
            text = table_to_text(table)
            if text:
                elements.append((table.bbox[1], text))
            table_rects.append(table.bbox)

    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        bbox: BBox = tuple(block.get("bbox", (0, 0, 0, 0)))  # type: ignore[arg-type]
        if bbox_intersects(bbox, table_rects):
            continue
        text = block_to_text(block)
        if text:
            elements.append((bbox[1], text))

    elements.sort(key=lambda item: item[0])
    ordered_text = [item[1] for item in elements]
    return "\n\n".join(ordered_text).strip()


def extract_text_from_pdf(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    try:
        pages_text = []
        for index, page in enumerate(doc):
            page_text = extract_page_elements(page)
            if page_text:
                pages_text.append(f"--- Page {index + 1} ---\n{page_text}")
        return "\n\n".join(pages_text)
    finally:
        doc.close()


def main() -> None:
    args = parse_args()

    pdf_path = Path(args.input_pdf).expanduser().resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = pdf_path.with_suffix(".txt")

    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output file already exists: {output_path}. Use --overwrite to replace it.")

    text_content = extract_text_from_pdf(pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text_content, encoding=args.encoding)
    print(f"Saved text to {output_path}")


if __name__ == "__main__":
    main()
