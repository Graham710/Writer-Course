from src import coach_engine


def test_coach_refuses_off_topic_despite_overlap_keyword():
    chunks = [
        {
            "unit_id": "1",
            "page": 16,
            "text": "Narrating is about focalization, scene distance, and perspective.",
            "citation": "p.16",
        }
    ]

    answer = coach_engine.answer_question("1", "What is a sports strategy for this unit?", chunks)
    assert answer == coach_engine.REFUSAL_TEXT


def test_coach_accepts_on_topic_question_when_overlap_is_strong():
    chunks = [
        {
            "unit_id": "1",
            "page": 16,
            "text": "Narrating is about focalization, scene distance, and perspective in prose.",
            "citation": "p.16",
        }
    ]

    answer = coach_engine.answer_question("1", "What is focalization and perspective in this unit?", chunks)
    assert answer != coach_engine.REFUSAL_TEXT


def test_coach_empty_question_refused():
    assert coach_engine.answer_question("1", "   ", []) == coach_engine.REFUSAL_TEXT
