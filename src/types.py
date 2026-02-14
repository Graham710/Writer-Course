"""Data models used across the Writer Course app."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class LineNote:
    """Line-level feedback note."""

    line_number: int
    text_excerpt: str
    comment: str
    citation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LineNote":
        if payload is None:
            return cls(line_number=0, text_excerpt="", comment="")
        return cls(
            line_number=int(payload.get("line_number", 0)),
            text_excerpt=str(payload.get("text_excerpt", "")),
            comment=str(payload.get("comment", "")),
            citation=payload.get("citation"),
        )


@dataclass
class CourseUnit:
    id: str
    title: str
    start_page: int
    end_page: int
    learning_objectives: List[str] = field(default_factory=list)
    source_chunks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CourseUnit":
        return cls(
            id=str(payload["id"]),
            title=str(payload["title"]),
            start_page=int(payload["start_page"]),
            end_page=int(payload["end_page"]),
            learning_objectives=list(payload.get("learning_objectives", [])),
            source_chunks=list(payload.get("source_chunks", [])),
        )


@dataclass
class ExerciseSpec:
    unit_id: str
    source_mode: str
    prompt: str
    success_criteria: List[str]
    timebox_minutes: int
    kind: str = "core"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ExerciseSpec":
        return cls(
            unit_id=str(payload["unit_id"]),
            source_mode=str(payload["source_mode"]),
            prompt=str(payload["prompt"]),
            success_criteria=list(payload.get("success_criteria", [])),
            timebox_minutes=int(payload["timebox_minutes"]),
            kind=str(payload.get("kind", "core")),
        )


@dataclass
class FeedbackReport:
    overall_score: int
    rubric_scores: Dict[str, int]
    strengths: List[str]
    craft_risks: List[str]
    line_notes: List[LineNote]
    revision_plan: List[str]
    unlock_eligible: bool

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["line_notes"] = [note.to_dict() for note in self.line_notes]
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FeedbackReport":
        line_notes = [
            note if isinstance(note, LineNote) else LineNote.from_dict(note)
            for note in payload.get("line_notes", [])
        ]
        return cls(
            overall_score=int(payload.get("overall_score", 0)),
            rubric_scores=dict(payload.get("rubric_scores", {})),
            strengths=list(payload.get("strengths", [])),
            craft_risks=list(payload.get("craft_risks", [])),
            line_notes=line_notes,
            revision_plan=list(payload.get("revision_plan", [])),
            unlock_eligible=bool(payload.get("unlock_eligible", False)),
        )


@dataclass
class ProgressRecord:
    current_unit_id: str
    unlocked_units: List[str]
    attempts: Dict[str, int]
    best_score_by_unit: Dict[str, int]
    last_opened_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ProgressRecord":
        return cls(
            current_unit_id=str(payload.get("current_unit_id", "0")),
            unlocked_units=list(payload.get("unlocked_units", ["0"])),
            attempts={k: int(v) for k, v in payload.get("attempts", {}).items()},
            best_score_by_unit={k: int(v) for k, v in payload.get("best_score_by_unit", {}).items()},
            last_opened_at=str(payload.get("last_opened_at", datetime.utcnow().isoformat())),
        )


@dataclass
class ChatTurn:
    unit_id: str
    question: str
    answer: str
    citations: List[str]

    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
