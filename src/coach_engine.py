"""Coach interaction constrained to one unit's PDF chunks."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Dict, List, Tuple

from .config import get_openai_api_key, get_openai_model, has_openai_api_key
from .types import CoachAnswer, CoachEvidence

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
_CITATION_RE = re.compile(r"^p\.(\d+)$")


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


def _refusal_answer() -> CoachAnswer:
    return CoachAnswer(
        answer=REFUSAL_TEXT,
        citations=[],
        evidence=[],
        confidence=1.0,
        is_refusal=True,
    )


def _fallback_structured_answer(relevant_chunks: List[Dict[str, object]]) -> CoachAnswer:
    chosen = relevant_chunks[0]
    snippet = str(chosen.get("text", "")).strip()
    first_sentence = snippet.split(".")[0][:250]
    page = int(chosen.get("page", 0) or 0)
    citation = f"p.{page}"

    evidence_quote = snippet[:220] if snippet else "No direct quote available in this chunk."
    return CoachAnswer(
        answer=f"From this unit: {first_sentence}. ({citation})",
        citations=[citation],
        evidence=[CoachEvidence(quote=evidence_quote, citation=citation)],
        confidence=0.74,
        is_refusal=False,
    )


def _parse_json_object(raw: str) -> Dict[str, object]:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or start >= end:
        raise ValueError("No JSON object found")
    return json.loads(raw[start : end + 1])


def _valid_citation(citation: str, valid_pages: set[int]) -> bool:
    match = _CITATION_RE.match((citation or "").strip())
    if not match:
        return False
    try:
        return int(match.group(1)) in valid_pages
    except ValueError:
        return False


def _normalize_answer_payload(payload: Dict[str, object], relevant_chunks: List[Dict[str, object]]) -> CoachAnswer | None:
    valid_pages = {int(chunk.get("page", 0) or 0) for chunk in relevant_chunks}

    answer = str(payload.get("answer", "")).strip()
    if not answer:
        return None

    citations_raw = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    citations = [str(item).strip() for item in citations_raw if str(item).strip()]
    citations = [item for item in citations if _valid_citation(item, valid_pages)]

    evidence_raw = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
    evidence: List[CoachEvidence] = []
    for item in evidence_raw:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", "")).strip()
        citation = str(item.get("citation", "")).strip()
        if not quote or not _valid_citation(citation, valid_pages):
            continue
        evidence.append(CoachEvidence(quote=quote[:320], citation=citation))

    if not citations or not evidence:
        return None

    try:
        confidence = float(payload.get("confidence", 0.0) or 0.0)
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    # Keep answer citation-visible for UI trust.
    if not re.search(r"\(p\.\d+\)", answer):
        answer = f"{answer} ({citations[0]})"

    return CoachAnswer(
        answer=answer,
        citations=citations,
        evidence=evidence,
        confidence=confidence,
        is_refusal=False,
    )


def _openai_answer(question: str, relevant_chunks: List[Dict[str, object]]) -> CoachAnswer | None:
    if not has_openai_api_key():
        return None

    prompt = f"""You are the course coach for one unit only.

Question: {question}

Use only this context:
{_build_context(relevant_chunks)}

Return JSON only:
{{
  "answer": "...",
  "citations": ["p.NUM"],
  "evidence": [{{"quote":"short quote from context", "citation":"p.NUM"}}],
  "confidence": 0.0
}}

Rules:
- If context is insufficient, return:
  {{"answer":"{REFUSAL_TEXT}","citations":[],"evidence":[],"confidence":1.0}}
- Include at least one citation and one evidence quote for in-scope answers.
- Evidence citations must match the provided context pages.
"""

    try:
        from openai import OpenAI

        client = OpenAI(api_key=get_openai_api_key(), timeout=20)
        response = client.responses.create(
            model=get_openai_model(),
            input=[{"role": "user", "content": prompt}],
            temperature=0.15,
            max_output_tokens=800,
        )
        payload = _parse_json_object(str(getattr(response, "output_text", "")))

        if str(payload.get("answer", "")).strip() == REFUSAL_TEXT:
            return _refusal_answer()

        return _normalize_answer_payload(payload, relevant_chunks)
    except Exception:
        return None


def ask_question(unit_id: str, question: str, chunks: List[Dict[str, object]]) -> CoachAnswer:
    """Return structured coach output with evidence and confidence."""

    if not question.strip():
        return _refusal_answer()

    relevant_chunks = _rank_chunks(question, chunks)
    if not relevant_chunks:
        return _refusal_answer()

    if _is_off_scope(question, relevant_chunks[0]):
        return _refusal_answer()

    if not has_openai_api_key():
        return _fallback_structured_answer(relevant_chunks)

    generated = _openai_answer(question, relevant_chunks)
    if generated is not None:
        return generated

    return _fallback_structured_answer(relevant_chunks)


def answer_question(unit_id: str, question: str, chunks: List[Dict[str, object]]) -> str:
    """Compatibility wrapper: return string-only answer for existing callsites."""

    return ask_question(unit_id, question, chunks).answer
