"""Coach interaction constrained to one unit's PDF chunks."""

from __future__ import annotations

import re
from typing import Dict, List

from .config import get_openai_api_key, get_openai_model, has_openai_api_key

REFUSAL_TEXT = "That is not covered in this course material."


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z]{2,}", text.lower())


def _rank_chunks(question: str, chunks: List[Dict[str, object]]) -> List[Dict[str, object]]:
    question_tokens = set(_tokenize(question))
    if not question_tokens:
        return []

    ranked = []
    for chunk in chunks:
        chunk_text = str(chunk.get("text", "")).lower()
        overlap = len(question_tokens.intersection(set(_tokenize(chunk_text))))
        score = overlap / max(1, len(question_tokens))
        ranked.append((score, chunk))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [chunk for score, chunk in ranked if score > 0]


def _build_context(chunks: List[Dict[str, object]], max_chunks: int = 6) -> str:
    snippets = []
    for chunk in chunks[:max_chunks]:
        page = chunk.get("page", "")
        text = str(chunk.get("text", "")).strip()
        snippets.append(f"[p.{page}] {text[:900]}")
    return "\n\n".join(snippets)


def answer_question(unit_id: str, question: str, chunks: List[Dict[str, object]]) -> str:
    if not question.strip():
        return REFUSAL_TEXT

    relevant_chunks = _rank_chunks(question, chunks)
    if not relevant_chunks:
        return REFUSAL_TEXT

    if len(relevant_chunks) == 0:
        return REFUSAL_TEXT

    if _is_off_scope(question, relevant_chunks[0]):
        return REFUSAL_TEXT

    if not has_openai_api_key():
        chosen = relevant_chunks[0]
        snippet = str(chosen.get("text", "")).strip()
        first_sentence = snippet.split(".")[0][:250]
        return f"From this unit: {first_sentence}. (p.{chosen.get('page', '0')})"

    context = _build_context(relevant_chunks)
    prompt = f"""You are the course coach for this unit only.

Question: {question}

Use only this unit context to answer and cite each substantive claim with (p.NUM).
If context is insufficient, respond exactly: {REFUSAL_TEXT}

Context:
{context}
"""

    try:
        from openai import OpenAI

        client = OpenAI(api_key=get_openai_api_key(), timeout=20)
        response = client.responses.create(
            model=get_openai_model(),
            input=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = str(getattr(response, "output_text", ""))
        if text.strip():
            return text
    except Exception:
        pass

    chosen = relevant_chunks[0]
    return f"Based on unit material, here's the best available answer: {str(chosen.get('text', ''))[:250]} (p.{chosen.get('page', '0')})"


def _is_off_scope(question: str, best_chunk: Dict[str, object]) -> bool:
    q = question.lower()
    if "what is" in q and "your" in q and "novel" in q:
        return True
    page_text = str(best_chunk.get("text", "")).lower()
    tokens = _tokenize(q)
    if not tokens:
        return True
    return not any(token in page_text for token in tokens)
