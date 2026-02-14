import json
from pathlib import Path

from src import lesson_engine
from src.types import CourseUnit, LessonIdea, LessonPack


def _unit(unit_id: str, start: int, end: int) -> CourseUnit:
    return CourseUnit(
        id=unit_id,
        title=f"Unit {unit_id}",
        start_page=start,
        end_page=end,
        learning_objectives=["Keep craft choices explicit."],
    )


def _pack(unit_id: str, page: int) -> LessonPack:
    return LessonPack(
        unit_id=unit_id,
        summary=f"Summary for {unit_id}",
        key_ideas=[LessonIdea(text=f"Idea {i}", citation=f"p.{page}") for i in range(5)],
        pitfalls=[LessonIdea(text=f"Pitfall {i}", citation=f"p.{page}") for i in range(3)],
        reflection_questions=[f"Question {i}" for i in range(3)],
        micro_drills=[f"Drill {i}" for i in range(2)],
        source_mode="fallback_local",
    )


def test_lesson_pack_cache_rebuilds_when_unit_coverage_incomplete(tmp_path, monkeypatch):
    cache_path = tmp_path / "lesson_packs.json"

    monkeypatch.setattr("src.lesson_engine.lesson_packs_path", lambda: cache_path)
    monkeypatch.setattr("src.lesson_engine.get_pdf_path", lambda: Path("/tmp/sample.pdf"))
    monkeypatch.setattr("src.lesson_engine.chunk_chars", lambda: 1200)

    units = [_unit("0", 7, 15), _unit("1", 16, 34)]
    payload = {
        "source_pdf": "sample.pdf",
        "unit_layout": {
            "unit_count": 2,
            "units": [
                {"id": "0", "start_page": 7, "end_page": 15},
                {"id": "1", "start_page": 16, "end_page": 34},
            ],
        },
        "chunk_config": {"max_chars": 1200},
        "pack_version": lesson_engine.PACK_VERSION,
        "packs": [_pack("0", 7).to_dict()],
    }
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    unit_chunks = {
        "0": [{"unit_id": "0", "page": 7, "text": "Unit zero chunk text for cache rebuild."}],
        "1": [{"unit_id": "1", "page": 16, "text": "Unit one chunk text for cache rebuild."}],
    }

    packs = lesson_engine.load_or_build_lesson_packs(units, unit_chunks)

    assert set(packs.keys()) == {"0", "1"}
    persisted = json.loads(cache_path.read_text(encoding="utf-8"))
    assert len(persisted["packs"]) == 2
