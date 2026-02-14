from src import coach_engine


def test_coach_refusal_text_remains_exact():
    chunks = [
        {
            "unit_id": "1",
            "page": 16,
            "text": "Narrating is about focalization, scene distance, and perspective in prose.",
            "citation": "p.16",
        }
    ]

    structured = coach_engine.ask_question("1", "What is quantum mechanics?", chunks)
    assert structured.answer == coach_engine.REFUSAL_TEXT
    assert structured.is_refusal is True

    text_only = coach_engine.answer_question("1", "What is quantum mechanics?", chunks)
    assert text_only == coach_engine.REFUSAL_TEXT
