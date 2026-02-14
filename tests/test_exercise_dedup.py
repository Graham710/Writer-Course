import json

from src import exercise_engine
from src.types import CourseUnit


def _unit(unit_id: str = "0") -> CourseUnit:
    return CourseUnit(
        id=unit_id,
        title="Orientation",
        start_page=7,
        end_page=15,
        learning_objectives=["Track focalization."],
        source_chunks=[],
    )


def test_load_or_build_exercises_rebuilds_from_invalid_duplicates(tmp_path, monkeypatch):
    cache_path = tmp_path / "exercises.json"
    monkeypatch.setattr("src.exercise_engine.exercises_path", lambda: cache_path)

    unit = _unit()
    cache_path.write_text(
        json.dumps(
            [
                {
                    "unit_id": "0",
                    "source_mode": "legacy",
                    "prompt": "Duplicate core",
                    "success_criteria": [],
                    "timebox_minutes": 30,
                    "kind": "core",
                },
                {
                    "unit_id": "0",
                    "source_mode": "legacy",
                    "prompt": "Duplicate core",
                    "success_criteria": [],
                    "timebox_minutes": 30,
                    "kind": "core",
                },
                {
                    "unit_id": "0",
                    "source_mode": "legacy",
                    "prompt": "Duplicate stretch",
                    "success_criteria": [],
                    "timebox_minutes": 50,
                    "kind": "stretch",
                },
            ]
        )
    )

    exercise_map = exercise_engine.load_or_build_exercises([unit], {"0": []})
    specs = exercise_map["0"]
    assert len(specs) == 2
    assert {spec.kind for spec in specs} == {"core", "stretch"}

    reloaded = json.loads(cache_path.read_text(encoding="utf-8"))
    assert isinstance(reloaded, list)
    assert len(reloaded) == 2


def test_load_or_build_exercises_accepts_valid_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "exercises.json"
    monkeypatch.setattr("src.exercise_engine.exercises_path", lambda: cache_path)

    unit = _unit()
    cache_path.write_text(
        json.dumps(
            [
                {
                    "unit_id": "0",
                    "source_mode": "generated",
                    "prompt": "Core prompt",
                    "success_criteria": ["a"],
                    "timebox_minutes": 30,
                    "kind": "core",
                },
                {
                    "unit_id": "0",
                    "source_mode": "generated",
                    "prompt": "Stretch prompt",
                    "success_criteria": ["a"],
                    "timebox_minutes": 50,
                    "kind": "stretch",
                },
            ]
        )
    )

    exercise_map = exercise_engine.load_or_build_exercises([unit], {"0": []})
    specs = exercise_map["0"]
    assert len(specs) == 2
    assert specs[0].prompt == "Core prompt"
    assert specs[1].prompt == "Stretch prompt"
