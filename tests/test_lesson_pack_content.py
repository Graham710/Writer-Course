import re

from src.lesson_engine import build_lesson_pack
from src.types import CourseUnit


def _unit() -> CourseUnit:
    return CourseUnit(
        id="1",
        title="Narrating",
        start_page=16,
        end_page=34,
        learning_objectives=[
            "Differentiate narrative perspective and focalization",
            "Keep readers oriented while revealing character through detail",
        ],
    )


def _chunks():
    return [
        {
            "unit_id": "1",
            "page": 16,
            "text": "Narrating controls focalization and scene distance so the reader stays anchored.",
            "citation": "p.16",
        },
        {
            "unit_id": "1",
            "page": 17,
            "text": "Detail should carry pressure in action, not only in abstract summary lines.",
            "citation": "p.17",
        },
        {
            "unit_id": "1",
            "page": 18,
            "text": "Perspective choices shape how consequences are felt sentence by sentence.",
            "citation": "p.18",
        },
    ]


def test_lesson_pack_has_required_counts_and_valid_citations(monkeypatch):
    monkeypatch.setattr("src.lesson_engine.has_openai_api_key", lambda: False)

    pack = build_lesson_pack(_unit(), _chunks())

    assert pack.summary
    assert len(pack.key_ideas) == 5
    assert len(pack.pitfalls) == 3
    assert len(pack.reflection_questions) == 3
    assert len(pack.micro_drills) == 2

    valid_pages = {16, 17, 18}
    for item in pack.key_ideas + pack.pitfalls:
        assert re.match(r"^p\.\d+$", item.citation)
        page = int(item.citation.split(".")[1])
        assert page in valid_pages
