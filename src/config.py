"""Configuration helpers for local app wiring."""

from __future__ import annotations

from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_pdf_path() -> Path:
    override = os.getenv("WRITER_COURSE_PDF_PATH")
    if override and Path(override).exists():
        return Path(override)

    candidates = sorted(_project_root().glob("*.pdf"))
    for candidate in candidates:
        if "how fiction works" in candidate.name.lower():
            return candidate
    if candidates:
        return candidates[0]
    raise FileNotFoundError("Could not find a PDF in the project root.")


def data_dir() -> Path:
    return _project_root() / "data"


def units_path() -> Path:
    return data_dir() / "units.json"


def chunks_path() -> Path:
    return data_dir() / "chunks.json"


def exercises_path() -> Path:
    return data_dir() / "exercises.json"


def db_path() -> Path:
    return Path(os.getenv("WRITER_COURSE_DB_PATH", str(_project_root() / "writer_course_state.db")))


def has_openai_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def get_openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5.2")


def openai_timeout() -> int:
    return int(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))


def unlock_threshold() -> int:
    try:
        return int(os.getenv("WRITER_COURSE_UNLOCK_THRESHOLD", "85"))
    except ValueError:
        return 85


def chunk_chars() -> int:
    try:
        return int(os.getenv("WRITER_COURSE_CHUNK_CHARS", "1200"))
    except ValueError:
        return 1200
