"""
Document ingestion pipeline:
  PDF bytes → extract text → chunk → classify → embed → Qdrant upsert
"""

import json
import re
import uuid
from typing import IO

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
        # Payload indexes for fast filtered search
        for field, schema_type in [
            ("clause_type", PayloadSchemaType.KEYWORD),
            ("doc_id", PayloadSchemaType.KEYWORD),
            ("risk_score", PayloadSchemaType.INTEGER),
        ]:
            qdrant_client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name=field,
                field_schema=schema_type,
            )


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
# Main ingestion entry point
# ---------------------------------------------------------------------------

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

    return {
        "doc_id": doc_id,
        "filename": filename,
        "total_chunks": len(chunks),
        "clause_counts": clause_counts,
        "risk_flags": risk_flags,
    }
