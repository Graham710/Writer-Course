"""Streamlit app for the PDF-only interactive writing course."""

from __future__ import annotations

import difflib
import json
from typing import Dict, List

import plotly.graph_objects as go
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
    """Load course units, chunks, and exercises with Streamlit cache."""

    units = load_units()
    all_chunks = load_or_build_chunks(units)
    unit_chunks = {unit.id: chunks_by_unit(unit, all_chunks) for unit in units}
    exercise_map = load_or_build_exercises(units, unit_chunks)
    return units, all_chunks, exercise_map


def _render_home_progress(unit_ids: List[str], best_scores: Dict[str, int]) -> None:
    """Render the Home section progress summary and chart."""

    if not unit_ids:
        st.info("No units loaded yet.")
        return

    data = {f"Unit {unit_id}": [best_scores.get(unit_id, 0)] for unit_id in unit_ids}
    st.bar_chart(data)


def _render_lesson(unit: CourseUnit, chunks: List[dict]) -> None:
    """Render the lesson tab for a selected unit."""

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
    """Render one exercise card for a unit and exercise kind."""

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


def _build_rubric_radar(rubric_scores: Dict[str, int]) -> go.Figure:
    """Create a radar chart figure for the rubric scores."""

    labels = [
        "Concept Application",
        "Narrative Effectiveness",
        "Language Precision",
        "Revision Readiness",
    ]
    values = [rubric_scores.get("concept_application", 0), rubric_scores.get("narrative_effectiveness", 0), rubric_scores.get("language_precision", 0), rubric_scores.get("revision_readiness", 0)]
    values += [values[0]]
    labels += [labels[0]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(r=values, theta=labels, fill="toself", name="Rubric")
    )
    fig.update_layout(
        polar={"radialaxis": {"visible": True, "range": [0, 100]}},
        showlegend=False,
        title="Rubric",
        margin=dict(l=20, r=20, t=30, b=10),
    )
    return fig


def _render_attempt_trend(attempts: List[Dict[str, object]]) -> None:
    """Render a line chart for this unit's score progression."""

    if not attempts:
        return

    attempts_chron = list(reversed(attempts))
    x = list(range(1, len(attempts_chron) + 1))
    scores = [int(attempt["overall_score"]) for attempt in attempts_chron]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=scores, mode="lines+markers", name="Score"))
    fig.update_layout(
        title="Score Trend",
        xaxis_title="Attempt",
        yaxis_title="Score",
        yaxis_range=[0, 100],
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def _build_portfolio_markdown(portfolio: Dict[str, object]) -> str:
    """Render portfolio export payload as readable Markdown."""

    lines: List[str] = ["# Writer Course Portfolio", "", f"Exported: {portfolio.get('exported_at', '')}", ""]
    for unit_record in portfolio.get("units", []):
        unit_id = str(unit_record.get("unit_id", ""))
        title = unit_record.get("title")
        lines.append(f"## Unit {unit_id}: {title}" if title else f"## Unit {unit_id}")

        attempts = unit_record.get("attempts", [])
        if not attempts:
            lines.append("- No attempts recorded.")
            lines.append("")
            continue

        for attempt in attempts:
            created_at = attempt.get("created_at", "")
            score = attempt.get("overall_score", 0)
            draft = attempt.get("draft", "")
            lines.append(f"### {created_at} — Score {score}")
            lines.append("")
            lines.append("```text")
            lines.append(str(draft))
            lines.append("```")
            lines.append("")

    if not portfolio.get("units"):
        lines.append("No attempts yet.")

    return "\n".join(lines)


def _show_feedback_unit(unit_id: str, attempts: List[dict]) -> None:
    """Render feedback summary for the latest attempt on a unit."""

    if not attempts:
        st.info("No feedback yet. Submit a draft to generate the next feedback pass.")
        return

    latest = attempts[0]
    report = FeedbackReport.from_dict(json.loads(latest["feedback_json"]))
    st.metric("Overall Score", f"{report.overall_score} / 100")
    st.progress(min(report.overall_score, 100) / 100)

    st.plotly_chart(_build_rubric_radar(report.rubric_scores), use_container_width=True)

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


def _render_journal(attempts: List[Dict[str, object]], unit_ids: List[str]) -> None:
    """Render Journal / History tab with attempt history, diffs, and exports."""

    st.subheader("Journal / History")

    if not attempts:
        st.info("No prior attempts yet.")
        return

    st.markdown("### Score trend")
    _render_attempt_trend(attempts)

    attempts_chron = list(reversed(attempts))
    def format_attempt_label(index: int, attempt: Dict[str, object]) -> str:
        return f"#{index + 1} · {attempt['created_at']} · score {attempt['overall_score']}"

    st.markdown("### Compare drafts")
    options = range(len(attempts_chron))
    attempt_labels = {idx: format_attempt_label(idx, attempt) for idx, attempt in enumerate(attempts_chron)}

    left_col, right_col = st.columns(2)
    with left_col:
        earlier_idx = st.selectbox(
            "Earlier attempt",
            options=options,
            format_func=lambda idx: attempt_labels[idx],
        )
    with right_col:
        later_idx = st.selectbox(
            "Later attempt",
            options=options,
            index=max(0, len(options) - 1),
            format_func=lambda idx: attempt_labels[idx],
        )

    earlier_idx = min(earlier_idx, later_idx)
    later_idx = max(earlier_idx, later_idx)

    if earlier_idx == later_idx:
        st.warning("Choose two different attempts to compare.")
        return

    earlier_attempt = attempts_chron[earlier_idx]
    later_attempt = attempts_chron[later_idx]

    earlier_score = int(earlier_attempt["overall_score"])
    later_score = int(later_attempt["overall_score"])
    st.metric("Score delta", f"{later_score}", delta=later_score - earlier_score)

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown(f"**{format_attempt_label(earlier_idx, earlier_attempt)}**")
        st.text(earlier_attempt["draft"])
    with col_right:
        st.markdown(f"**{format_attempt_label(later_idx, later_attempt)}**")
        st.text(later_attempt["draft"])

    diff = "\n".join(
        difflib.unified_diff(
            str(earlier_attempt["draft"]).splitlines(),
            str(later_attempt["draft"]).splitlines(),
            fromfile=format_attempt_label(earlier_idx, earlier_attempt),
            tofile=format_attempt_label(later_idx, later_attempt),
            lineterm="",
        )
    )
    st.markdown("### Unified diff")
    st.code(diff, language="diff")

    for attempt in attempts:
        report = json.loads(attempt["feedback_json"])
        with st.expander(f"{attempt['created_at']} — score {attempt['overall_score']}"):
            st.markdown("**Draft:**")
            st.text(attempt["draft"][:500])
            st.markdown("**Feedback JSON:**")
            st.json(report)

    st.markdown("### Export portfolio")
    portfolio = storage.export_portfolio(unit_ids)
    portfolio_json = json.dumps(portfolio, indent=2)
    portfolio_markdown = _build_portfolio_markdown(portfolio)

    json_col, markdown_col = st.columns(2)
    with json_col:
        st.download_button(
            "Download portfolio JSON",
            data=portfolio_json,
            file_name="writer_course_portfolio.json",
            mime="application/json",
        )
    with markdown_col:
        st.download_button(
            "Download portfolio Markdown",
            data=portfolio_markdown,
            file_name="writer_course_portfolio.md",
            mime="text/markdown",
        )


def main() -> None:
    """Render the main course interface."""

    st.title("Interactive Fiction Writing Course")
    units, all_chunks, exercise_map = _load_assets()
    unit_ids = [unit.id for unit in units]
    unit_lookup = {unit.id: unit for unit in units}

    progress = storage.load_progress(unit_ids)
    progress.last_opened_at = st.session_state.get("last_opened_at", progress.last_opened_at)

    if not has_openai_api_key():
        st.info(
            "OpenAI API key missing. Submitting drafts or asking coach questions will use local fallback feedback and course-context citations."
        )

    st.subheader("Home")
    st.progress(len(progress.unlocked_units) / max(1, len(units)))
    st.write(
        f"Unlocked units: {len(progress.unlocked_units)}/{len(units)} — "
        f"Current unit: {progress.current_unit_id}"
    )
    _render_home_progress(unit_ids, progress.best_score_by_unit)

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
    chunks = [chunk for chunk in all_chunks if chunk.get("unit_id") == selected_unit_id]
    unit_exercises = exercise_map.get(selected_unit_id, [])

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
        draft_input_key = f"draft_input_{selected_unit_id}"

        if draft_key not in st.session_state:
            st.session_state[draft_key] = storage.get_draft(selected_unit_id)

        with st.form(key=f"feedback_form_{selected_unit_id}"):
            draft = st.text_area(
                "Submit your draft for this unit",
                value=st.session_state[draft_key],
                height=260,
                key=draft_input_key,
            )
            st.caption(f"Word count: {len((draft or "").split())}")

            col_submit, col_resubmit = st.columns([1, 1])
            with col_submit:
                submit_clicked = st.form_submit_button(
                    "Submit Draft",
                    use_container_width=True,
                )
            with col_resubmit:
                resubmit_clicked = st.form_submit_button(
                    "Rework and Resubmit",
                    use_container_width=True,
                )

        if submit_clicked or resubmit_clicked:
            st.session_state[draft_key] = draft
            if not draft.strip():
                st.error("Please enter a draft before submitting.")
            else:
                storage.save_draft(selected_unit_id, draft)
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

    with tabs[3]:
        st.subheader("Coach")
        question_key = f"question_{selected_unit_id}"
        question = st.text_area("Ask a question about the current unit", key=question_key)
        if st.button("Ask coach"):
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
        attempts = storage.get_attempts_for_unit(selected_unit_id)
        _render_journal(attempts, unit_ids)

    storage.persist_progress(progress)


if __name__ == "__main__":
    main()
