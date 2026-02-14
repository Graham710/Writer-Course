from src.feedback_engine import _fallback_report
from src.types import CourseUnit


def test_fallback_report_keeps_short_drafts_below_unlock_threshold():
    unit = CourseUnit(
        id="1",
        title="Narrating",
        start_page=16,
        end_page=34,
        learning_objectives=["Track focalization and perspective in prose."],
    )

    draft = "\n".join([f"Sentence {idx}: sample craft sentence." for idx in range(1, 8)])
    report = _fallback_report(unit, draft, [])

    assert report.overall_score < 85
    assert report.overall_score <= 80
    assert all(0 <= score <= 100 for score in report.rubric_scores.values())


def test_fallback_report_uses_actionable_feedback_items():
    unit = CourseUnit(
        id="2",
        title="Dialogue",
        start_page=131,
        end_page=135,
        learning_objectives=["Write dialogue that advances pressure and reveals perspective."],
    )

    draft = "\n".join(
        [
            "Mara stood by the window and watched the street light up.",
            "She heard a truck down the block and checked the message on her phone.",
            "The room felt too quiet.",
        ]
    )
    report = _fallback_report(unit, draft, [])

    assert len(report.strengths) >= 1
    assert len(report.craft_risks) >= 1
    assert len(report.revision_plan) >= 3
    assert all("(" in note.comment and ")" in note.comment for note in report.line_notes)
