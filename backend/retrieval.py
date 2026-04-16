"""
Query pipeline:
  user utterance → intent classify → embed → Qdrant filtered search → LLM synthesis → answer
"""

import json

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from config import (
    OPENAI_API_KEY,
    QDRANT_HOST,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    EMBED_MODEL,
    LLM_MODEL,
    CLAUSE_TYPES,
)

openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant_client = QdrantClient(host=QDRANT_HOST, api_key=QDRANT_API_KEY, https=True, port=443)

# ---------------------------------------------------------------------------
# Intent classification — instant keyword matching (no API call = no latency)
# ---------------------------------------------------------------------------

_INTENT_KEYWORDS = {
    "data_rights": ["data", "share", "sell", "location", "privacy", "personal", "information",
                    "track", "monitor", "collect", "store", "third party", "advertis", "gps",
                    "डेटा", "जानकारी", "ಡೇಟಾ", "தரவு"],
    "cancellation": ["cancel", "subscription", "renew", "auto", "refund", "stop", "end",
                     "रद्द", "ರದ್ದು"],
    "payment": ["pay", "miss", "late", "fee", "charge", "bill", "cost", "price", "money",
                "amount", "overdue", "debt", "भुगतान", "पैसा", "ಪಾವತಿ"],
    "termination": ["terminat", "suspend", "ban", "block", "close account", "delete account",
                    "समाप्त", "ಮುಕ್ತಾಯ"],
    "arbitration": ["sue", "court", "lawsuit", "legal action", "lawyer", "arbitrat", "class action",
                    "मुकदमा", "ನ್ಯಾಯಾಲಯ"],
    "liability": ["liab", "responsible", "damage", "loss", "compensat", "fault",
                  "नुकसान", "ಹಾನಿ"],
}

def classify_intent(question: str) -> str:
    """Instant keyword-based intent classifier — zero API calls."""
    q = question.lower()
    scores = {ct: 0 for ct in CLAUSE_TYPES}
    for clause_type, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                scores[clause_type] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


# ---------------------------------------------------------------------------
# Language detection (best-effort — falls back to English)
# ---------------------------------------------------------------------------

def detect_language(text: str) -> str:
    """Return a language name string, e.g. 'English', 'Hindi', 'Kannada'."""
    try:
        from langdetect import detect
        code = detect(text)
        lang_map = {
            "en": "English",
            "hi": "Hindi",
            "kn": "Kannada",
            "ta": "Tamil",
            "te": "Telugu",
            "ml": "Malayalam",
            "mr": "Marathi",
            "bn": "Bengali",
            "gu": "Gujarati",
            "pa": "Punjabi",
            "ur": "Urdu",
        }
        return lang_map.get(code, "English")
    except Exception:
        return "English"


# ---------------------------------------------------------------------------
# Qdrant retrieval
# ---------------------------------------------------------------------------

def retrieve_chunks(
    query: str,
    doc_id: str,
    clause_type: str,
    top_k: int = 6,
    min_score: float = 0.35,
) -> list[dict]:
    """
    Embed the query and do filtered semantic search in Qdrant.
    Always filters by doc_id. Additionally filters by clause_type
    unless it's 'general' (too broad to filter usefully).
    """
    # Embed the query
    resp = openai_client.embeddings.create(model=EMBED_MODEL, input=[query])
    query_vec = resp.data[0].embedding

    # Build filter
    conditions = [FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
    if clause_type != "general":
        conditions.append(
            FieldCondition(key="clause_type", match=MatchValue(value=clause_type))
        )

    results = qdrant_client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_vec,
        query_filter=Filter(must=conditions),
        limit=top_k,
        with_payload=True,
        score_threshold=min_score,
    )

    # If filtered search returns too few results, fall back to doc-only filter
    if len(results) < 2 and clause_type != "general":
        results = qdrant_client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vec,
            query_filter=Filter(must=[
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id))
            ]),
            limit=top_k,
            with_payload=True,
            score_threshold=min_score,
        )

    return [
        {
            "text": r.payload["text"],
            "clause_type": r.payload.get("clause_type", "general"),
            "risk_score": r.payload.get("risk_score", 0),
            "page_num": r.payload.get("page_num", 0),
            "score": r.score,
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# LLM synthesis
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = """You are explaining what a legal document says to someone who cannot read legalese.
Answer their question using ONLY the clauses provided below.
Use the simplest words possible. Maximum 4 sentences.
If the answer involves giving away personal data, auto-renewal, arbitration, or limits on user rights — say so clearly.
Respond in {language}.

User question: {question}

Relevant clauses:
{clauses}"""

RISK_ADDENDUM = "\n\nBy the way, this section of the document is worth reading carefully before you agree."

def synthesize_answer(question: str, chunks: list[dict], language: str) -> str:
    """Generate a plain-language answer from retrieved chunks."""
    if not chunks:
        return (
            "I couldn't find a clear answer to that in this document. "
            "Try asking about data sharing, cancellation, payment terms, or your rights."
        )

    clauses_text = "\n\n---\n\n".join(
        f"[Clause type: {c['clause_type']}, Risk: {c['risk_score']}/3]\n{c['text']}"
        for c in chunks
    )

    prompt = SYNTHESIS_PROMPT.format(
        language=language,
        question=question,
        clauses=clauses_text[:3000],
    )

    resp = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
    )
    answer = resp.choices[0].message.content.strip()

    # Proactive risk flag: if any retrieved chunk is risk_score >= 2, add addendum
    max_risk = max((c["risk_score"] for c in chunks), default=0)
    if max_risk >= 2:
        answer += RISK_ADDENDUM

    return answer


def synthesize_answer_stream(question: str, chunks: list[dict], language: str):
    """
    Streaming version — yields text chunks so Vapi can start speaking
    before the full answer is generated, avoiding timeout.
    """
    if not chunks:
        yield "I couldn't find a clear answer to that in this document. Try asking about data sharing, cancellation, or payment terms."
        return

    clauses_text = "\n\n---\n\n".join(
        f"[Clause type: {c['clause_type']}, Risk: {c['risk_score']}/3]\n{c['text']}"
        for c in chunks
    )

    prompt = SYNTHESIS_PROMPT.format(
        language=language,
        question=question,
        clauses=clauses_text[:3000],
    )

    max_risk = max((c["risk_score"] for c in chunks), default=0)

    stream = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content

    if max_risk >= 2:
        yield RISK_ADDENDUM


# ---------------------------------------------------------------------------
# Main query entry point
# ---------------------------------------------------------------------------

def answer_query(question: str, doc_id: str) -> str:
    """
    Full RAG pipeline for a voice query.
    Returns a plain-language answer string ready for Vapi to speak.
    """
    language = detect_language(question)
    clause_type = classify_intent(question)
    chunks = retrieve_chunks(question, doc_id, clause_type)
    return synthesize_answer(question, chunks, language)
