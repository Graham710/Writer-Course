"""Revision mission generation from feedback reports."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List

from .config import get_openai_api_key, get_openai_model, has_openai_api_key
from .types import CourseUnit, FeedbackReport, RevisionMission

_DIMENSION_LABELS = {
    "concept_application": "Concept Application",
    "narrative_effectiveness": "Narrative Effectiveness",
    "language_precision": "Language Precision",
    "revision_readiness": "Revision Readiness",
}


def _weakest_dimension(rubric_scores: Dict[str, int]) -> str:
    if not rubric_scores:
        return "concept_application"
    return min(rubric_scores.keys(), key=lambda key: int(rubric_scores.get(key, 0)))


def _citation(chunks: List[Dict[str, object]]) -> str:
    if not chunks:
        return "p.0"
    page = int(chunks[0].get("page", 0) or 0)
    return f"p.{page}"


def _fallback_mission(
    unit: CourseUnit, report: FeedbackReport, draft: str, chunks: List[Dict[str, object]]
) -> RevisionMission:
    focus = _weakest_dimension(report.rubric_scores)
    focus_label = _DIMENSION_LABELS.get(focus, focus.replace("_", " ").title())
    citation = _citation(chunks)

    checklist = [
        f"Rewrite the opening so {focus_label.lower()} is explicit in the first 3-5 lines. ({citation})",
        f"Replace one abstract sentence with concrete action or sensory detail tied to unit goals. ({citation})",
        f"Done when the new draft keeps one clear perspective and addresses one item from craft risks. ({citation})",
    ]

    return RevisionMission(
        id=None,
        unit_id=unit.id,
        attempt_id=0,
        focus_dimension=focus,
        title=f"Mission: Strengthen {focus_label}",
        instructions=(
            f"Focus this revision pass on {focus_label.lower()}. Keep scope tight: one focused rewrite with"
            f" direct alignment to unit {unit.id} ({unit.title}). Use cited unit material for guidance. ({citation})"
        ),
        checklist=checklist,
        status="active",
        created_at=datetime.utcnow().isoformat(),
        completed_at=None,
    )


def _prompt(unit: CourseUnit, report: FeedbackReport, draft: str, chunks: List[Dict[str, object]]) -> str:
    context = "\n\n".join(
        f"[p.{chunk.get('page', 0)}] {str(chunk.get('text', ''))[:450]}"
        for chunk in chunks[:8]
    )

    return f"""You are building one revision mission for a writing student.

Unit: {unit.id} - {unit.title}
Rubric scores: {json.dumps(report.rubric_scores)}
Craft risks: {json.dumps(report.craft_risks)}
Draft excerpt: {draft[:850]}

Course context (use only this):
{context}

Return JSON only:
{{
  "focus_dimension": "one of concept_application|narrative_effectiveness|language_precision|revision_readiness",
  "title": "short mission title",
  "instructions": "1-2 sentence mission description with citation (p.NUM)",
  "checklist": ["step 1", "step 2", "Done when ..."]
}}

Rules:
- Return exactly 3 checklist items.
- Third checklist item must start with 'Done when'.
- Include at least one citation in instructions and each checklist item, formatted as (p.NUM).
- Use only provided context.
"""


def _parse_json_object(raw: str) -> Dict[str, object]:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or start >= end:
        raise ValueError("No JSON object found")
    return json.loads(raw[start : end + 1])


def _normalize_mission_payload(
    payload: Dict[str, object], unit: CourseUnit, report: FeedbackReport, draft: str, chunks: List[Dict[str, object]]
) -> RevisionMission:
    fallback = _fallback_mission(unit, report, draft, chunks)

    focus_dimension = str(payload.get("focus_dimension", fallback.focus_dimension)).strip()
    if focus_dimension not in _DIMENSION_LABELS:
        focus_dimension = fallback.focus_dimension

    title = str(payload.get("title", fallback.title)).strip() or fallback.title
    instructions = str(payload.get("instructions", fallback.instructions)).strip() or fallback.instructions
    raw_checklist = payload.get("checklist") if isinstance(payload.get("checklist"), list) else []
    checklist = [str(item).strip() for item in raw_checklist if str(item).strip()]

    while len(checklist) < 3:
        checklist.append(fallback.checklist[len(checklist)])
    checklist = checklist[:3]
    if not checklist[2].lower().startswith("done when"):
        checklist[2] = fallback.checklist[2]

    return RevisionMission(
        id=None,
        unit_id=unit.id,
        attempt_id=0,
        focus_dimension=focus_dimension,
        title=title,
        instructions=instructions,
        checklist=checklist,
        status="active",
        created_at=datetime.utcnow().isoformat(),
        completed_at=None,
    )


def _openai_mission(
    unit: CourseUnit, report: FeedbackReport, draft: str, chunks: List[Dict[str, object]]
) -> RevisionMission | None:
    if not has_openai_api_key():
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=get_openai_api_key(), timeout=25)
        response = client.responses.create(
            model=get_openai_model(),
            input=[{"role": "user", "content": _prompt(unit, report, draft, chunks)}],
            temperature=0.2,
            max_output_tokens=700,
        )
        payload = _parse_json_object(str(getattr(response, "output_text", "")))
        return _normalize_mission_payload(payload, unit, report, draft, chunks)
    except Exception:
        return None


def build_revision_mission(
    unit: CourseUnit,
    report: FeedbackReport,
    draft: str,
    chunks: List[Dict[str, object]],
) -> RevisionMission:
    """Build one revision mission tied to the latest attempt for a unit."""

    generated = _openai_mission(unit, report, draft, chunks)
    if generated is not None:
        return generated
    return _fallback_mission(unit, report, draft, chunks)
