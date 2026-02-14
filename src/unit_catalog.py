"""Course units defined from the user-provided page map."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .config import units_path, data_dir
from .types import CourseUnit


RAW_UNITS = [
    {
        "id": "0",
        "title": "Orientation",
        "start_page": 7,
        "end_page": 15,
        "learning_objectives": [
            "Map the course sequence to the specific craft skill you will practice each week.",
            "Use the unit vocabulary to diagnose what is working and what still needs attention.",
            "Set a clear workflow: draft, revise, and reflect on one improvement before moving forward.",
        ],
    },
    {
        "id": "1",
        "title": "Narrating",
        "start_page": 16,
        "end_page": 34,
        "learning_objectives": [
            "Anchor each draft in one focal perspective and keep it stable across the scene.",
            "Balance what the reader sees, hears, and knows at each moment.",
            "Maintain orientation through concrete scene grounding instead of backstory explanation.",
        ],
    },
    {
        "id": "2",
        "title": "Flaubert and Modern Narrative",
        "start_page": 35,
        "end_page": 39,
        "learning_objectives": [
            "Track when voice narrows or expands to create distance and emotional pressure.",
            "Prioritize scene-based movement over summary so revision decisions stay concrete.",
            "Use paragraph shape to make cause, reaction, and consequence visible.",
        ],
    },
    {
        "id": "3",
        "title": "Flaubert and the Rise of the Flaneur",
        "start_page": 40,
        "end_page": 46,
        "learning_objectives": [
            "Build observational prose that records action before interpretation.",
            "Let detail and movement carry character judgment instead of abstract labels.",
            "Keep attention directed even when the scene perspective drifts.",
        ],
    },
    {
        "id": "4",
        "title": "Detail",
        "start_page": 47,
        "end_page": 63,
        "learning_objectives": [
            "Choose details that perform a specific narrative job.",
            "Remove descriptive weight that does not change tension or decision.",
            "Attach setting and objects directly to character pressure and motive.",
        ],
    },
    {
        "id": "5",
        "title": "Character",
        "start_page": 64,
        "end_page": 84,
        "learning_objectives": [
            "Reveal character through choice, gesture, and response in pressure points.",
            "Replace explanatory traits with observable contradiction.",
            "Use voice and detail to make motivation feel earned.",
        ],
    },
    {
        "id": "6",
        "title": "A Brief History of Consciousness",
        "start_page": 85,
        "end_page": 99,
        "learning_objectives": [
            "Track shifts in awareness from sensation to thought to decision.",
            "Keep interior perspective legible through line breaks, rhythm, and focus words.",
            "Make each cognitive turn in a sentence create a clear change of direction.",
        ],
    },
    {
        "id": "7",
        "title": "Form",
        "start_page": 100,
        "end_page": 108,
        "learning_objectives": [
            "Shape scene order to escalate expectation and release.",
            "Use transitions to control time, causality, and point of view.",
            "Experiment with rearrangement while preserving narrative clarity.",
        ],
    },
    {
        "id": "8",
        "title": "Sympathy and Complexity",
        "start_page": 109,
        "end_page": 114,
        "learning_objectives": [
            "Generate sympathy through behavior and consequence, not moral explanation.",
            "Introduce conflict inside the emotion of a scene, not as editorial commentary.",
            "Hold compassion and uncertainty together in the same scene.",
        ],
    },
    {
        "id": "9",
        "title": "Language",
        "start_page": 115,
        "end_page": 130,
        "learning_objectives": [
            "Use sentence tempo to control urgency, delay, and tonal distance.",
            "Differentiate narration, character voice, and implied perspective with diction.",
            "Keep imagery focused and reusable across revisions.",
        ],
    },
    {
        "id": "10",
        "title": "Dialogue",
        "start_page": 131,
        "end_page": 135,
        "learning_objectives": [
            "Write dialogue that shifts power, reveals motive, or changes stakes.",
            "Use interruption, overlap, and silence as functional scene decisions.",
            "Root every exchange in physical detail and immediate tension.",
        ],
    },
    {
        "id": "11",
        "title": "Truth, Convention, Realism",
        "start_page": 136,
        "end_page": 149,
        "learning_objectives": [
            "Balance factual fact and emotional truth without overexplaining either.",
            "Select convention as a deliberate structural choice, not a default crutch.",
            "Earn trust through precise, selective revelation across scenes.",
        ],
    },
]


def _default_units() -> List[CourseUnit]:
    return [CourseUnit.from_dict(unit) for unit in RAW_UNITS]


def load_units() -> List[CourseUnit]:
    path = units_path()
    data_dir().mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            units = [CourseUnit.from_dict(item) for item in raw]
            if units:
                return units
        except Exception:
            pass
    units = _default_units()
    save_units(units)
    return units


def save_units(units: List[CourseUnit]) -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    payload = [unit.to_dict() for unit in units]
    units_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")


def unit_by_id(unit_id: str) -> CourseUnit | None:
    for unit in load_units():
        if unit.id == unit_id:
            return unit
    return None


def unit_ids() -> List[str]:
    return [unit.id for unit in load_units()]
