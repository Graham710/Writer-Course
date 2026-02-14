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
