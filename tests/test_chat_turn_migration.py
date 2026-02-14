from src import storage


def test_chat_turn_migration_preserves_old_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITER_COURSE_DB_PATH", str(tmp_path / "writer_course_state.db"))

    conn = storage._connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chat_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT NOT NULL,
            citations TEXT
        );
        INSERT INTO chat_turns (unit_id, question, answer, created_at, citations)
        VALUES ('1', 'Old?', 'Old answer', '2026-02-14T00:00:00', '[]');
        """
    )
    conn.commit()

    storage.init_db(conn)
    conn.close()

    turns = storage.get_chat_turns("1", limit=5)
    assert turns
    assert turns[0]["answer"] == "Old answer"
    assert turns[0].get("evidence") == []

    storage.save_chat_turn(
        "1",
        "New?",
        "New answer",
        citations=["p.16"],
        evidence=[{"quote": "Narrating controls perspective.", "citation": "p.16"}],
        confidence=0.82,
    )

    latest = storage.get_chat_turns("1", limit=1)[0]
    assert latest["answer"] == "New answer"
    assert latest["citations"] == ["p.16"]
    assert latest["evidence"][0]["citation"] == "p.16"
    assert float(latest["confidence"]) == 0.82
