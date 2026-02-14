from src.lesson_engine import build_lesson_pack
from src.types import CourseUnit


def test_lesson_pack_fallback_without_api_key(monkeypatch):
    monkeypatch.setattr("src.lesson_engine.has_openai_api_key", lambda: False)

    unit = CourseUnit(
        id="3",
        title="Flaubert and the Rise of the Flaneur",
        start_page=40,
        end_page=46,
        learning_objectives=["Build observational prose that records action before interpretation."],
    )
    chunks = [
        {
            "unit_id": "3",
            "page": 41,
            "text": "Observation before judgment keeps prose kinetic and less abstract.",
            "citation": "p.41",
        }
    ]

    pack = build_lesson_pack(unit, chunks)

    assert pack.source_mode == "fallback_local"
    assert pack.unit_id == "3"
    assert len(pack.key_ideas) == 5
    assert len(pack.pitfalls) == 3
    assert len(pack.reflection_questions) == 3
    assert len(pack.micro_drills) == 2
