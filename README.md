# Interactive Fiction Writing Course App

This is a local-first Streamlit app built around the book *How Fiction Works*.

## What you get

- One-unit-at-a-time guided flow.
- Practice prompts in each unit.
- GPT-5.2 feedback with rubric scores and line-level notes.
- Unit unlock flow advances by submitted attempt rather than score threshold.
- Local SQLite progress persistence for drafts, feedback, and coach chat.
- PDF-only lesson, exercise, and coach scope.

## Setup

1. Install dependencies with `uv`:

```bash
uv sync
```

2. Copy `.env.example` to `.env` and add your OpenAI key.

3. Start the app:

```bash
streamlit run app.py
```

## Files

- `app.py` — main Streamlit UI.
- `src/config.py` — app and env configuration.
- `src/pdf_ingest.py` — PDF extraction + chunking by unit pages.
- `src/unit_catalog.py` — unit map from the provided plan.
- `src/exercise_engine.py` — exercise generation.
- `src/feedback_engine.py` — feedback pipeline with schema normalization.
- `src/coach_engine.py` — unit-scoped coach answers.
- `src/storage.py` — local SQLite persistence.
- `src/types.py` — structured app models.
- `data/units.json` and `data/chunks.json` — cached content and metadata.
- `data/exercises.json` — cached generated exercises.

## Data policy

- No external books or web sources are queried for lesson/coach content.
- If no matching unit content is available, the coach returns:

> That is not covered in this course material.

## Notes

The first AI action requires `OPENAI_API_KEY` for live model scoring. Without it, the app still runs and uses local fallback feedback and coach responses sourced from course context.
