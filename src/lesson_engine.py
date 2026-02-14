"""Lesson pack generation and caching for unit study content."""

from __future__ import annotations

import json
import re
from typing import Dict, List

from .config import (
    chunk_chars,
    data_dir,
    get_openai_api_key,
    get_openai_model,
    get_pdf_path,
    has_openai_api_key,
    lesson_packs_path,
)
from .types import CourseUnit, LessonIdea, LessonPack

PACK_VERSION = 1
_CITATION_RE = re.compile(r"^p\.(\d+)$")


def _unit_cache_fingerprint(units: List[CourseUnit]) -> Dict[str, object]:
    return {
        "unit_count": len(units),
        "units": [
            {"id": unit.id, "start_page": unit.start_page, "end_page": unit.end_page}
            for unit in units
        ],
    }


def _citation_page(citation: str) -> int | None:
    match = _CITATION_RE.match((citation or "").strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _valid_citation(citation: str, valid_pages: set[int]) -> bool:
    page = _citation_page(citation)
    return page is not None and page in valid_pages


def _safe_sentence(text: str, max_len: int = 170) -> str:
    parts = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", text or "") if segment.strip()]
    sentence = parts[0] if parts else (text or "").strip()
    return sentence[:max_len].strip() or "Focus on how this unit handles craft choices."


def _chunk_rank(unit: CourseUnit, chunks: List[Dict[str, object]]) -> List[Dict[str, object]]:
    objective_terms = {
        token.lower()
        for objective in unit.learning_objectives
        for token in re.findall(r"[a-z]{3,}", objective.lower())
    }

    scored = []
    for chunk in chunks:
        text = str(chunk.get("text", ""))
        tokens = set(re.findall(r"[a-z]{3,}", text.lower()))
        overlap = len(tokens.intersection(objective_terms))
        score = overlap * 6 + min(8, len(text) // 180)
        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored]


def _fallback_lesson_pack(unit: CourseUnit, chunks: List[Dict[str, object]]) -> LessonPack:
    ranked = _chunk_rank(unit, chunks)
    if not ranked:
        base_page = max(1, unit.start_page)
        citation = f"p.{base_page}"
        key_ideas = [
            LessonIdea(
                text=f"Apply this unit's central technique directly to scene-level choices ({idx + 1}/5).",
                citation=citation,
            )
            for idx in range(5)
        ]
        pitfalls = [
            LessonIdea(
                text=f"Avoid drifting away from the unit objective before revision pass {idx + 1}.",
                citation=citation,
            )
            for idx in range(3)
        ]
        return LessonPack(
            unit_id=unit.id,
            summary="This unit centers on one craft move at a time and asks for deliberate revision.",
            key_ideas=key_ideas,
            pitfalls=pitfalls,
            reflection_questions=[
                "Which craft move from this unit is currently strongest in your draft?",
                "Where does your draft lose control of point of view or scene pressure?",
                "What single change would improve clarity most in the next revision pass?",
            ],
            micro_drills=[
                "Write 5 lines that keep one perspective fixed while raising scene tension.",
                "Rewrite one paragraph using sharper sensory details tied to motive.",
            ],
            source_mode="fallback_local",
        )

    first = ranked[0]
    first_page = int(first.get("page", unit.start_page or 1) or 1)
    summary = _safe_sentence(str(first.get("text", "")), max_len=320)

    key_ideas: List[LessonIdea] = []
    for idx in range(5):
        source = ranked[idx % len(ranked)]
        page = int(source.get("page", first_page) or first_page)
        text = _safe_sentence(str(source.get("text", "")), max_len=175)
        key_ideas.append(LessonIdea(text=text, citation=f"p.{page}"))

    pitfalls: List[LessonIdea] = []
    for idx in range(3):
        source = ranked[(idx + 1) % len(ranked)]
        page = int(source.get("page", first_page) or first_page)
        objective = unit.learning_objectives[idx % len(unit.learning_objectives)] if unit.learning_objectives else "the core technique"
        pitfalls.append(
            LessonIdea(
                text=f"Do not replace {objective.lower()} with abstract summary; keep it visible in concrete scene action.",
                citation=f"p.{page}",
            )
        )

    objectives = unit.learning_objectives or [f"Apply the key move in {unit.title}."]
    reflection_questions = [
        f"Where in your latest draft do you explicitly apply: {objectives[0]}?",
        f"What sentence currently weakens this unit's goal: {objectives[min(1, len(objectives)-1)]}?",
        f"What change would make your next revision align better with {unit.title}?",
    ]

    micro_drills = [
        "Draft 6 lines that introduce a conflict beat using only observable actions.",
        "Revise one paragraph by cutting abstraction and replacing it with sensory detail.",
    ]

    return LessonPack(
        unit_id=unit.id,
        summary=summary,
        key_ideas=key_ideas,
        pitfalls=pitfalls,
        reflection_questions=reflection_questions,
        micro_drills=micro_drills,
        source_mode="fallback_local",
    )


def _build_openai_prompt(unit: CourseUnit, chunks: List[Dict[str, object]]) -> str:
    context = "\n\n".join(
        f"[p.{chunk.get('page', 0)}] {str(chunk.get('text', ''))[:650]}"
        for chunk in chunks[:10]
    )
    objectives = "; ".join(unit.learning_objectives)

    return f"""You are building a study pack for one writing-course unit.

Unit: {unit.id} - {unit.title}
Learning objectives: {objectives}

Course context (PDF only):
{context}

Return JSON only with this exact shape:
{{
  "summary": "short paragraph",
  "key_ideas": [{{"text":"...","citation":"p.NUM"}}],
  "pitfalls": [{{"text":"...","citation":"p.NUM"}}],
  "reflection_questions": ["..."],
  "micro_drills": ["..."]
}}

Rules:
- Use only the provided context.
- key_ideas must be exactly 5 items.
- pitfalls must be exactly 3 items.
- reflection_questions must be exactly 3 items.
- micro_drills must be exactly 2 items.
- Every key idea and pitfall must include citation in citation field exactly as p.NUM.
"""


def _parse_json_object(raw: str) -> Dict[str, object]:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or start >= end:
        raise ValueError("No JSON object found")
    return json.loads(raw[start : end + 1])


def _normalize_idea_list(
    raw_items: object,
    valid_pages: set[int],
    fallback_items: List[LessonIdea],
    expected_count: int,
) -> List[LessonIdea]:
    normalized: List[LessonIdea] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            citation = str(item.get("citation", "")).strip()
            if not text or not _valid_citation(citation, valid_pages):
                continue
            normalized.append(LessonIdea(text=text, citation=citation))
            if len(normalized) >= expected_count:
                break

    while len(normalized) < expected_count:
        normalized.append(fallback_items[len(normalized) % len(fallback_items)])

    return normalized[:expected_count]


def _normalize_text_list(raw_items: object, expected_count: int, fallback_items: List[str]) -> List[str]:
    items = [str(item).strip() for item in raw_items] if isinstance(raw_items, list) else []
    items = [item for item in items if item]
    while len(items) < expected_count:
        items.append(fallback_items[len(items) % len(fallback_items)])
    return items[:expected_count]


def _openai_pack(unit: CourseUnit, chunks: List[Dict[str, object]]) -> LessonPack | None:
    if not has_openai_api_key() or not chunks:
        return None

    fallback = _fallback_lesson_pack(unit, chunks)
    valid_pages = {int(chunk.get("page", 0) or 0) for chunk in chunks}

    try:
        from openai import OpenAI

        client = OpenAI(api_key=get_openai_api_key(), timeout=25)
        response = client.responses.create(
            model=get_openai_model(),
            input=[{"role": "user", "content": _build_openai_prompt(unit, chunks)}],
            temperature=0.1,
            max_output_tokens=1200,
        )
        raw = str(getattr(response, "output_text", ""))
        payload = _parse_json_object(raw)

        summary = str(payload.get("summary", "")).strip() or fallback.summary
        key_ideas = _normalize_idea_list(
            payload.get("key_ideas"), valid_pages, fallback.key_ideas, expected_count=5
        )
        pitfalls = _normalize_idea_list(
            payload.get("pitfalls"), valid_pages, fallback.pitfalls, expected_count=3
        )
        reflection_questions = _normalize_text_list(
            payload.get("reflection_questions"), 3, fallback.reflection_questions
        )
        micro_drills = _normalize_text_list(payload.get("micro_drills"), 2, fallback.micro_drills)

        return LessonPack(
            unit_id=unit.id,
            summary=summary,
            key_ideas=key_ideas,
            pitfalls=pitfalls,
            reflection_questions=reflection_questions,
            micro_drills=micro_drills,
            source_mode="openai_structured",
        )
    except Exception:
        return None


def build_lesson_pack(unit: CourseUnit, chunks: List[Dict[str, object]]) -> LessonPack:
    """Build one lesson pack using OpenAI when available, then deterministic fallback."""

    generated = _openai_pack(unit, chunks)
    if generated is not None:
        return generated
    return _fallback_lesson_pack(unit, chunks)


def _cache_compatible(payload: object, units: List[CourseUnit]) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("source_pdf") != get_pdf_path().name:
        return False
    if payload.get("unit_layout") != _unit_cache_fingerprint(units):
        return False

    chunk_config = payload.get("chunk_config")
    if not isinstance(chunk_config, dict):
        return False
    if chunk_config.get("max_chars") != chunk_chars():
        return False

    return payload.get("pack_version") == PACK_VERSION


def _pack_valid_for_unit(pack: LessonPack, unit: CourseUnit) -> bool:
    valid_pages = set(range(unit.start_page, unit.end_page + 1))
    if not pack.summary.strip():
        return False
    if len(pack.key_ideas) != 5 or len(pack.pitfalls) != 3:
        return False
    if len(pack.reflection_questions) != 3 or len(pack.micro_drills) != 2:
        return False

    for item in pack.key_ideas + pack.pitfalls:
        if not item.text.strip() or not _valid_citation(item.citation, valid_pages):
            return False
    return True


def _read_cached_packs() -> Dict[str, object]:
    path = lesson_packs_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_or_build_lesson_packs(
    units: List[CourseUnit], unit_chunks: Dict[str, List[Dict[str, object]]]
) -> Dict[str, LessonPack]:
    """Load lesson packs from cache or rebuild them when cache is stale."""

    data_dir().mkdir(parents=True, exist_ok=True)
    path = lesson_packs_path()
    cached = _read_cached_packs()

    if _cache_compatible(cached, units):
        raw_packs = cached.get("packs")
        if isinstance(raw_packs, list):
            mapped: Dict[str, LessonPack] = {}
            for item in raw_packs:
                if not isinstance(item, dict):
                    continue
                pack = LessonPack.from_dict(item)
                mapped[pack.unit_id] = pack
            if set(mapped.keys()) == {unit.id for unit in units}:
                valid = True
                for unit in units:
                    if not _pack_valid_for_unit(mapped[unit.id], unit):
                        valid = False
                        break
                if valid:
                    return mapped

    mapped: Dict[str, LessonPack] = {}
    for unit in units:
        mapped[unit.id] = build_lesson_pack(unit, unit_chunks.get(unit.id, []))

    payload = {
        "source_pdf": get_pdf_path().name,
        "unit_layout": _unit_cache_fingerprint(units),
        "chunk_config": {"max_chars": chunk_chars()},
        "pack_version": PACK_VERSION,
        "packs": [mapped[unit.id].to_dict() for unit in units],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return mapped
