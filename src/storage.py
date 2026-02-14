"""SQLite persistence for local progress, attempts, drafts, and coach history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Dict, Iterable, List

from .config import db_path, unlock_threshold
from .types import ChatTurn, FeedbackReport, ProgressRecord


def _connection(path=None):
    path = path or db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn=None):
    conn = conn or _connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_unit_id TEXT NOT NULL,
            unlocked_units TEXT NOT NULL,
            attempts TEXT NOT NULL,
            best_score_by_unit TEXT NOT NULL,
            last_opened_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT NOT NULL,
            draft TEXT NOT NULL,
            overall_score INTEGER NOT NULL,
            feedback_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS drafts (
            unit_id TEXT PRIMARY KEY,
            draft TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT NOT NULL,
            citations TEXT
        );
        """
    )
    conn.commit()


def _default_progress(unit_ids: List[str]) -> ProgressRecord:
    first_unit = unit_ids[0] if unit_ids else "0"
    return ProgressRecord(
        current_unit_id=first_unit,
        unlocked_units=[first_unit],
        attempts={},
        best_score_by_unit={},
        last_opened_at=datetime.utcnow().isoformat(),
    )


def load_progress(unit_ids: List[str]) -> ProgressRecord:
    conn = _connection()
    init_db(conn)
    row = conn.execute("SELECT * FROM progress WHERE id = 1").fetchone()
    if row is None:
        progress = _default_progress(unit_ids)
        persist_progress(progress, conn=conn)
        conn.close()
        return progress

    progress = ProgressRecord(
        current_unit_id=row["current_unit_id"],
        unlocked_units=json.loads(row["unlocked_units"]),
        attempts=json.loads(row["attempts"]),
        best_score_by_unit=json.loads(row["best_score_by_unit"]),
        last_opened_at=row["last_opened_at"],
    )

    if progress.current_unit_id not in unit_ids:
        progress.current_unit_id = unit_ids[0] if unit_ids else "0"
    progress.unlocked_units = [u for u in progress.unlocked_units if u in unit_ids]
    if not progress.unlocked_units:
        progress.unlocked_units = [unit_ids[0]] if unit_ids else ["0"]

    if progress.current_unit_id not in progress.unlocked_units:
        progress.current_unit_id = progress.unlocked_units[0]

    progress.last_opened_at = datetime.utcnow().isoformat()
    persist_progress(progress, conn=conn)
    conn.close()
    return progress


def persist_progress(progress: ProgressRecord, conn=None) -> None:
    conn = conn or _connection()
    init_db(conn)
    payload = progress.to_dict()
    conn.execute(
        """
        INSERT INTO progress (id, current_unit_id, unlocked_units, attempts, best_score_by_unit, last_opened_at)
        VALUES (1, :current_unit_id, :unlocked_units, :attempts, :best_score_by_unit, :last_opened_at)
        ON CONFLICT(id) DO UPDATE SET
            current_unit_id = excluded.current_unit_id,
            unlocked_units = excluded.unlocked_units,
            attempts = excluded.attempts,
            best_score_by_unit = excluded.best_score_by_unit,
            last_opened_at = excluded.last_opened_at;
        """,
        {
            "current_unit_id": payload["current_unit_id"],
            "unlocked_units": json.dumps(payload["unlocked_units"]),
            "attempts": json.dumps(payload["attempts"]),
            "best_score_by_unit": json.dumps(payload["best_score_by_unit"]),
            "last_opened_at": payload["last_opened_at"],
        },
    )
    conn.commit()


def set_current_unit(progress: ProgressRecord, unit_id: str) -> ProgressRecord:
    if unit_id in progress.unlocked_units:
        progress.current_unit_id = unit_id
        persist_progress(progress)
    return progress


def _next_unit_id(unit_id: str, all_units: List[str]) -> str | None:
    if unit_id not in all_units:
        return None
    idx = all_units.index(unit_id)
    if idx + 1 >= len(all_units):
        return None
    return all_units[idx + 1]


def add_feedback_attempt(
    progress: ProgressRecord,
    unit_id: str,
    draft: str,
    report: FeedbackReport,
    all_unit_ids: List[str],
) -> ProgressRecord:
    conn = _connection()
    init_db(conn)
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO attempts (unit_id, draft, overall_score, feedback_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (unit_id, draft, report.overall_score, json.dumps(report.to_dict()), now),
    )

    progress.attempts[unit_id] = progress.attempts.get(unit_id, 0) + 1
    progress.best_score_by_unit[unit_id] = max(
        progress.best_score_by_unit.get(unit_id, 0), report.overall_score
    )

    if report.overall_score >= unlock_threshold() and unit_id in all_unit_ids:
        nxt = _next_unit_id(unit_id, all_unit_ids)
        if nxt and nxt not in progress.unlocked_units:
            progress.unlocked_units.append(nxt)
            progress.unlocked_units.sort(key=lambda x: all_unit_ids.index(x))

    progress.last_opened_at = now
    persist_progress(progress, conn=conn)
    conn.commit()
    conn.close()
    return progress


def save_draft(unit_id: str, text: str) -> None:
    conn = _connection()
    init_db(conn)
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO drafts (unit_id, draft, updated_at) VALUES (?, ?, ?)"
        " ON CONFLICT(unit_id) DO UPDATE SET draft=excluded.draft, updated_at=excluded.updated_at",
        (unit_id, text, now),
    )
    conn.commit()
    conn.close()


def get_draft(unit_id: str) -> str:
    conn = _connection()
    init_db(conn)
    row = conn.execute("SELECT draft FROM drafts WHERE unit_id = ?", (unit_id,)).fetchone()
    conn.close()
    if row is None:
        return ""
    return row["draft"]


def get_attempts_for_unit(unit_id: str, limit: int | None = None) -> List[Dict[str, object]]:
    conn = _connection()
    init_db(conn)
    q = "SELECT id, unit_id, draft, overall_score, feedback_json, created_at FROM attempts WHERE unit_id = ? ORDER BY id DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q, (unit_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_latest_feedback_for_unit(unit_id: str) -> FeedbackReport | None:
    attempts = get_attempts_for_unit(unit_id, limit=1)
    if not attempts:
        return None
    return FeedbackReport.from_dict(json.loads(attempts[0]["feedback_json"]))


def save_chat_turn(unit_id: str, question: str, answer: str, citations: List[str] | None = None) -> None:
    conn = _connection()
    init_db(conn)
    citations_json = json.dumps(citations or [])
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO chat_turns (unit_id, question, answer, created_at, citations) VALUES (?, ?, ?, ?, ?)",
        (unit_id, question, answer, now, citations_json),
    )
    conn.commit()
    conn.close()


def get_chat_turns(unit_id: str, limit: int | None = None) -> List[Dict[str, object]]:
    conn = _connection()
    init_db(conn)
    q = "SELECT question, answer, created_at, citations FROM chat_turns WHERE unit_id = ? ORDER BY id DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q, (unit_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_attempts() -> List[Dict[str, object]]:
    conn = _connection()
    init_db(conn)
    rows = conn.execute(
        "SELECT id, unit_id, overall_score, created_at FROM attempts ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
