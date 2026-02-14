from src.revision_engine import build_revision_mission
from src.types import CourseUnit, FeedbackReport


def test_revision_mission_targets_weakest_dimension(monkeypatch):
    monkeypatch.setattr("src.revision_engine.has_openai_api_key", lambda: False)

    unit = CourseUnit(
        id="9",
        title="Language",
        start_page=115,
        end_page=130,
        learning_objectives=["Shape sentences for tonal control and timing."],
    )
    report = FeedbackReport(
        overall_score=72,
        rubric_scores={
            "concept_application": 78,
            "narrative_effectiveness": 75,
            "language_precision": 61,
            "revision_readiness": 73,
        },
        strengths=["Good momentum."],
        craft_risks=["Language slips into abstraction."],
        line_notes=[],
        revision_plan=["Tighten diction."],
        unlock_eligible=False,
    )
    chunks = [
        {
            "unit_id": "9",
            "page": 116,
            "text": "Language controls tone through sentence tempo and selective detail.",
        }
    ]

    mission = build_revision_mission(unit, report, "Draft text", chunks)

    assert mission.focus_dimension == "language_precision"
    assert len(mission.checklist) == 3
    assert mission.checklist[2].startswith("Done when")
    assert "(p." in mission.instructions
