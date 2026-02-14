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
class LessonIdea:
    text: str
    citation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LessonIdea":
        if payload is None:
            return cls(text="", citation="p.0")
        return cls(
            text=str(payload.get("text", "")),
            citation=str(payload.get("citation", "p.0")),
        )


@dataclass
class LessonPack:
    unit_id: str
    summary: str
    key_ideas: List[LessonIdea]
    pitfalls: List[LessonIdea]
    reflection_questions: List[str]
    micro_drills: List[str]
    source_mode: str = "fallback_local"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "summary": self.summary,
            "key_ideas": [item.to_dict() for item in self.key_ideas],
            "pitfalls": [item.to_dict() for item in self.pitfalls],
            "reflection_questions": list(self.reflection_questions),
            "micro_drills": list(self.micro_drills),
            "source_mode": self.source_mode,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LessonPack":
        payload = payload or {}
        key_ideas = payload.get("key_ideas", [])
        pitfalls = payload.get("pitfalls", [])
        return cls(
            unit_id=str(payload.get("unit_id", "")),
            summary=str(payload.get("summary", "")),
            key_ideas=[
                item if isinstance(item, LessonIdea) else LessonIdea.from_dict(item)
                for item in key_ideas
                if isinstance(item, (dict, LessonIdea))
            ],
            pitfalls=[
                item if isinstance(item, LessonIdea) else LessonIdea.from_dict(item)
                for item in pitfalls
                if isinstance(item, (dict, LessonIdea))
            ],
            reflection_questions=[str(item) for item in payload.get("reflection_questions", [])],
            micro_drills=[str(item) for item in payload.get("micro_drills", [])],
            source_mode=str(payload.get("source_mode", "fallback_local")),
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
class RevisionMission:
    id: Optional[int]
    unit_id: str
    attempt_id: int
    focus_dimension: str
    title: str
    instructions: str
    checklist: List[str]
    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RevisionMission":
        payload = payload or {}
        mission_id = payload.get("id")
        return cls(
            id=int(mission_id) if mission_id is not None else None,
            unit_id=str(payload.get("unit_id", "")),
            attempt_id=int(payload.get("attempt_id", 0)),
            focus_dimension=str(payload.get("focus_dimension", "")),
            title=str(payload.get("title", "")),
            instructions=str(payload.get("instructions", "")),
            checklist=[str(item) for item in payload.get("checklist", [])],
            status=str(payload.get("status", "active")),
            created_at=str(payload.get("created_at", datetime.utcnow().isoformat())),
            completed_at=(
                str(payload.get("completed_at")) if payload.get("completed_at") is not None else None
            ),
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
class CoachEvidence:
    quote: str
    citation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CoachEvidence":
        payload = payload or {}
        return cls(
            quote=str(payload.get("quote", "")),
            citation=str(payload.get("citation", "p.0")),
        )


@dataclass
class CoachAnswer:
    answer: str
    citations: List[str]
    evidence: List[CoachEvidence]
    confidence: float
    is_refusal: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": list(self.citations),
            "evidence": [item.to_dict() for item in self.evidence],
            "confidence": self.confidence,
            "is_refusal": self.is_refusal,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CoachAnswer":
        payload = payload or {}
        return cls(
            answer=str(payload.get("answer", "")),
            citations=[str(item) for item in payload.get("citations", [])],
            evidence=[
                item if isinstance(item, CoachEvidence) else CoachEvidence.from_dict(item)
                for item in payload.get("evidence", [])
                if isinstance(item, (dict, CoachEvidence))
            ],
            confidence=float(payload.get("confidence", 0.0) or 0.0),
            is_refusal=bool(payload.get("is_refusal", False)),
        )


@dataclass
class ChatTurn:
    unit_id: str
    question: str
    answer: str
    citations: List[str] = field(default_factory=list)
    evidence: List[CoachEvidence] = field(default_factory=list)
    confidence: Optional[float] = None

    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "question": self.question,
            "answer": self.answer,
            "citations": list(self.citations),
            "evidence": [item.to_dict() for item in self.evidence],
            "confidence": self.confidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ChatTurn":
        payload = payload or {}
        return cls(
            unit_id=str(payload.get("unit_id", "")),
            question=str(payload.get("question", "")),
            answer=str(payload.get("answer", "")),
            citations=[str(item) for item in payload.get("citations", [])],
            evidence=[
                item if isinstance(item, CoachEvidence) else CoachEvidence.from_dict(item)
                for item in payload.get("evidence", [])
                if isinstance(item, (dict, CoachEvidence))
            ],
            confidence=(
                float(payload.get("confidence"))
                if payload.get("confidence") is not None
                else None
            ),
            created_at=str(payload.get("created_at", datetime.utcnow().isoformat())),
        )
