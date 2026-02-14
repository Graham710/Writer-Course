"""Exercise generation from unit content and fallback generation when needed."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from .config import data_dir, exercises_path
from .types import CourseUnit, ExerciseSpec


_IMPERATIVE_PATTERNS = [
    r"\bwrite\b",
    r"\bdescribe\b",
    r"\btry\b",
    r"\bcompose\b",
    r"\bdraft\b",
    r"\bexercise\b",
]



def extract_directive_lines(texts: List[Dict[str, object]], max_items: int = 3) -> List[str]:
    """Extract candidate directive-style lines from chunked lesson text.

    Args:
        texts:
            A list of chunk dictionaries loaded from PDF ingestion.
        max_items:
            Maximum number of directive candidates to return.

    Returns:
        A list of cleaned directive strings, capped at ``max_items``.
    """

    directives: List[str] = []
    for chunk in texts:
        chunk_text = str(chunk.get("text", ""))
        for line in chunk_text.split("."):
            candidate = re.sub(r"\s+", " ", line).strip()
            if not candidate:
                continue
            if any(re.search(pattern, candidate, flags=re.IGNORECASE) for pattern in _IMPERATIVE_PATTERNS) and len(candidate) > 30:
                directives.append(candidate.strip("- "))
            if len(directives) >= max_items:
                return directives[:max_items]
    return directives



def _is_valid_exercise_cache(
    payload: object, unit_ids: List[str]
) -> Dict[str, List[ExerciseSpec]] | None:
    """Validate cached exercise payload shape and unit coverage.

    Args:
        payload:
            Raw JSON payload from the cache file.
        unit_ids:
            Unit IDs currently in the catalog.

    Returns:
        Parsed cache as ``dict[str, list[ExerciseSpec]]`` when valid,
        otherwise ``None``.
    """

    if not isinstance(payload, list):
        return None

    mapped: Dict[str, List[ExerciseSpec]] = {}
    try:
        for item in payload:
            spec = ExerciseSpec.from_dict(item)
            mapped.setdefault(spec.unit_id, []).append(spec)
    except Exception:
        return None

    if set(mapped.keys()) != set(unit_ids):
        return None

    for unit_id in unit_ids:
        specs = mapped[unit_id]
        if len(specs) != 2:
            return None
        kinds = [spec.kind for spec in specs]
        if kinds.count("core") != 1 or kinds.count("stretch") != 1:
            return None
    return mapped



def _make_prompt(unit: CourseUnit, objective: str, mode: str, source_mode: str) -> ExerciseSpec:
    """Create one exercise prompt for a unit with a defined objective.

    Args:
        unit:
            Source unit metadata.
        objective:
            Exercise objective text.
        mode:
            ``core`` or ``stretch``.
        source_mode:
            Indicates whether source text or generic generation produced it.

    Returns:
        A fully populated :class:`ExerciseSpec`.
    """

    constraints = [
        "Keep the prompt strictly in the craft scope of this unit only.",
        "Use only one clear narrative line, no essay-length analysis.",
        "Do not summarize the book text; produce your own original scene/paragraph.",
    ]

    self_check = [
        "Does it use the unit's core technique in at least two places?",
        "Does word choice create concrete imagery tied to setting or mood?",
        "Is perspective, form, or rhythm clearly controlled?",
    ]

    prompt_lines = [
        f"Unit {unit.id} ({unit.title}) {mode} exercise",
        f"Objective: {objective}",
        "",
        "Instructions:",
        "- Write a short practice piece (2-4 paragraphs).",
        "- Use concrete details and keep all choices motivated by scene purpose.",
        "",
        "Constraints:",
        *(f"- {line}" for line in constraints),
        "",
        "Estimated time: 30 minutes",
        "",
        "Self-check list:",
        *(f"- {line}" for line in self_check),
        "",
        "What rubric will prioritize:",
        "- Concept application, narrative effectiveness, language control, revision clarity.",
    ]

    return ExerciseSpec(
        unit_id=unit.id,
        source_mode=source_mode,
        prompt="\n".join(prompt_lines),
        success_criteria=self_check,
        timebox_minutes=30,
        kind=mode,
    )



def _default_objective(unit: CourseUnit) -> str:
    """Return a fallback exercise objective for units with no directives."""

    if unit.learning_objectives:
        return unit.learning_objectives[0]
    return f"Practice applying the core principle in {unit.title}."



def build_exercises_for_unit(unit: CourseUnit, chunks: List[Dict[str, object]]) -> List[ExerciseSpec]:
    """Build the core and stretch prompts for a single course unit."""

    directives = extract_directive_lines(chunks)

    if directives:
        core = _make_prompt(unit, directives[0], "core", "book_derived")
        stretch = _make_prompt(
            unit,
            directives[1] if len(directives) > 1 else f"Use deeper perspective shifts than in: {directives[0]}",
            "stretch",
            "book_derived",
        )
        stretch.timebox_minutes = 50
        return [core, stretch]

    base_objective = _default_objective(unit)
    core = _make_prompt(unit, base_objective, "core", "generated_from_unit")
    stretch = _make_prompt(
        unit,
        f"Push the core objective into a tougher constraint: include at least one deliberate contradiction, uncertainty, or unreliability.",
        "stretch",
        "generated_from_unit",
    )
    stretch.timebox_minutes = 50
    return [core, stretch]



def load_or_build_exercises(
    units: List[CourseUnit],
    unit_chunks: Dict[str, List[Dict[str, object]]],
) -> Dict[str, List[ExerciseSpec]]:
    """Load cached exercises, or build and persist fresh ones per unit.

    Cache is rebuilt when the payload is malformed, stale, or doesn't contain a
    single ``core`` and ``stretch`` exercise per current unit.
    """

    data_dir().mkdir(parents=True, exist_ok=True)
    path = exercises_path()
    payload: List[dict] = []
    unit_ids = [unit.id for unit in units]

    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            cached = _is_valid_exercise_cache(raw, unit_ids)
            if cached is not None:
                return cached
        except Exception:
            pass

    mapped: Dict[str, List[ExerciseSpec]] = {}
    for unit in units:
        chunks = unit_chunks.get(unit.id, [])
        mapped[unit.id] = build_exercises_for_unit(unit, chunks)
        payload.extend(spec.to_dict() for spec in mapped[unit.id])

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return mapped
