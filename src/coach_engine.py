"""Coach interaction constrained to one unit's PDF chunks."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List, Tuple

from .config import get_openai_api_key, get_openai_model, has_openai_api_key

REFUSAL_TEXT = "That is not covered in this course material."

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "can",
    "did",
    "do",
    "for",
    "from",
    "has",
    "have",
    "had",
    "he",
    "her",
    "hers",
    "his",
    "i",
    "in",
    "is",
    "it",
    "its",
    "if",
    "me",
    "my",
    "no",
    "not",
    "of",
    "on",
    "or",
    "our",
    "she",
    "so",
    "the",
    "to",
    "that",
    "this",
    "was",
    "we",
    "with",
    "you",
    "your",
    "all",
    "any",
    "been",
    "been",
    "does",
    "doing",
    "into",
    "just",
    "more",
    "only",
    "should",
    "very",
    "when",
    "what",
    "which",
    "while",
    "who",
    "will",
    "would",
    "yourself",
    "their",
}

_OFF_TOPIC_KEYWORDS = {
    "programming",
    "recipe",
    "sports",
    "football",
    "basketball",
    "algorithm",
    "engineering",
    "cooking",
    "stock",
    "market",
    "tax",
    "politics",
}

_RELEVANCE_MIN_OVERLAP = 1
_RELEVANCE_RATIO = 0.15


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alpha tokens with stop-word filtering."""

    tokens = re.findall(r"[a-z]{2,}", text.lower())
    return [token for token in tokens if token not in _STOP_WORDS]


def _relevance_metrics(question_tokens: List[str], chunk_tokens: List[str]) -> Tuple[float, int]:
    """Compute overlap ratio and overlap count between two token sequences."""

    if not question_tokens:
        return 0.0, 0

    qset = set(question_tokens)
    cset = set(chunk_tokens)
    overlap = qset.intersection(cset)
    return (len(overlap) / len(qset), len(overlap))


def _chunk_text_tokens(chunk: Dict[str, object]) -> List[str]:
    """Extract normalized tokens for one chunk."""

    return _tokenize(str(chunk.get("text", "")))


def _rank_chunks(question: str, chunks: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Rank chunks by lightweight TF-IDF score and discard weak overlaps."""

    if not chunks:
        return []

    question_tokens = _tokenize(question)
    if not question_tokens:
        return []

    question_set = set(question_tokens)
    tokenized_chunks = [_chunk_text_tokens(chunk) for chunk in chunks]
    try:
        total_chunks = len(chunks)
        if total_chunks == 0:
            return []

        doc_freq = Counter()
        for tokens in tokenized_chunks:
            doc_freq.update(set(tokens))

        ranked: List[Tuple[float, Dict[str, object]]] = []
        for chunk, chunk_tokens in zip(chunks, tokenized_chunks):
            overlap_ratio, overlap_count = _relevance_metrics(
                question_tokens=question_tokens, chunk_tokens=chunk_tokens
            )
            if overlap_count < _RELEVANCE_MIN_OVERLAP or overlap_ratio < _RELEVANCE_RATIO:
                continue

            chunk_counter = Counter(chunk_tokens)
            chunk_len = len(chunk_tokens) or 1
            score = 0.0
            for token in question_set:
                if token not in chunk_counter:
                    continue
                tf = chunk_counter[token] / chunk_len
                idf = math.log((1 + total_chunks) / (1 + doc_freq.get(token, 0))) + 1.0
                score += tf * idf

            if score <= 0:
                continue

            ranked.append((score, chunk))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in ranked]
    except Exception:
        # Fallback to simple overlap scoring if TF-IDF path fails.
        fallback: List[Tuple[float, Dict[str, object]]] = []
        question_set = set(question_tokens)
        for chunk, chunk_tokens in zip(chunks, tokenized_chunks):
            overlap_ratio, overlap_count = _relevance_metrics(
                question_tokens=question_tokens, chunk_tokens=chunk_tokens
            )
            if overlap_count >= _RELEVANCE_MIN_OVERLAP and overlap_ratio >= _RELEVANCE_RATIO:
                fallback.append((overlap_ratio, chunk))

        fallback.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in fallback]


def _build_context(chunks: List[Dict[str, object]], max_chunks: int = 6) -> str:
    """Build the prompt context from the highest-ranked chunks."""

    snippets = []
    for chunk in chunks[:max_chunks]:
        page = chunk.get("page", "")
        text = str(chunk.get("text", "")).strip()
        snippets.append(f"[p.{page}] {text[:900]}")
    return "\n\n".join(snippets)


def answer_question(unit_id: str, question: str, chunks: List[Dict[str, object]]) -> str:
    """Answer a unit-scoped question or return a refusal when off-scope."""

    if not question.strip():
        return REFUSAL_TEXT

    relevant_chunks = _rank_chunks(question, chunks)
    if not relevant_chunks:
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
    """Determine if a question should be treated as outside course scope."""

    tokens = _tokenize(question)
    if not tokens:
        return True

    question_set = set(tokens)
    if question_set.intersection(_OFF_TOPIC_KEYWORDS):
        return True

    chunk_text = str(best_chunk.get("text", ""))
    chunk_tokens = _chunk_text_tokens({"text": chunk_text})
    overlap_ratio, overlap_count = _relevance_metrics(question_tokens=tokens, chunk_tokens=chunk_tokens)

    if overlap_count < _RELEVANCE_MIN_OVERLAP:
        return True

    return overlap_ratio < _RELEVANCE_RATIO
