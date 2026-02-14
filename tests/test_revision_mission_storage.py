from src import storage
from src.types import RevisionMission


def _mission(unit_id: str, attempt_id: int) -> RevisionMission:
    return RevisionMission(
        id=None,
        unit_id=unit_id,
        attempt_id=attempt_id,
        focus_dimension="language_precision",
        title="Mission: Strengthen Language Precision",
        instructions="Tighten language choices and remove abstraction. (p.116)",
        checklist=[
            "Rewrite one paragraph for precision. (p.116)",
            "Replace one abstract sentence with sensory detail. (p.116)",
            "Done when the revision reads clearly in one perspective. (p.116)",
        ],
        status="active",
    )


def test_revision_mission_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITER_COURSE_DB_PATH", str(tmp_path / "writer_course_state.db"))

    assert storage.get_active_revision_mission("1") is None

    saved = storage.save_revision_mission(_mission("1", 3))
    assert saved.id is not None

    active = storage.get_active_revision_mission("1")
    assert active is not None
    assert active.attempt_id == 3
    assert active.status == "active"

    storage.complete_revision_mission(int(saved.id))
    assert storage.get_active_revision_mission("1") is None

    saved2 = storage.save_revision_mission(_mission("1", 4))
    assert saved2.id is not None
    updated_count = storage.supersede_active_revision_missions("1", new_attempt_id=5)
    assert updated_count == 1
    assert storage.get_active_revision_mission("1") is None
