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

_CONTRADICTION_TRIGGERS = [
    "told me", "said", "promised", "said it would", "they said", "he said", "she said",
    "verbally", "verbal", "agreed verbally", "mentioned", "assured me", "i was told",
    "मुझे बताया", "कहा था", "वादा किया", "ಹೇಳಿದ್ದರು", "சொன்னார்கள்",
]

_NEGOTIATE_TRIGGERS = [
    "negotiate", "change", "modify", "push back", "ask them to", "can i ask",
    "is this negotiable", "can i change", "challenge", "dispute this", "too harsh",
    "unfair clause", "better terms", "बदल सकता", "बातचीत", "ಮಾರ್ಪಡಿಸ",
]


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


def classify_mode(question: str) -> str:
    """
    Detect special interaction modes beyond simple Q&A.
    Returns: 'contradiction' | 'negotiate' | 'standard'
    """
    q = question.lower()
    if any(t in q for t in _CONTRADICTION_TRIGGERS):
        return "contradiction"
    if any(t in q for t in _NEGOTIATE_TRIGGERS):
        return "negotiate"
    return "standard"


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

IMPORTANT formatting rules:
- If the answer involves money amounts, fees, or time periods — state the REAL-WORLD CONSEQUENCE in plain numbers.
  Example: instead of "a penalty at the licensor's discretion", say "₹500 per day — so after 30 days that's ₹15,000 extra".
- If the answer involves giving away personal data, auto-renewal, arbitration, or limits on user rights — say so clearly and directly.
- After your answer, ask ONE natural follow-up: "Does that make sense, or should I explain it differently?"

Respond in {language}.

User question: {question}

Relevant clauses:
{clauses}"""


CONTRADICTION_PROMPT = """You are a legal document advisor protecting someone from exploitation.
The user claims something was verbally promised or told to them. Compare this claim to the actual written contract clauses.

User's claim: {question}

Written contract clauses:
{clauses}

Respond in {language}. Cover these points in maximum 4 sentences:
1. Does the written contract support or CONTRADICT what they were told?
2. If contradicted: state clearly that written contracts override verbal promises under Indian Contract Act.
3. Advise them to document the verbal promise (get it in writing via WhatsApp/email, or find a witness).
4. Tell them which specific clause number contradicts the verbal promise.

Be direct and protective. Do not soften the warning."""


NEGOTIATE_PROMPT = """You are a legal advisor helping someone get fairer contract terms.
The user wants to know if they can push back on a clause.

User question: {question}

Relevant clauses:
{clauses}

Respond in {language}. Cover in maximum 4 sentences:
1. Is this clause standard industry practice, or unusually one-sided?
2. Specifically what they can ask to change (be concrete — e.g. "ask to cap the late fee at 2% per month").
3. One example sentence they can actually say or write to request the change.
4. What to do if the other party refuses (sign anyway? walk away? consult a lawyer?).

Be practical and empowering."""


RISK_ADDENDUM = "\n\nBy the way, this section of the document is worth reading carefully before you agree."

def synthesize_answer(question: str, chunks: list[dict], language: str, mode: str = "standard") -> str:
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

    if mode == "contradiction":
        prompt = CONTRADICTION_PROMPT.format(language=language, question=question, clauses=clauses_text[:3000])
    elif mode == "negotiate":
        prompt = NEGOTIATE_PROMPT.format(language=language, question=question, clauses=clauses_text[:3000])
    else:
        prompt = SYNTHESIS_PROMPT.format(language=language, question=question, clauses=clauses_text[:3000])

    resp = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=350,
    )
    answer = resp.choices[0].message.content.strip()

    max_risk = max((c["risk_score"] for c in chunks), default=0)
    if max_risk >= 2 and mode == "standard":
        answer += RISK_ADDENDUM

    return answer


def synthesize_answer_stream(question: str, chunks: list[dict], language: str, mode: str = "standard"):
    """
    Streaming version — yields text chunks so Vapi can start speaking
    before the full answer is generated, avoiding timeout.
    Mode: 'standard' | 'contradiction' | 'negotiate'
    """
    if not chunks:
        yield "I couldn't find a clear answer to that in this document. Try asking about data sharing, cancellation, payment terms, or your rights."
        return

    clauses_text = "\n\n---\n\n".join(
        f"[Clause type: {c['clause_type']}, Risk: {c['risk_score']}/3]\n{c['text']}"
        for c in chunks
    )

    if mode == "contradiction":
        prompt = CONTRADICTION_PROMPT.format(language=language, question=question, clauses=clauses_text[:3000])
    elif mode == "negotiate":
        prompt = NEGOTIATE_PROMPT.format(language=language, question=question, clauses=clauses_text[:3000])
    else:
        prompt = SYNTHESIS_PROMPT.format(language=language, question=question, clauses=clauses_text[:3000])

    max_risk = max((c["risk_score"] for c in chunks), default=0)

    stream = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=350,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content

    if max_risk >= 2 and mode == "standard":
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
    mode = classify_mode(question)
    chunks = retrieve_chunks(question, doc_id, clause_type)
    return synthesize_answer(question, chunks, language, mode)
