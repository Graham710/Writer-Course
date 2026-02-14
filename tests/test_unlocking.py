from pathlib import Path

from src import storage, types
from src.unit_catalog import load_units


def test_progress_unlocks_on_any_attempt(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITER_COURSE_DB_PATH", str(tmp_path / "writer_course_state.db"))
    units = load_units()
    unit_ids = [unit.id for unit in units]

    progress = storage.load_progress(unit_ids)
    assert progress.current_unit_id == "0"
    assert progress.unlocked_units == ["0"]

    low_report = types.FeedbackReport(
        overall_score=84,
        rubric_scores={
            "concept_application": 70,
            "narrative_effectiveness": 84,
            "language_precision": 83,
            "revision_readiness": 85,
        },
        strengths=["ok"],
        craft_risks=["ok"],
        line_notes=[],
        revision_plan=["ok"],
        unlock_eligible=False,
    )
    progress = storage.add_feedback_attempt(progress, "0", "draft", low_report, unit_ids)
    assert "1" in progress.unlocked_units
    assert progress.attempts["0"] == 1
    assert progress.best_score_by_unit["0"] == 84

    pass_report = types.FeedbackReport(
        overall_score=85,
        rubric_scores={
            "concept_application": 92,
            "narrative_effectiveness": 85,
            "language_precision": 88,
            "revision_readiness": 80,
        },
        strengths=["ok"],
        craft_risks=["ok"],
        line_notes=[],
        revision_plan=["ok"],
        unlock_eligible=True,
    )
    progress = storage.add_feedback_attempt(progress, "0", "draft", pass_report, unit_ids)
    assert "1" in progress.unlocked_units
    assert progress.attempts["0"] == 2
    assert progress.best_score_by_unit["0"] == 85
