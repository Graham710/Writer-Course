# Writer Course -- Claude Code Context

## Project
Local-first Streamlit app for an interactive fiction writing course built around *How Fiction Works* by James Wood. PDF-only content scope. OpenAI gpt-5.2 for feedback; local heuristic fallback when API is unavailable.

## Stack
- Python 3, Streamlit, OpenAI Responses API, SQLite3, pypdf/pdfplumber, Plotly
- Package manager: `uv` (use `uv sync` to install)
- Dependencies in `requirements.txt`

## Architecture
- `app.py` -- Streamlit entry point (UI, tabs, session state)
- `src/config.py` -- env/path resolution (dotenv loaded here)
- `src/types.py` -- dataclass models: CourseUnit, FeedbackReport, ExerciseSpec, ProgressRecord, ChatTurn, LineNote
- `src/pdf_ingest.py` -- PDF extraction, sentence chunking, cache to `data/chunks.json`
- `src/unit_catalog.py` -- hard-coded unit map (12 units) with page ranges, cache to `data/units.json`
- `src/exercise_engine.py` -- exercise generation from directives, cache to `data/exercises.json`
- `src/feedback_engine.py` -- OpenAI evaluation pipeline + heuristic `_fallback_report`
- `src/coach_engine.py` -- unit-scoped Q&A with TF-IDF chunk ranking + off-topic refusal
- `src/storage.py` -- SQLite persistence (progress, attempts, drafts, chat_turns)

## Key Invariants
- All lesson/coach/exercise content MUST derive from PDF chunks only. No external sources.
- Coach must return `REFUSAL_TEXT` ("That is not covered in this course material.") for off-topic questions.
- Every feedback strength, risk, line note, and revision item must include a page citation `(p.NUM)`.
- Rubric has exactly 4 dimensions: concept_application, narrative_effectiveness, language_precision, revision_readiness.
- Overall score = weighted average: concept 35%, narrative 30%, language 20%, revision 15%.
- Unit unlock happens on any submission (not score-gated).
- Scores are clamped 0-100.

## Commands
```bash
uv sync                    # Install dependencies
streamlit run app.py       # Start dev server
pytest tests/              # Run tests (9 test files, no API keys needed)
ruff format . && ruff check --fix .  # Format and lint
```

## Testing
- `pytest tests/` -- uses `tmp_path` and `monkeypatch` for DB isolation
- Tests cover: coach guardrails, exercise dedup, fallback scoring, feedback schema normalization, PDF cache compat, storage roundtrip, unit loading, unit unlocking

## Environment
- `.env` contains `OPENAI_API_KEY` -- NEVER read, edit, or commit this file
- `.env.example` is the safe template
- `WRITER_COURSE_DB_PATH` defaults to `writer_course_state.db`
- `WRITER_COURSE_UNLOCK_THRESHOLD` defaults to 85

## MCP Servers Available
- **Context7** -- use for Streamlit, OpenAI Responses API, Plotly, pypdf docs lookup
