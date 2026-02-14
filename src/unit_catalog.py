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
            "Understand how the course is organized and what each chapter teaches",
            "Identify the book's vocabulary of craft terms",
            "Track how fiction can be evaluated through close reading",
        ],
    },
    {
        "id": "1",
        "title": "Narrating",
        "start_page": 16,
        "end_page": 34,
        "learning_objectives": [
            "Differentiate narrative perspective and focalization",
            "Practice choosing a useful narrative distance",
            "Keep readers oriented while revealing character through detail",
        ],
    },
    {
        "id": "2",
        "title": "Flaubert and Modern Narrative",
        "start_page": 35,
        "end_page": 39,
        "learning_objectives": [
            "Describe how form and voice interact in modern prose",
            "Recognize modern narrative pressure away from simple plot first",
            "Borrow useful revision habits from classic realism",
        ],
    },
    {
        "id": "3",
        "title": "Flaubert and the Rise of the Flaneur",
        "start_page": 40,
        "end_page": 46,
        "learning_objectives": [
            "Explain the flaneur viewpoint and observational prose",
            "Use scene-level movement to carry character meaning",
            "Balance wandering perception with scene control",
        ],
    },
    {
        "id": "4",
        "title": "Detail",
        "start_page": 47,
        "end_page": 63,
        "learning_objectives": [
            "Use concrete details to guide attention and meaning",
            "Distinguish useful detail from decorative texture",
            "Use objects and setting to signal internal state",
        ],
    },
    {
        "id": "5",
        "title": "Character",
        "start_page": 64,
        "end_page": 84,
        "learning_objectives": [
            "Build character through behavior and perception",
            "Avoid summary-based character shortcuts",
            "Let voice, detail, and action create contradictions",
        ],
    },
    {
        "id": "6",
        "title": "A Brief History of Consciousness",
        "start_page": 85,
        "end_page": 99,
        "learning_objectives": [
            "Map how interior attention shifts across scenes",
            "Write with controlled interiority without confusion",
            "Track sentence rhythm to reflect thought movement",
        ],
    },
    {
        "id": "7",
        "title": "Form",
        "start_page": 100,
        "end_page": 108,
        "learning_objectives": [
            "Understand how scenes and transitions shape reader expectation",
            "Use form to control temporal pressure",
            "Test multiple orderings without losing coherence",
        ],
    },
    {
        "id": "8",
        "title": "Sympathy and Complexity",
        "start_page": 109,
        "end_page": 114,
        "learning_objectives": [
            "Balance empathy with moral and psychological complexity",
            "Avoid sentimentality in emotional pivots",
            "Keep characters specific instead of generalized",
        ],
    },
    {
        "id": "9",
        "title": "Language",
        "start_page": 115,
        "end_page": 130,
        "learning_objectives": [
            "Shape sentences for tonal control and timing",
            "Use diction to separate narration and character consciousness",
            "Keep imagery purposeful and repeatable across draft passes",
        ],
    },
    {
        "id": "10",
        "title": "Dialogue",
        "start_page": 131,
        "end_page": 135,
        "learning_objectives": [
            "Write dialogue that reveals social distance and power",
            "Use silence, interruption, and mismatch for realism",
            "Embed dialogue in scene context instead of isolated lines",
        ],
    },
    {
        "id": "11",
        "title": "Truth, Convention, Realism",
        "start_page": 136,
        "end_page": 149,
        "learning_objectives": [
            "Define the trade-off between literal truth and narrative truth",
            "Use convention with control instead of habit",
            "Make the reader trust fiction through precision",
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
