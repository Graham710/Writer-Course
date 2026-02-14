"""Feedback evaluation using OpenAI Responses API with local fallback."""

from __future__ import annotations

import json
import re
from typing import Dict, List

from . import types
from .config import get_openai_api_key, get_openai_model, has_openai_api_key, unlock_threshold
from .types import CourseUnit, FeedbackReport, LineNote


RUBRIC_DIMENSIONS = [
    "concept_application",
    "narrative_effectiveness",
    "language_precision",
    "revision_readiness",
]


def _fallback_report(unit: CourseUnit, draft_text: str, chunks: List[Dict[str, object]]) -> FeedbackReport:
    text = (draft_text or "").strip()
    objective_terms = [term.lower() for objective in unit.learning_objectives for term in objective.split()]
    draft_lower = text.lower()
    objective_hits = sum(1 for term in objective_terms if term and term in draft_lower)

    lines = [line.strip() for line in re.split(r"\n+", text) if line.strip()]
    concept = min(100, 35 + objective_hits)
    narrative = min(100, 30 + min(120, len(lines) * 8) + (20 if text else 0))
    language = min(100, 35 + int(len(set(text.split())) * 0.7) + (10 if any(word in draft_lower for word in ["show", "scene", "voice", "tone"]) else 0))
    revision = min(100, 20 + len(lines) * 6 + (15 if len(text) > 200 else 0))
    rubric = {
        "concept_application": concept,
        "narrative_effectiveness": narrative,
        "language_precision": language,
        "revision_readiness": revision,
    }

    weighted = (
        rubric["concept_application"] * 0.35
        + rubric["narrative_effectiveness"] * 0.30
        + rubric["language_precision"] * 0.20
        + rubric["revision_readiness"] * 0.15
    )
    overall = int(round(weighted))
    citation = f"p.{chunks[0]['page']}" if chunks else "p.0"

    line_notes = []
    for idx, line in enumerate(lines[:3], start=1):
        line_notes.append(
            LineNote(
                line_number=idx,
                text_excerpt=line[:120],
                comment=f"Check if this line supports the unit goals more directly. ({citation})",
                citation=citation,
            )
        )

    strengths = [
        f"The draft shows craft effort and can be improved by adding precise scene anchors. ({citation})",
    ]
    risks = [
        f"Some transitions are broad and may blur focus; tighten around concrete moments. ({citation})",
    ]
    revision_plan = [
        "Cut one generalized sentence and replace with scene detail.",
        "Add one more internal beat that changes the reader's expectation.",
        "Read once and mark lines that are not tied to action or perspective.",
    ]

    return FeedbackReport(
        overall_score=overall,
        rubric_scores=rubric,
        strengths=strengths,
        craft_risks=risks,
        line_notes=line_notes,
        revision_plan=revision_plan,
        unlock_eligible=overall >= unlock_threshold(),
    )


def _parse_json_object(raw: str) -> Dict:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or start >= end:
        raise ValueError("No JSON object found")
    return json.loads(raw[start : end + 1])


def _normalize_report(payload: Dict, unit: CourseUnit, chunks: List[Dict[str, object]], original_score: int | None = None) -> FeedbackReport:
    report_payload = dict(payload or {})

    rubric = report_payload.get("rubric_scores", {}) if isinstance(report_payload.get("rubric_scores"), dict) else {}
    normalized_rubric: Dict[str, int] = {}
    for dim in RUBRIC_DIMENSIONS:
        raw_value = rubric.get(dim, 0)
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            value = 0
        normalized_rubric[dim] = max(0, min(100, value))

    if "overall_score" in report_payload:
        try:
            overall = int(report_payload["overall_score"])
        except (TypeError, ValueError):
            overall = int(round(
                normalized_rubric["concept_application"] * 0.35
                + normalized_rubric["narrative_effectiveness"] * 0.30
                + normalized_rubric["language_precision"] * 0.20
                + normalized_rubric["revision_readiness"] * 0.15
            ))
    else:
        overall = original_score or int(round(
            normalized_rubric["concept_application"] * 0.35
            + normalized_rubric["narrative_effectiveness"] * 0.30
            + normalized_rubric["language_precision"] * 0.20
            + normalized_rubric["revision_readiness"] * 0.15
        ))

    overall = max(0, min(100, overall))

    citation_fallback = f"p.{chunks[0]['page']}" if chunks else "p.0"

    strengths = report_payload.get("strengths", [])
    if not isinstance(strengths, list):
        strengths = []
    strengths = [str(item) for item in strengths[:4]]
    if not strengths:
        strengths = [f"Clear draft direction is visible. ({citation_fallback})"]

    risks = report_payload.get("craft_risks", [])
    if not isinstance(risks, list):
        risks = []
    risks = [str(item) for item in risks[:4]]
    if not risks:
        risks = [f"Tighten concrete detail and perspective alignment. ({citation_fallback})"]

    raw_notes = report_payload.get("line_notes", [])
    line_notes = []
    if isinstance(raw_notes, list):
        for note in raw_notes[:6]:
            if not isinstance(note, dict):
                continue
            line_notes.append(
                LineNote(
                    line_number=int(note.get("line_number", 0) or 0),
                    text_excerpt=str(note.get("text_excerpt", "")),
                    comment=str(note.get("comment", "")),
                    citation=note.get("citation", citation_fallback),
                )
            )
    if not line_notes:
        fallback_text = (unit.title or "current unit")
        line_notes = [
            LineNote(
                line_number=1,
                text_excerpt=fallback_text,
                comment=f"Start by grounding scene details in the unit's topic. ({citation_fallback})",
                citation=citation_fallback,
            )
        ]

    revision_plan = report_payload.get("revision_plan", [])
    if not isinstance(revision_plan, list):
        revision_plan = []
    revision_plan = [str(item) for item in revision_plan[:6]]
    if not revision_plan:
        revision_plan = [
            "Rewrite first sentence so readers can identify location and point of view.",
            "Replace one abstract claim with a physical detail.",
            "Add one stronger transition between scenes.",
        ]

    return FeedbackReport(
        overall_score=overall,
        rubric_scores=normalized_rubric,
        strengths=strengths,
        craft_risks=risks,
        line_notes=line_notes,
        revision_plan=revision_plan,
        unlock_eligible=overall >= unlock_threshold(),
    )


def _build_prompt(unit: CourseUnit, draft_text: str, chunks: List[Dict[str, object]]) -> str:
    chunk_summary = "\n\n".join(
        [f"[p.{item['page']}] {item['text'][:700]}" for item in chunks[:8]]
    )
    objectives = "; ".join(unit.learning_objectives)
    schema = """{
  "overall_score": int,
  "rubric_scores": {
    "concept_application": int,
    "narrative_effectiveness": int,
    "language_precision": int,
    "revision_readiness": int
  },
  "strengths": [string list],
  "craft_risks": [string list],
  "line_notes": [
    {"line_number": int, "text_excerpt": string, "comment": string, "citation": string}
  ],
  "revision_plan": [string list],
  "unlock_eligible": bool
}"""
    prompt = f"""You are a strict literary writing coach. Review only the provided course unit context.

Unit {unit.id}: {unit.title}
Learning objectives: {objectives}

Course context:
{chunk_summary}

Student draft:
{draft_text}

Return JSON with this exact schema:
{schema}

Rules:
- Use only unit context and do not use external writing theory.
- Every strength, risk, and note should include a citation in the form (p.NUM).
- numeric scores must be 0-100.
- overall_score is weighted concept_application 35, narrative 30, language 20, revision 15.
"""
    return prompt


def evaluate_draft(unit: CourseUnit, draft_text: str, chunks: List[Dict[str, object]]) -> FeedbackReport:
    if not has_openai_api_key():
        return _fallback_report(unit, draft_text, chunks)

    context = chunks[:12]
    prompt = _build_prompt(unit, draft_text, context)
    try:
        from openai import OpenAI

        client = OpenAI(api_key=get_openai_api_key(), timeout=30)
        response = client.responses.create(
            model=get_openai_model(),
            input=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        raw = _extract_model_text(response)
        payload = _parse_json_object(raw)
        return _normalize_report(payload, unit, context)
    except Exception:
        return _fallback_report(unit, draft_text, context)


def _extract_model_text(response) -> str:
    if hasattr(response, "output_text") and isinstance(response.output_text, str):
        return response.output_text

    # Best effort fallback for responses payload formats.
    output = getattr(response, "output", [])
    pieces: List[str] = []
    for item in output:
        content = getattr(item, "content", None)
        if isinstance(content, list):
            for block in content:
                if getattr(block, "type", "") == "output_text":
                    pieces.append(getattr(block, "text", ""))
        elif isinstance(content, str):
            pieces.append(content)
    return "".join(pieces)
