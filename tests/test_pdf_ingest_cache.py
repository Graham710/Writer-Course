from pathlib import Path

from src import pdf_ingest
from src.types import CourseUnit


def _unit() -> CourseUnit:
    return CourseUnit(id="0", title="Orientation", start_page=7, end_page=15)


def _unit_layout_payload():
    return {
        "unit_count": 1,
        "units": [
            {"id": "0", "start_page": 7, "end_page": 15},
        ],
    }


def test_cache_compatible_false_without_chunk_config(tmp_path):
    unit = _unit()
    payload = {
        "source_pdf": "sample.pdf",
        "unit_layout": _unit_layout_payload(),
        "chunks": [],
    }
    assert pdf_ingest._cache_compatible(payload, Path("/tmp/sample.pdf"), [unit]) is False


def test_cache_compatible_true_for_matching_portable_inputs(monkeypatch):
    unit = _unit()
    monkeypatch.setattr("src.pdf_ingest.chunk_chars", lambda: 1200)

    payload = {
        "source_pdf": "sample.pdf",
        "unit_layout": _unit_layout_payload(),
        "chunk_config": {"max_chars": 1200},
        "chunks": [],
    }
    assert pdf_ingest._cache_compatible(payload, Path("/var/data/sample.pdf"), [unit]) is True


def test_cache_compatible_false_on_chunksize_change(monkeypatch):
    unit = _unit()
    monkeypatch.setattr("src.pdf_ingest.chunk_chars", lambda: 900)

    payload = {
        "source_pdf": "sample.pdf",
        "unit_layout": _unit_layout_payload(),
        "chunk_config": {"max_chars": 1200},
        "chunks": [],
    }
    assert pdf_ingest._cache_compatible(payload, Path("/tmp/sample.pdf"), [unit]) is False
