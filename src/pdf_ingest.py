"""PDF extraction and chunking for PDF-only curriculum teaching."""

from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Dict, List

from .config import chunk_chars, data_dir, chunks_path, get_pdf_path
from .types import CourseUnit


def extract_page_texts(pdf_path: Path | None = None) -> List[str]:
    """Load text for each page from the configured PDF.

    Args:
        pdf_path:
            Optional explicit path to a PDF file. When omitted, resolves from
            ``WRITER_COURSE_PDF_PATH`` or project discovery.

    Returns:
        A list of normalized page texts.
    """

    pdf_path = pdf_path or get_pdf_path()

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        return [_normalize(page.extract_text() or "") for page in reader.pages]
    except Exception:
        try:
            import pdfplumber

            texts: List[str] = []
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page in pdf.pages:
                    texts.append(_normalize(page.extract_text() or ""))
            return texts
        except Exception as exc:
            raise RuntimeError(f"Unable to read PDF text at {pdf_path}: {exc}") from exc


def _normalize(text: str) -> str:
    """Normalize whitespace in extracted text."""

    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return cleaned


def _split_into_chunks(text: str, max_chars: int) -> List[str]:
    """Split text into sentence-based chunks bounded by ``max_chars``."""

    if not text:
        return [""]
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[\.!?])\s+", text)
    chunks: List[str] = []
    current = []
    current_len = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current and current_len + len(sentence) + 1 > max_chars:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += len(sentence) + 1

    if current:
        chunks.append(" ".join(current).strip())

    if not chunks:
        return [text[:max_chars]]
    return chunks


def _unit_cache_fingerprint(units: List[CourseUnit]) -> Dict[str, object]:
    """Build a stable representation of current unit layout boundaries."""

    return {
        "unit_count": len(units),
        "units": [
            {"id": unit.id, "start_page": unit.start_page, "end_page": unit.end_page}
            for unit in units
        ],
    }


def _cache_compatible(payload: dict, pdf_path: Path, units: List[CourseUnit]) -> bool:
    """Check whether a cached payload matches current rendering inputs."""

    if not isinstance(payload, dict):
        return False
    if payload.get("source_pdf") != pdf_path.name:
        return False

    cached_units = payload.get("unit_layout")
    if cached_units != _unit_cache_fingerprint(units):
        return False

    chunk_config = payload.get("chunk_config")
    if not isinstance(chunk_config, dict):
        return False

    return chunk_config.get("max_chars") == chunk_chars()


def _read_cached_chunks() -> Dict[str, object]:
    """Load the chunks cache payload if present and JSON-decodable."""

    path = chunks_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_or_build_chunks(units: List[CourseUnit]) -> List[Dict[str, object]]:
    """Return all unit chunks, using cache when configuration and layout match."""

    data_dir().mkdir(parents=True, exist_ok=True)
    path = chunks_path()

    pdf_path = get_pdf_path()
    cached = _read_cached_chunks()
    if _cache_compatible(cached, pdf_path, units):
        chunks = cached.get("chunks")
        if isinstance(chunks, list) and chunks:
            for unit in units:
                unit.source_chunks = [
                    item["chunk_id"] for item in chunks if item.get("unit_id") == unit.id
                ]
            return chunks  # type: ignore[return-value]

    pages = extract_page_texts(pdf_path)
    all_chunks: List[Dict[str, object]] = []
    max_chars = chunk_chars()
    page_count = len(pages)

    for unit in units:
        source_ids = []
        start = max(unit.start_page, 1)
        end = min(unit.end_page, page_count)
        for page_num in range(start, end + 1):
            text = pages[page_num - 1]
            chunk_texts = _split_into_chunks(text, max_chars=max_chars)
            for chunk_index, chunk_text in enumerate(chunk_texts):
                if not chunk_text.strip():
                    continue
                chunk_id = f"{unit.id}:{page_num}:{chunk_index}"
                all_chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "unit_id": unit.id,
                        "page": page_num,
                        "citation": f"p.{page_num}",
                        "text": chunk_text,
                        "chunk_index": chunk_index,
                    }
                )
                source_ids.append(chunk_id)
        unit.source_chunks = source_ids

    payload = {
        "source_pdf": pdf_path.name,
        "unit_layout": _unit_cache_fingerprint(units),
        "chunk_config": {"max_chars": max_chars},
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
        "chunks": all_chunks,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return all_chunks


def chunks_by_unit(unit: CourseUnit, chunks: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Filter all chunks for a specific unit id."""

    return [chunk for chunk in chunks if chunk.get("unit_id") == unit.id]
