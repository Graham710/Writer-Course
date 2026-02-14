from src import coach_engine, types


def test_coach_refuses_out_of_scope_question():
    chunks = [
        {
            "unit_id": "1",
            "page": 16,
            "text": "Narrating is about focalization, scene distance, and perspective.",
            "citation": "p.16",
        }
    ]

    answer = coach_engine.answer_question("1", "What is quantum mechanics?", chunks)
    assert answer == coach_engine.REFUSAL_TEXT


def test_coach_in_scope_response_has_citation_or_refusal():
    chunks = [
        {
            "unit_id": "1",
            "page": 16,
            "text": "Narrating is about focalization, scene distance, and perspective in prose.",
            "citation": "p.16",
        }
    ]

    answer = coach_engine.answer_question(
        "1", "What does narrating mean for this unit?", chunks
    )
    assert answer == "From this unit: Narrating is about focalization, scene distance, and perspective in prose. (p.16)" or "p.16" in answer
