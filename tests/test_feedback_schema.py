from src.feedback_engine import _normalize_report
from src import types


def test_feedback_report_falls_back_to_schema():
    fake_payload = {
        "overall_score": 90,
        "rubric_scores": {
            "concept_application": 96,
            "narrative_effectiveness": 88,
            "language_precision": "90",
            "revision_readiness": 80,
        },
        "strengths": ["strong command"],
        "craft_risks": ["watch pacing"],
        "line_notes": [
            {
                "line_number": 1,
                "text_excerpt": "A line",
                "comment": "Good use",
                "citation": "p.20",
            }
        ],
        "revision_plan": ["Trim first paragraph"],
    }
    unit = types.CourseUnit(
        id="1",
        title="Narrating",
        start_page=16,
        end_page=34,
        learning_objectives=["Track narrator"],
        source_chunks=[],
    )
    report = _normalize_report(fake_payload, unit, [])

    assert isinstance(report, types.FeedbackReport)
    assert report.overall_score == 90
    assert report.rubric_scores["language_precision"] == 90
    assert report.unlock_eligible is True
    assert len(report.line_notes) == 1
    assert report.line_notes[0].citation == "p.20"
