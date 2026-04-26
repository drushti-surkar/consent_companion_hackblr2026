"""
Document ingestion pipeline:
  PDF bytes → extract text → chunk → classify → embed → Qdrant upsert
"""

import json
import re
import uuid
from typing import IO
from concurrent.futures import ThreadPoolExecutor

import pypdf
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
    PayloadSchemaType,
)

from config import (
    OPENAI_API_KEY,
    QDRANT_HOST,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    EMBED_MODEL,
    EMBED_DIM,
    LLM_MODEL,
    CLAUSE_TYPES,
)

openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant_client = QdrantClient(host=QDRANT_HOST, api_key=QDRANT_API_KEY, https=True, port=443)


# ---------------------------------------------------------------------------
# Qdrant collection setup
# ---------------------------------------------------------------------------

def ensure_collection():
    """Create the Qdrant collection if it doesn't exist, with payload indexes."""
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )
    # Always ensure payload indexes exist (safe to call on existing collections)
    for field, schema_type in [
        ("clause_type", PayloadSchemaType.KEYWORD),
        ("doc_id",      PayloadSchemaType.KEYWORD),
        ("risk_score",  PayloadSchemaType.INTEGER),
        ("rec_type",    PayloadSchemaType.KEYWORD),  # "chunk" vs "doc_summary"
    ]:
        try:
            qdrant_client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name=field,
                field_schema=schema_type,
            )
        except Exception:
            pass  # Index already exists — that's fine


# ---------------------------------------------------------------------------
# Qdrant doc-summary persistence (makes app stateless-safe on Vercel/Render)
# ---------------------------------------------------------------------------

def _persist_summary(summary: dict) -> None:
    """
    Store the full ingest summary as a special 'doc_summary' point in Qdrant.
    This means the app works even after a cold start / server restart —
    no Redis or external state store needed.
    """
    qdrant_client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[PointStruct(
            id=str(uuid.uuid4()),
            vector=[0.0] * EMBED_DIM,   # dummy vector — we only need the payload
            payload={"rec_type": "doc_summary", **summary},
        )],
    )


def get_doc_summary(doc_id: str) -> dict | None:
    """
    Retrieve a previously ingested doc summary from Qdrant.
    Used as a fallback when DOC_REGISTRY (in-memory) doesn't have the doc
    (e.g. after a server restart or on a stateless serverless platform).
    """
    results, _ = qdrant_client.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=Filter(must=[
            FieldCondition(key="doc_id",   match=MatchValue(value=doc_id)),
            FieldCondition(key="rec_type", match=MatchValue(value="doc_summary")),
        ]),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if results:
        payload = dict(results[0].payload)
        payload.pop("rec_type", None)   # strip internal field before returning
        return payload
    return None


# ---------------------------------------------------------------------------
# PDF → text
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file: IO[bytes]) -> list[dict]:
    """Return list of {page_num, text} dicts."""
    reader = pypdf.PdfReader(file)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"page_num": i + 1, "text": text})
    return pages


# ---------------------------------------------------------------------------
# Chunking (recursive, ~400 tokens / 50-token overlap, by character proxy)
# ---------------------------------------------------------------------------

CHUNK_SIZE = 1600   # ~400 tokens at ~4 chars/token
CHUNK_OVERLAP = 200  # ~50 tokens

def _split_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Simple recursive splitter by paragraphs, then sentences, then characters."""
    if len(text) <= size:
        return [text.strip()] if text.strip() else []

    # Try splitting on double newlines (paragraphs)
    separators = ["\n\n", "\n", ". ", " "]
    for sep in separators:
        parts = text.split(sep)
        if len(parts) > 1:
            chunks = []
            current = ""
            for part in parts:
                candidate = current + (sep if current else "") + part
                if len(candidate) <= size:
                    current = candidate
                else:
                    if current.strip():
                        chunks.append(current.strip())
                    # Start next chunk with overlap from end of current
                    overlap_text = current[-overlap:] if len(current) > overlap else current
                    current = overlap_text + (sep if overlap_text else "") + part
            if current.strip():
                chunks.append(current.strip())
            if len(chunks) > 1:
                return chunks

    # Hard split as last resort
    return [text[i : i + size].strip() for i in range(0, len(text), size - overlap) if text[i : i + size].strip()]


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Return list of {text, page_num} chunk dicts."""
    chunks = []
    for page in pages:
        for chunk_text in _split_text(page["text"]):
            if len(chunk_text) > 50:  # skip tiny fragments
                chunks.append({"text": chunk_text, "page_num": page["page_num"]})
    return chunks


# ---------------------------------------------------------------------------
# Clause classification (runs at ingest time — latency doesn't matter)
# ---------------------------------------------------------------------------

CLASSIFY_PROMPT = """You are a legal document classifier. Given a clause from a legal document, output ONLY valid JSON with two fields:
- "clause_type": one of [{types}]
- "risk_score": integer 0-3 (0=benign/standard, 1=slightly concerning, 2=concerning, 3=high risk — user rights significantly impacted)

High risk examples: auto-renewal traps, mandatory arbitration, broad data monetization, unilateral contract changes, no-refund policies.

Clause:
{clause}

Output JSON only, no explanation."""


def classify_chunk(text: str) -> dict:
    """Return {clause_type, risk_score} for a text chunk."""
    prompt = CLASSIFY_PROMPT.format(
        types=", ".join(CLAUSE_TYPES),
        clause=text[:800],  # limit to avoid token waste
    )
    try:
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=60,
            response_format={"type": "json_object"},
        )
        result = json.loads(resp.choices[0].message.content)
        clause_type = result.get("clause_type", "general")
        if clause_type not in CLAUSE_TYPES:
            clause_type = "general"
        risk_score = int(result.get("risk_score", 0))
        risk_score = max(0, min(3, risk_score))
        return {"clause_type": clause_type, "risk_score": risk_score}
    except Exception:
        return {"clause_type": "general", "risk_score": 0}


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embed a list of strings. Returns list of vectors."""
    # OpenAI allows up to 2048 inputs per call; chunk if needed
    batch_size = 100
    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = openai_client.embeddings.create(model=EMBED_MODEL, input=batch)
        all_vectors.extend([item.embedding for item in resp.data])
    return all_vectors


# ---------------------------------------------------------------------------
# Overall risk score (document-level, 0–10)
# ---------------------------------------------------------------------------

def compute_overall_risk(classifications: list[dict]) -> dict:
    """
    Aggregate per-clause risk_scores into a single 0–10 document risk score.
    Returns {score, badge, label, high_risk_count}.
    """
    if not classifications:
        return {"score": 0, "badge": "safe", "label": "Low Risk", "high_risk_count": 0}

    total_weight = sum(c["risk_score"] for c in classifications)
    max_possible = 3 * len(classifications)
    raw_score = (total_weight / max_possible) * 10 if max_possible > 0 else 0

    # Extra boost per score-3 clause (each one is a serious red flag)
    count_score_3 = sum(1 for c in classifications if c["risk_score"] == 3)
    score = min(10, round(raw_score + count_score_3 * 0.6))

    high_risk_count = sum(1 for c in classifications if c["risk_score"] >= 2)

    if score <= 3:
        badge, label = "safe", "Low Risk"
    elif score <= 6:
        badge, label = "caution", "Review Carefully"
    else:
        badge, label = "danger", "High Risk"

    return {"score": score, "badge": badge, "label": label, "high_risk_count": high_risk_count}


# ---------------------------------------------------------------------------
# "Before You Sign" checklist generation
# ---------------------------------------------------------------------------

CHECKLIST_PROMPT = """You are a legal advisor helping a regular person decide whether to sign a document.
Given the high-risk clauses below from a document called "{filename}", generate EXACTLY 5 plain-language action items.

Rules:
- Each item starts with an action verb: Check, Ask, Confirm, Avoid, Note, Verify, Understand, Demand
- Reference the specific clause concern (no legal jargon)
- Maximum 20 words per item
- Focus on protecting the signer's rights and money

Output JSON: {{"items": ["1. Action item", "2. Action item", "3. Action item", "4. Action item", "5. Action item"]}}

High-risk clauses:
{clauses}"""


def generate_checklist(chunks: list[dict], classifications: list[dict], filename: str) -> list[str]:
    """Generate a 5-point 'Before You Sign' checklist from the document's riskiest clauses."""
    risky = [
        (c, cls) for c, cls in zip(chunks, classifications)
        if cls["risk_score"] >= 2
    ][:6]

    if not risky:
        risky = list(zip(chunks, classifications))[:5]

    clauses_text = "\n\n---\n\n".join(
        f"[{cls['clause_type']}, risk {cls['risk_score']}/3]: {chunk['text'][:400]}"
        for chunk, cls in risky
    )

    try:
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": CHECKLIST_PROMPT.format(
                filename=filename, clauses=clauses_text
            )}],
            temperature=0.3,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content.strip())
        items = parsed.get("items") or parsed.get("checklist") or list(parsed.values())[0]
        return [str(i) for i in items[:5]]
    except Exception:
        return [
            "1. Verify all payment amounts, fees, and late penalties before signing.",
            "2. Check whether your personal or health data can be shared or sold.",
            "3. Confirm the cancellation and full refund policy in writing.",
            "4. Ask about arbitration clauses — they prevent you from suing in court.",
            "5. Note any clause letting the other party change terms without notice.",
        ]


# ---------------------------------------------------------------------------
# Plain Number Translator — turns legalese numbers into real consequences
# ---------------------------------------------------------------------------

PLAIN_NUMBERS_PROMPT = """Extract all significant monetary amounts, fees, percentages, time periods, and penalties from these legal clauses.
For each one, write the real-world consequence in plain everyday language.
Focus on amounts that could financially harm or restrict the signer.

Output JSON: {{"numbers": [{{"original": "exact legal phrase", "plain": "plain consequence in 1 sentence", "clause_type": "category"}}]}}

Rules:
- Maximum 8 items
- Skip trivial/benign numbers (e.g. document version dates)
- Make the "plain" field visceral and concrete (e.g. "₹500/day = ₹15,000 if you're 30 days late")
- Infer currency context (Indian Rupee ₹ if no symbol given)

Clauses:
{clauses}"""


def extract_plain_numbers(chunks: list[dict], classifications: list[dict]) -> list[dict]:
    """Extract numbers/amounts from risky clauses and explain their real-world impact."""
    risky = [
        (c, cls) for c, cls in zip(chunks, classifications)
        if cls["risk_score"] >= 2
    ][:8]

    if not risky:
        return []

    clauses_text = "\n\n---\n\n".join(
        f"[{cls['clause_type']}]: {chunk['text'][:500]}"
        for chunk, cls in risky
    )

    try:
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": PLAIN_NUMBERS_PROMPT.format(clauses=clauses_text)}],
            temperature=0.2,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content.strip())
        items = parsed.get("numbers") or parsed.get("items") or list(parsed.values())[0]
        return items[:8] if isinstance(items, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Contradiction Detector — finds conflicting clauses in the document
# ---------------------------------------------------------------------------

CONTRADICTION_PROMPT = """Analyze these legal clauses for contradictions or inconsistencies.
Look for:
- Conflicting rights or obligations
- Inconsistent time periods or amounts
- Clauses that cancel each other out
- Ambiguities that could be interpreted differently

For each contradiction found, output the conflicting parts and explain the issue in plain language.

Output JSON: {{"contradictions": [{{"clause1": "exact text from first clause", "clause2": "exact text from second clause", "explanation": "plain explanation of the contradiction", "severity": "high|medium|low"}}]}}

Rules:
- Maximum 5 contradictions
- Only include real contradictions, not minor differences
- "severity" based on impact: high = major rights affected, medium = important terms, low = minor
- If no contradictions found, return empty array

Clauses:
{clauses}"""


def detect_contradictions(chunks: list[dict], classifications: list[dict]) -> list[dict]:
    """Detect contradictions between clauses in the document."""
    # Use all chunks, not just risky ones, since contradictions can be between any clauses
    clauses_text = "\n\n---\n\n".join(
        f"[{i+1}] [{cls['clause_type']}]: {chunk['text'][:500]}"
        for i, (chunk, cls) in enumerate(zip(chunks, classifications))
    )

    try:
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": CONTRADICTION_PROMPT.format(clauses=clauses_text)}],
            temperature=0.2,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content.strip())
        items = parsed.get("contradictions") or []
        return items[:5] if isinstance(items, list) else []
    except Exception:
        return []


def ingest_text(text: str, title: str = "Pasted Document") -> dict:
    """
    Ingest raw pasted text — same pipeline as ingest_document but skips PDF extraction.
    Useful when the user copies text from a contract or pastes from a photo/scan.
    """
    ensure_collection()
    doc_id = str(uuid.uuid4())

    # Treat the whole text as one "page"
    pages = [{"page_num": 1, "text": text}]
    chunks = chunk_pages(pages)
    if not chunks:
        raise ValueError("No usable text content found. Please paste at least a few sentences.")

    # Same pipeline from here
    classifications = [classify_chunk(c["text"]) for c in chunks]
    vectors = embed_texts([c["text"] for c in chunks])

    points = []
    for chunk, cls, vec in zip(chunks, classifications, vectors):
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={
                "text": chunk["text"],
                "clause_type": cls["clause_type"],
                "risk_score": cls["risk_score"],
                "page_num": chunk["page_num"],
                "doc_id": doc_id,
                "filename": title,
            },
        ))

    qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)

    clause_counts: dict[str, int] = {}
    risk_flags = []
    for chunk, cls in zip(chunks, classifications):
        ct = cls["clause_type"]
        clause_counts[ct] = clause_counts.get(ct, 0) + 1
        if cls["risk_score"] >= 2:
            risk_flags.append({
                "text": chunk["text"][:300],
                "clause_type": ct,
                "risk_score": cls["risk_score"],
                "page_num": chunk["page_num"],
            })

    overall_risk = compute_overall_risk(classifications)
    with ThreadPoolExecutor(max_workers=3) as pool:
        checklist = pool.submit(generate_checklist, chunks, classifications, title).result()
        plain_numbers = pool.submit(extract_plain_numbers, chunks, classifications).result()
        contradictions = pool.submit(detect_contradictions, chunks, classifications).result()

    result = {
        "doc_id": doc_id,
        "filename": title,
        "total_chunks": len(chunks),
        "clause_counts": clause_counts,
        "risk_flags": risk_flags,
        "overall_risk": overall_risk,
        "checklist": checklist,
        "plain_numbers": plain_numbers,
        "contradictions": contradictions,
    }
    _persist_summary(result)   # ← stateless-safe persistence
    return result


def ingest_document(file: IO[bytes], filename: str) -> dict:
    """
    Full pipeline: PDF → chunks → classify → embed → upsert to Qdrant.
    Returns summary stats dict.
    """
    ensure_collection()

    doc_id = str(uuid.uuid4())

    # 1. Extract
    pages = extract_text_from_pdf(file)
    if not pages:
        raise ValueError("Could not extract text from PDF. Is it a scanned image?")

    # 2. Chunk
    chunks = chunk_pages(pages)
    if not chunks:
        raise ValueError("No text chunks found after splitting.")

    # 3. Classify each chunk
    classifications = [classify_chunk(c["text"]) for c in chunks]

    # 4. Embed all chunks in one batch
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)

    # 5. Build Qdrant points
    points = []
    for i, (chunk, cls, vec) in enumerate(zip(chunks, classifications, vectors)):
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    "text": chunk["text"],
                    "clause_type": cls["clause_type"],
                    "risk_score": cls["risk_score"],
                    "page_num": chunk["page_num"],
                    "doc_id": doc_id,
                    "filename": filename,
                },
            )
        )

    # 6. Upsert
    qdrant_client.upsert(collection_name=QDRANT_COLLECTION, points=points)

    # 7. Build summary
    clause_counts: dict[str, int] = {}
    risk_flags = []
    for chunk, cls in zip(chunks, classifications):
        ct = cls["clause_type"]
        clause_counts[ct] = clause_counts.get(ct, 0) + 1
        if cls["risk_score"] >= 2:
            risk_flags.append({
                "text": chunk["text"][:300],
                "clause_type": ct,
                "risk_score": cls["risk_score"],
                "page_num": chunk["page_num"],
            })

    # 8. Compute overall risk score, generate checklist + plain numbers in parallel
    overall_risk = compute_overall_risk(classifications)

    with ThreadPoolExecutor(max_workers=3) as pool:
        checklist_future = pool.submit(generate_checklist, chunks, classifications, filename)
        plain_numbers_future = pool.submit(extract_plain_numbers, chunks, classifications)
        contradictions_future = pool.submit(detect_contradictions, chunks, classifications)
        checklist = checklist_future.result()
        plain_numbers = plain_numbers_future.result()
        contradictions = contradictions_future.result()

    result = {
        "doc_id": doc_id,
        "filename": filename,
        "total_chunks": len(chunks),
        "clause_counts": clause_counts,
        "risk_flags": risk_flags,
        "overall_risk": overall_risk,
        "checklist": checklist,
        "plain_numbers": plain_numbers,
        "contradictions": contradictions,
    }
    _persist_summary(result)   # ← stateless-safe persistence
    return result
