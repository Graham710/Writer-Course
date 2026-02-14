"""SQLite persistence for local progress, attempts, drafts, and coach history."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Dict, List

from .config import db_path
from .types import ChatTurn, FeedbackReport, ProgressRecord, RevisionMission


def _connection(path=None):
    path = path or db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def _ensure_column(conn: sqlite3.Connection, table: str, column_definition: str) -> None:
    column_name = column_definition.split()[0]
    if column_name in _table_columns(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_definition}")


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

        CREATE TABLE IF NOT EXISTS revision_missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT NOT NULL,
            attempt_id INTEGER NOT NULL,
            focus_dimension TEXT NOT NULL,
            title TEXT NOT NULL,
            instructions TEXT NOT NULL,
            checklist_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        """
    )

    # Migration-safe additions for existing DBs.
    _ensure_column(conn, "chat_turns", "evidence_json TEXT")
    _ensure_column(conn, "chat_turns", "confidence REAL")

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
    """Persist the progress envelope back to SQLite."""

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
    """Persist selection if the unit is unlocked and return updated progress."""

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


def add_feedback_attempt_with_id(
    progress: ProgressRecord,
    unit_id: str,
    draft: str,
    report: FeedbackReport,
    all_unit_ids: List[str],
) -> tuple[ProgressRecord, int]:
    """Record an attempt and return updated progress with inserted attempt id."""

    conn = _connection()
    init_db(conn)
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        "INSERT INTO attempts (unit_id, draft, overall_score, feedback_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (unit_id, draft, report.overall_score, json.dumps(report.to_dict()), now),
    )

    progress.attempts[unit_id] = progress.attempts.get(unit_id, 0) + 1
    progress.best_score_by_unit[unit_id] = max(
        progress.best_score_by_unit.get(unit_id, 0), report.overall_score
    )

    if unit_id in all_unit_ids:
        nxt = _next_unit_id(unit_id, all_unit_ids)
        if nxt and nxt not in progress.unlocked_units:
            progress.unlocked_units.append(nxt)
            progress.unlocked_units.sort(key=lambda x: all_unit_ids.index(x))

    progress.last_opened_at = now
    persist_progress(progress, conn=conn)
    conn.commit()
    conn.close()
    attempt_id = int(cursor.lastrowid or 0)
    return progress, attempt_id


def add_feedback_attempt(
    progress: ProgressRecord,
    unit_id: str,
    draft: str,
    report: FeedbackReport,
    all_unit_ids: List[str],
) -> ProgressRecord:
    """Record an attempt and unlock the next unit on the submission."""

    progress, _attempt_id = add_feedback_attempt_with_id(
        progress=progress,
        unit_id=unit_id,
        draft=draft,
        report=report,
        all_unit_ids=all_unit_ids,
    )
    return progress


def save_draft(unit_id: str, text: str) -> None:
    """Persist draft text for a unit in the `drafts` table."""

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
    """Load persisted draft for a unit."""

    conn = _connection()
    init_db(conn)
    row = conn.execute("SELECT draft FROM drafts WHERE unit_id = ?", (unit_id,)).fetchone()
    conn.close()
    if row is None:
        return ""
    return row["draft"]


def get_attempts_for_unit(unit_id: str, limit: int | None = None) -> List[Dict[str, object]]:
    """Fetch attempt rows for a unit, newest first."""

    conn = _connection()
    init_db(conn)
    q = "SELECT id, unit_id, draft, overall_score, feedback_json, created_at FROM attempts WHERE unit_id = ? ORDER BY id DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q, (unit_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_latest_feedback_for_unit(unit_id: str) -> FeedbackReport | None:
    """Return latest attempt feedback for a unit, if present."""

    attempts = get_attempts_for_unit(unit_id, limit=1)
    if not attempts:
        return None
    return FeedbackReport.from_dict(json.loads(attempts[0]["feedback_json"]))


def _serialize_evidence(evidence: List[dict] | None) -> str:
    return json.dumps(evidence or [])


def _deserialize_json_list(raw: object) -> List[object]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except Exception:
        return []


def save_chat_turn(
    unit_id: str,
    question: str,
    answer: str,
    citations: List[str] | None = None,
    evidence: List[dict] | None = None,
    confidence: float | None = None,
) -> None:
    """Persist a coach interaction turn."""

    conn = _connection()
    init_db(conn)
    citations_json = json.dumps(citations or [])
    evidence_json = _serialize_evidence(evidence)
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO chat_turns (unit_id, question, answer, created_at, citations, evidence_json, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (unit_id, question, answer, now, citations_json, evidence_json, confidence),
    )
    conn.commit()
    conn.close()


def get_chat_turns(unit_id: str, limit: int | None = None) -> List[Dict[str, object]]:
    """Fetch recent coach turns for a unit, newest first."""

    conn = _connection()
    init_db(conn)
    q = (
        "SELECT question, answer, created_at, citations, evidence_json, confidence "
        "FROM chat_turns WHERE unit_id = ? ORDER BY id DESC"
    )
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q, (unit_id,)).fetchall()
    conn.close()

    payload: List[Dict[str, object]] = []
    for row in rows:
        item = dict(row)
        item["citations"] = [str(value) for value in _deserialize_json_list(item.get("citations"))]
        evidence_list = _deserialize_json_list(item.get("evidence_json"))
        item["evidence"] = [value for value in evidence_list if isinstance(value, dict)]
        payload.append(item)
    return payload


def save_revision_mission(mission: RevisionMission) -> RevisionMission:
    """Insert or update a revision mission and return the persisted model."""

    conn = _connection()
    init_db(conn)
    payload = mission.to_dict()
    checklist_json = json.dumps(payload.get("checklist", []))

    if mission.id is None:
        cursor = conn.execute(
            """
            INSERT INTO revision_missions (
                unit_id, attempt_id, focus_dimension, title, instructions, checklist_json,
                status, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mission.unit_id,
                mission.attempt_id,
                mission.focus_dimension,
                mission.title,
                mission.instructions,
                checklist_json,
                mission.status,
                mission.created_at,
                mission.completed_at,
            ),
        )
        mission.id = int(cursor.lastrowid or 0)
    else:
        conn.execute(
            """
            UPDATE revision_missions
            SET unit_id = ?, attempt_id = ?, focus_dimension = ?, title = ?,
                instructions = ?, checklist_json = ?, status = ?, created_at = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                mission.unit_id,
                mission.attempt_id,
                mission.focus_dimension,
                mission.title,
                mission.instructions,
                checklist_json,
                mission.status,
                mission.created_at,
                mission.completed_at,
                mission.id,
            ),
        )

    conn.commit()
    conn.close()
    return mission


def _mission_from_row(row: sqlite3.Row) -> RevisionMission:
    return RevisionMission(
        id=int(row["id"]),
        unit_id=str(row["unit_id"]),
        attempt_id=int(row["attempt_id"]),
        focus_dimension=str(row["focus_dimension"]),
        title=str(row["title"]),
        instructions=str(row["instructions"]),
        checklist=[str(item) for item in _deserialize_json_list(row["checklist_json"])],
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        completed_at=str(row["completed_at"]) if row["completed_at"] is not None else None,
    )


def get_active_revision_mission(unit_id: str) -> RevisionMission | None:
    """Return the latest active revision mission for one unit."""

    conn = _connection()
    init_db(conn)
    row = conn.execute(
        """
        SELECT id, unit_id, attempt_id, focus_dimension, title, instructions,
               checklist_json, status, created_at, completed_at
        FROM revision_missions
        WHERE unit_id = ? AND status = 'active'
        ORDER BY id DESC
        LIMIT 1
        """,
        (unit_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return _mission_from_row(row)


def complete_revision_mission(mission_id: int) -> None:
    """Mark one revision mission as completed."""

    conn = _connection()
    init_db(conn)
    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE revision_missions SET status = 'completed', completed_at = ? WHERE id = ?",
        (now, mission_id),
    )
    conn.commit()
    conn.close()


def supersede_active_revision_missions(unit_id: str, new_attempt_id: int) -> int:
    """Mark existing active missions for a unit as superseded."""

    _ = new_attempt_id  # Explicitly keep API intention for audit/debug call sites.

    conn = _connection()
    init_db(conn)
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        """
        UPDATE revision_missions
        SET status = 'superseded', completed_at = ?
        WHERE unit_id = ? AND status = 'active'
        """,
        (now, unit_id),
    )
    conn.commit()
    conn.close()
    return int(cursor.rowcount or 0)


def get_all_attempts() -> List[Dict[str, object]]:
    """Fetch all attempts across all units."""

    conn = _connection()
    init_db(conn)
    rows = conn.execute(
        "SELECT id, unit_id, overall_score, created_at FROM attempts ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def export_portfolio(unit_ids: List[str]) -> Dict[str, object]:
    """Compile all unit attempts and core progress metadata into one export structure."""

    unit_set = set(unit_ids)
    progress = load_progress(unit_ids)

    conn = _connection()
    init_db(conn)
    if unit_ids:
        rows = conn.execute(
            "SELECT id, unit_id, draft, overall_score, feedback_json, created_at FROM attempts WHERE unit_id IN ({}) ORDER BY created_at ASC".format(
                ",".join("?" for _ in unit_ids)
            ),
            unit_ids,
        ).fetchall()
    else:
        rows = []
    conn.close()

    attempts_by_unit: Dict[str, List[Dict[str, object]]] = {unit_id: [] for unit_id in unit_set}
    for row in rows:
        unit_id = row["unit_id"]
        if unit_id in unit_set:
            attempts_by_unit.setdefault(unit_id, []).append(
                {
                    "id": row["id"],
                    "draft": row["draft"],
                    "overall_score": row["overall_score"],
                    "feedback": json.loads(row["feedback_json"]),
                    "created_at": row["created_at"],
                }
            )

    ordered_units = [
        {
            "unit_id": unit_id,
            "attempts": attempts_by_unit.get(unit_id, []),
        }
        for unit_id in unit_ids
    ]

    return {
        "exported_at": datetime.utcnow().isoformat(),
        "units": ordered_units,
        "current_unit_id": progress.current_unit_id,
        "unlocked_units": progress.unlocked_units,
        "best_score_by_unit": progress.best_score_by_unit,
        "attempts_count": sum(len(attempts) for attempts in attempts_by_unit.values()),
    }
