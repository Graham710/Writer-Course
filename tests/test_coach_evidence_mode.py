from src import coach_engine


def test_coach_structured_answer_includes_citations_and_evidence(monkeypatch):
    monkeypatch.setattr("src.coach_engine.has_openai_api_key", lambda: False)

    chunks = [
        {
            "unit_id": "1",
            "page": 16,
            "text": "Narrating is about focalization, scene distance, and perspective in prose.",
            "citation": "p.16",
        }
    ]

    answer = coach_engine.ask_question(
        "1", "What does focalization mean in this unit?", chunks
    )

    assert answer.is_refusal is False
    assert answer.citations
    assert answer.evidence
    assert 0.0 <= answer.confidence <= 1.0
    assert "p.16" in answer.answer

    # Compatibility wrapper still returns string output.
    text_answer = coach_engine.answer_question("1", "What does focalization mean in this unit?", chunks)
    assert text_answer == answer.answer
