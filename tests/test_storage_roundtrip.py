from src import storage, types


def _report(overall_score: int) -> types.FeedbackReport:
    return types.FeedbackReport(
        overall_score=overall_score,
        rubric_scores={
            "concept_application": 60,
            "narrative_effectiveness": 62,
            "language_precision": 58,
            "revision_readiness": 64,
        },
        strengths=["Good control"],
        craft_risks=["Needs work"],
        line_notes=[],
        revision_plan=["Revise a little"],
        unlock_eligible=False,
    )


def test_draft_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITER_COURSE_DB_PATH", str(tmp_path / "writer_course_state.db"))

    storage.save_draft("0", "First draft")
    assert storage.get_draft("0") == "First draft"


def test_progress_round_trip_rounds_back_to_db(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITER_COURSE_DB_PATH", str(tmp_path / "writer_course_state.db"))

    progress = storage.load_progress(["0", "1"])
    progress.current_unit_id = "1"
    progress.unlocked_units = ["0", "1"]
    progress.best_score_by_unit = {"0": 88}
    progress.attempts = {"0": 2}

    storage.persist_progress(progress)
    reloaded = storage.load_progress(["0", "1"])

    assert reloaded.current_unit_id == "1"
    assert reloaded.unlocked_units == ["0", "1"]
    assert reloaded.best_score_by_unit == {"0": 88}
    assert reloaded.attempts == {"0": 2}


def test_export_portfolio_includes_attempts(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITER_COURSE_DB_PATH", str(tmp_path / "writer_course_state.db"))
    progress = storage.load_progress(["0"])

    progress = storage.add_feedback_attempt(progress, "0", "Draft one", _report(82), ["0"])
    progress = storage.add_feedback_attempt(progress, "0", "Draft two", _report(87), ["0"])

    portfolio = storage.export_portfolio(["0"])

    assert portfolio["units"][0]["unit_id"] == "0"
    assert len(portfolio["units"][0]["attempts"]) == 2
    assert portfolio["units"][0]["attempts"][0]["draft"] == "Draft one"
    assert portfolio["units"][0]["attempts"][1]["draft"] == "Draft two"
