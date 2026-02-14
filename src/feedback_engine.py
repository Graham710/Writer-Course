"""Feedback evaluation using OpenAI Responses API with local fallback."""

from __future__ import annotations

import json
import re
import os
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

_REASONING_EFFORT_OPTIONS = {"none", "minimal", "low", "medium", "high", "xhigh"}
_FAST_MAX_CHARS = 900
_DEEP_MIN_CHARS = 2200


def _read_env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value


def _read_env_int(name: str, default: int | None) -> int | None:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value


def _read_reasoning_effort(level: str, default: str) -> str:
    raw = os.getenv(f"OPENAI_FEEDBACK_{level.upper()}_REASONING_EFFORT", "")
    effort = raw.strip().lower()
    return effort if effort in _REASONING_EFFORT_OPTIONS else default


def _fallback_report(unit: CourseUnit, draft_text: str, chunks: List[Dict[str, object]]) -> FeedbackReport:
    text = (draft_text or "").strip()
    objective_terms = [term.lower() for objective in unit.learning_objectives for term in objective.split()]
    draft_lower = text.lower()
    objective_hits = sum(1 for term in objective_terms if term and term in draft_lower)

    lines = [line.strip() for line in re.split(r"\n+", text) if line.strip()]
    words = re.findall(r"\b[a-z']+\b", draft_lower)
    unique_words = len(set(words))
    line_count = len(lines)

    concept = min(100, 30 + objective_hits + min(40, line_count * 4))
    narrative = min(100, 15 + min(90, len(words)) + (8 if line_count >= 3 else 0))
    language = min(
        100,
        22
        + int(unique_words * 0.35)
        + (10 if any(word in draft_lower for word in ["scene", "detail", "voice", "show", "saw", "heard"]) else 0),
    )
    revision = min(100, 18 + len(lines) * 3 + (8 if len(text) > 240 else 0))
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
        if idx == 1:
            comment = f"Anchor this opening with location/time and perspective before broader claims. ({citation})"
        elif idx == 2:
            comment = f"Convert abstract language here into observable action tied to stakes. ({citation})"
        else:
            comment = f"Check whether this line keeps the same point of view and pressure. ({citation})"

        line_notes.append(
            LineNote(
                line_number=idx,
                text_excerpt=line[:120],
                comment=comment,
                citation=citation,
            )
        )

    strengths = []
    if line_count >= 3:
        strengths.append(f"The draft has a readable beat flow that can support revision work. ({citation})")
    if any(word in draft_lower for word in ["scene", "detail", "voice", "character", "perspective"]):
        strengths.append(f"You already use concrete craft signals that readers can follow. ({citation})")
    if objective_hits > 0:
        strengths.append(f"Draft language maps to unit vocabulary in places. ({citation})")
    if not strengths:
        strengths.append(f"The draft has a clear direction and is ready for focused revision passes. ({citation})")

    risks = []
    if line_count < 3:
        risks.append(f"The draft may be too short for a full scene; add one more concrete beat. ({citation})")
    if objective_hits == 0:
        risks.append(f"Alignment with the unit goal is weak; restate one objective in scene terms. ({citation})")
    if not any(word in draft_lower for word in ["show", "showed", "saw", "heard", "felt", "replied"]):
        risks.append(f"Many moves are abstract; replace summary sentences with physical or behavioral detail. ({citation})")
    if not risks:
        risks.append(f"Line transitions need one clearer shift of stakes or perspective to avoid repetition. ({citation})")

    revision_plan = [
        f"Add an opening anchor: who is present, where, and what changes within the scene. ({citation})",
        f"Replace one generalized line with a direct action or sensory detail. ({citation})",
        f"Keep one perspective for the scene and remove any sentence that drifts into a different one. ({citation})",
    ]
    if objective_hits == 0:
        revision_plan.insert(
            0,
            f"Rewrite one line to include a key unit objective term. ({citation})",
        )
    if line_count >= 5:
        revision_plan.append(
            "Mark every sentence as setup, action, or consequence and remove anything that fits none. "
            f"({citation})"
        )

    return FeedbackReport(
        overall_score=overall,
        rubric_scores=rubric,
        strengths=strengths,
        craft_risks=risks,
        line_notes=line_notes,
        revision_plan=revision_plan,
        unlock_eligible=overall >= unlock_threshold(),
    )


def _feedback_profile(draft_text: str) -> str:
    text = (draft_text or "").strip()
    if len(text) <= _FAST_MAX_CHARS:
        return "FAST"
    if len(text) >= _DEEP_MIN_CHARS:
        return "DEEP"
    return "STANDARD"


def _feedback_runtime_options(draft_text: str) -> Dict[str, object]:
    profile = _feedback_profile(draft_text)
    if profile == "FAST":
        return {
            "temperature": _read_env_float("OPENAI_FEEDBACK_FAST_TEMPERATURE", 0.12),
            "max_output_tokens": _read_env_int("OPENAI_FEEDBACK_FAST_MAX_OUTPUT_TOKENS", 500),
            "reasoning_effort": _read_reasoning_effort(profile, "low"),
        }
    if profile == "DEEP":
        return {
            "temperature": _read_env_float("OPENAI_FEEDBACK_DEEP_TEMPERATURE", 0.18),
            "max_output_tokens": _read_env_int("OPENAI_FEEDBACK_DEEP_MAX_OUTPUT_TOKENS", 2000),
            "reasoning_effort": _read_reasoning_effort(profile, "high"),
        }
    return {
        "temperature": _read_env_float("OPENAI_FEEDBACK_STANDARD_TEMPERATURE", 0.15),
        "max_output_tokens": _read_env_int("OPENAI_FEEDBACK_STANDARD_MAX_OUTPUT_TOKENS", 1000),
        "reasoning_effort": _read_reasoning_effort(profile, "medium"),
    }


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
- Return JSON only; no wrapper text.
- Provide 2-3 strengths, 2-3 risks, and 3-5 revision items.
- Every strength, risk, note, and revision item must include at least one citation in the form (p.NUM).
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
        runtime = _feedback_runtime_options(draft_text)
        request_kwargs = {
            "model": get_openai_model(),
            "input": [{"role": "user", "content": prompt}],
            "temperature": float(runtime["temperature"]),
        }
        max_output_tokens = runtime["max_output_tokens"]
        if isinstance(max_output_tokens, int):
            request_kwargs["max_output_tokens"] = max_output_tokens
        reasoning_effort = runtime["reasoning_effort"]
        if isinstance(reasoning_effort, str) and reasoning_effort in _REASONING_EFFORT_OPTIONS:
            request_kwargs["reasoning"] = {"effort": reasoning_effort}
        response = client.responses.create(
            **request_kwargs,
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
