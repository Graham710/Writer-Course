"""Streamlit app for the PDF-only interactive writing course."""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Dict, List

import streamlit as st

from src import coach_engine, feedback_engine, storage
from src.config import has_openai_api_key
from src.exercise_engine import load_or_build_exercises
from src.pdf_ingest import chunks_by_unit, load_or_build_chunks
from src.types import CourseUnit, FeedbackReport
from src.unit_catalog import load_units


st.set_page_config(page_title="Writer Course", page_icon="✍️", layout="wide")


@st.cache_resource
def _load_assets() -> tuple[List[CourseUnit], list[dict], Dict[str, List[dict]]]:
    units = load_units()
    all_chunks = load_or_build_chunks(units)
    unit_chunks = {unit.id: chunks_by_unit(unit, all_chunks) for unit in units}
    exercise_map = load_or_build_exercises(units, unit_chunks)
    return units, all_chunks, exercise_map


def _render_lesson(unit: CourseUnit, chunks: List[dict]) -> None:
    st.subheader(f"Learn: {unit.title}")
    st.markdown("**Course scope:** Use only unit pages and cited passages.")

    key_concepts = unit.learning_objectives or ["No learning objectives loaded."]
    st.markdown("### Key Concepts")
    for concept in key_concepts:
        st.markdown(f"- {concept}")

    if not chunks:
        st.warning("No lesson passages were extracted for this unit yet.")
        return

    st.markdown("### Cited Passage Examples")
    for chunk in chunks[:3]:
        page = chunk.get("page", "?")
        text = str(chunk.get("text", ""))[:800]
        with st.expander(f"Page {page} citation"):
            st.markdown(f"{text} (p.{page})")

    st.markdown("### Unit Summary")
    combined = " ".join(str(chunk.get("text", "")) for chunk in chunks[:3]).strip()
    st.write(combined[:1200] + ("..." if len(combined) > 1200 else ""))


def _exercise_card(unit_id: str, exercises_by_kind: List, kind: str) -> None:
    spec = next((x for x in exercises_by_kind if x.kind == kind), None)
    if not spec:
        st.info("No exercise available for this slot yet.")
        return
    st.markdown(f"### {kind.title()} Exercise")
    st.markdown(spec.prompt)
    st.markdown("- Source mode: " + spec.source_mode)
    st.markdown(f"- Timebox: {spec.timebox_minutes} minutes")
    st.markdown("**Success criteria:**")
    for item in spec.success_criteria:
        st.markdown(f"- {item}")


def _show_feedback_unit(unit_id: str, attempts: List[dict]) -> None:
    if not attempts:
        st.info("No feedback yet. Submit a draft to unlock the next unit when your score is 85/100 or higher.")
        return

    latest = attempts[0]
    report = FeedbackReport.from_dict(json.loads(latest["feedback_json"]))
    st.metric("Overall Score", f"{report.overall_score} / 100")
    st.progress(min(report.overall_score, 100) / 100)

    st.markdown("### Rubric")
    for key, score in report.rubric_scores.items():
        label = key.replace("_", " ").title()
        st.progress(min(score, 100) / 100)
        st.markdown(f"- {label}: {score}")

    st.markdown("### Strengths")
    for item in report.strengths:
        st.markdown(f"- {item}")

    st.markdown("### Craft Risks")
    for item in report.craft_risks:
        st.markdown(f"- {item}")

    st.markdown("### Line Notes")
    for note in report.line_notes:
        st.markdown(
            f"- Line {note.line_number}: {note.text_excerpt[:120]} — {note.comment} ({note.citation or 'p.0'})"
        )

    st.markdown("### Revision Plan")
    for item in report.revision_plan:
        st.markdown(f"- {item}")

    st.caption(f"Unlock eligible: {report.unlock_eligible}")
    st.caption(f"Saved at: {latest['created_at']}")


def main() -> None:
    st.title("Interactive Fiction Writing Course")
    units, _all_chunks, exercise_map = _load_assets()
    unit_ids = [unit.id for unit in units]
    unit_lookup = {unit.id: unit for unit in units}

    progress = storage.load_progress(unit_ids)
    progress.last_opened_at = st.session_state.get("last_opened_at", progress.last_opened_at)

    if not has_openai_api_key():
        st.warning(
            "OpenAI API key missing. Add OPENAI_API_KEY to your environment and restart. "
            "AI feedback and coach actions are disabled until provided."
        )

    st.subheader("Home")
    st.progress(len(progress.unlocked_units) / max(1, len(units)))
    st.write(
        f"Unlocked units: {len(progress.unlocked_units)}/{len(units)} — "
        f"Current unit: {progress.current_unit_id}"
    )

    if progress.current_unit_id not in unit_ids:
        progress.current_unit_id = unit_ids[0]

    unlocked_choices = [unit for unit in units if unit.id in progress.unlocked_units]
    selected_unit_id = st.selectbox(
        "Resume current unit",
        options=[unit.id for unit in unlocked_choices],
        index=[unit.id for unit in unlocked_choices].index(progress.current_unit_id),
        format_func=lambda value: f"Unit {value}: {unit_lookup[value].title}",
    )
    if selected_unit_id != progress.current_unit_id:
        progress = storage.set_current_unit(progress, selected_unit_id)

    selected_unit = unit_lookup[selected_unit_id]
    chunks = [chunk for chunk in _all_chunks if chunk.get("unit_id") == selected_unit_id]
    unit_exercises = exercise_map.get(selected_unit_id, [])

    with st.expander("Score History"):
        for unit_id in unit_ids:
            best = progress.best_score_by_unit.get(unit_id, 0)
            unlocked = "✅" if unit_id in progress.unlocked_units else "🔒"
            st.markdown(f"- Unit {unit_id}: {unlocked} best score {best}")

    tabs = st.tabs(["Learn", "Practice", "Feedback", "Coach", "Journal / History"])

    with tabs[0]:
        _render_lesson(selected_unit, chunks)

    with tabs[1]:
        st.subheader("Practice")
        _exercise_card(selected_unit_id, unit_exercises, "core")
        st.divider()
        _exercise_card(selected_unit_id, unit_exercises, "stretch")

    with tabs[2]:
        st.subheader("Feedback")
        draft_key = f"draft_{selected_unit_id}"
        if draft_key not in st.session_state:
            st.session_state[draft_key] = storage.get_draft(selected_unit_id)

        draft = st.text_area(
            "Submit your draft for this unit",
            value=st.session_state[draft_key],
            height=260,
            key=draft_key,
        )
        storage.save_draft(selected_unit_id, draft)

        col_submit, col_resubmit = st.columns([1, 1])
        with col_submit:
            submit_clicked = st.button(
                "Submit Draft",
                use_container_width=True,
                disabled=not has_openai_api_key(),
            )
        with col_resubmit:
            resubmit_clicked = st.button(
                "Rework and Resubmit",
                use_container_width=True,
                disabled=not has_openai_api_key(),
            )

        if submit_clicked or resubmit_clicked:
            if not draft.strip():
                st.error("Please enter a draft before submitting.")
            else:
                with st.spinner("Running deep course review..."):
                    report = feedback_engine.evaluate_draft(selected_unit, draft, chunks)
                progress = storage.add_feedback_attempt(
                    progress,
                    selected_unit_id,
                    draft,
                    report,
                    unit_ids,
                )
                st.success("Feedback complete and saved.")

        attempts = storage.get_attempts_for_unit(selected_unit_id)
        _show_feedback_unit(selected_unit_id, attempts)

        latest = storage.get_latest_feedback_for_unit(selected_unit_id)
        if latest and latest.unlock_eligible:
            next_unit_id = storage._next_unit_id(selected_unit_id, unit_ids)
            if next_unit_id and next_unit_id not in progress.unlocked_units:
                if st.button(f"Unlock Next Unit", use_container_width=True):
                    progress.unlocked_units.append(next_unit_id)
                    progress.unlocked_units = sorted(
                        progress.unlocked_units,
                        key=lambda value: unit_ids.index(value),
                    )
                    storage.persist_progress(progress)
                    st.success(f"Unit {next_unit_id} unlocked.")

    with tabs[3]:
        st.subheader("Coach")
        question = st.text_area("Ask a question about the current unit", key=f"question_{selected_unit_id}")
        if st.button("Ask coach", disabled=not has_openai_api_key()):
            if not question.strip():
                st.error("Ask a question first.")
            else:
                answer = coach_engine.answer_question(selected_unit_id, question, chunks)
                storage.save_chat_turn(selected_unit_id, question, answer)
                st.info(answer)

        st.markdown("### Recent coach turns")
        for turn in storage.get_chat_turns(selected_unit_id, limit=3):
            st.markdown(f"**Q:** {turn['question']}")
            st.markdown(f"**A:** {turn['answer']}")
            st.markdown(f"_at {turn['created_at']}_")

    with tabs[4]:
        st.subheader("Journal / History")
        attempts = storage.get_attempts_for_unit(selected_unit_id)
        if not attempts:
            st.info("No prior attempts yet.")
            return

        for attempt in attempts:
            report = json.loads(attempt["feedback_json"])
            with st.expander(f"{attempt['created_at']} — score {attempt['overall_score']}"):
                st.markdown("**Draft:**")
                st.text(attempt["draft"][:500])
                st.markdown("**Feedback JSON:**")
                st.json(report)

    storage.persist_progress(progress)


if __name__ == "__main__":
    main()
