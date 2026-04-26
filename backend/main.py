"""
Consent Companion — FastAPI backend
Endpoints:
  POST /ingest         — upload a PDF, returns doc_id + clause summary
  POST /chat           — Vapi custom LLM webhook
  GET  /docs/{doc_id}  — fetch summary for a previously ingested doc
  GET  /health         — health check
"""

import io
import json
import asyncio
import logging
from typing import Any, AsyncGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("consent")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ingest import ingest_document, ingest_text, get_doc_summary, ensure_collection
from retrieval import retrieve_chunks, classify_intent, classify_mode, detect_language, synthesize_answer_stream, answer_query
from config import OPENAI_API_KEY, QDRANT_HOST, QDRANT_API_KEY
from openai import OpenAI

app = FastAPI(title="Consent Companion", version="1.0.0")


@app.on_event("startup")
async def preload_demo_doc():
    """
    Pre-register the demo doc from Qdrant so voice queries work immediately.
    Falls back to a minimal stub if Qdrant hasn't been populated yet.
    """
    # Ensure Qdrant collection + indexes exist before any queries
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, ensure_collection)
    except Exception as e:
        log.warning("ensure_collection failed on startup: %s", e)

    demo_id = os.getenv("DEMO_DOC_ID")
    demo_name = os.getenv("DEMO_DOC_NAME", "demo.pdf")
    if not demo_id:
        return
    # Try Qdrant first (works after first ingest even across restarts)
    try:
        summary = get_doc_summary(demo_id)
        if summary:
            DOC_REGISTRY[demo_id] = summary
            log.info("Demo doc loaded from Qdrant: %s (%s)", demo_id, demo_name)
            return
    except Exception as e:
        log.warning("Qdrant demo-doc lookup failed: %s", e)
    # Fallback stub (works on very first boot before any ingest)
    DOC_REGISTRY[demo_id] = {
        "doc_id": demo_id,
        "filename": demo_name,
        "total_chunks": 7,
        "clause_counts": {"data_rights": 2, "cancellation": 1, "payment": 1,
                          "arbitration": 1, "liability": 1, "general": 1},
        "risk_flags": [],
        "overall_risk": {"score": 8, "badge": "danger", "label": "High Risk", "high_risk_count": 4},
        "checklist": [],
        "plain_numbers": [],
        "contradictions": [],
    }
    log.info("Demo doc stub registered: %s", demo_id)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory doc registry (maps doc_id → summary dict)
# For a hackathon this is fine; replace with Redis/DB for production
DOC_REGISTRY: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Ingest endpoint
# ---------------------------------------------------------------------------

@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    """
    Upload a PDF. Returns doc_id, clause breakdown, and risk flags.
    Frontend uses doc_id for all subsequent voice queries.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:  # 20 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 20 MB).")

    try:
        summary = ingest_document(io.BytesIO(contents), file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    DOC_REGISTRY[summary["doc_id"]] = summary
    return summary


# ---------------------------------------------------------------------------
# Doc summary endpoint
# ---------------------------------------------------------------------------

@app.post("/ingest-text")
async def ingest_text_endpoint(request: Request):
    """
    Accept raw pasted text, run the full RAG pipeline, return the same
    summary dict as /ingest. Lets users skip PDF upload entirely.
    """
    body = await request.json()
    text  = (body.get("text") or "").strip()
    title = (body.get("title") or "Pasted Document").strip() or "Pasted Document"

    if not text:
        raise HTTPException(status_code=400, detail="No text provided.")
    if len(text) > 100_000:
        raise HTTPException(status_code=400, detail="Text too long (max 100,000 characters).")
    if len(text) < 80:
        raise HTTPException(status_code=400, detail="Text too short — please paste at least a few sentences.")

    try:
        summary = ingest_text(text, title)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    DOC_REGISTRY[summary["doc_id"]] = summary
    return summary


@app.get("/docs/{doc_id}")
async def get_doc(doc_id: str):
    if doc_id in DOC_REGISTRY:
        return DOC_REGISTRY[doc_id]
    # Fallback: query Qdrant (handles cold starts + stateless serverless platforms)
    try:
        summary = get_doc_summary(doc_id)
        if summary:
            DOC_REGISTRY[doc_id] = summary   # warm the in-memory cache
            return summary
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Document not found.")


# ---------------------------------------------------------------------------
# Vapi custom LLM webhook  (POST /chat)
# ---------------------------------------------------------------------------
# Vapi sends an OpenAI-compatible request body. We parse the last user message,
# run the RAG pipeline, and return an OpenAI-compatible response.
#
# Vapi passes the doc_id via the system prompt or via a custom metadata field.
# We embed the doc_id in the Vapi system prompt during assistant creation so it
# arrives in every request. Format: "DOC_ID:<uuid>"
# ---------------------------------------------------------------------------

class VapiMessage(BaseModel):
    role: str
    content: str


class VapiRequest(BaseModel):
    model: str = "consent-companion"
    messages: list[VapiMessage]
    # Vapi may pass extra fields; allow them
    model_config = {"extra": "allow"}


def _extract_doc_id(messages: list[VapiMessage]) -> str | None:
    """Parse doc_id from the system message embedded by Vapi."""
    for msg in messages:
        if msg.role == "system" and "DOC_ID:" in msg.content:
            for part in msg.content.split():
                if part.startswith("DOC_ID:"):
                    return part.split(":", 1)[1].strip()
    return None


def _last_user_message(messages: list[VapiMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return ""


@app.post("/chat")
async def chat(request: Request):
    """
    Vapi custom LLM webhook — streams OpenAI-compatible SSE so Vapi
    starts speaking before the full answer is generated.
    """
    body = await request.json()

    # Parse messages manually to tolerate any extra Vapi fields
    messages = [VapiMessage(**m) for m in body.get("messages", [])]
    stream_requested = body.get("stream", False)

    # Extract doc_id from metadata (preferred) or system prompt
    metadata = body.get("metadata", {})
    doc_id = metadata.get("docId") or _extract_doc_id(messages)
    user_query = _last_user_message(messages)

    # Resolve doc_id — try Qdrant if not in memory, then fall back to first loaded doc
    if doc_id and doc_id not in DOC_REGISTRY:
        try:
            summary = get_doc_summary(doc_id)
            if summary:
                DOC_REGISTRY[doc_id] = summary
        except Exception:
            pass
    if not doc_id or doc_id not in DOC_REGISTRY:
        doc_id = next(iter(DOC_REGISTRY), None) if DOC_REGISTRY else None

    async def event_stream() -> AsyncGenerator[str, None]:
        call_id = "chatcmpl-consent"

        def chunk(content: str, finish: str | None = None) -> str:
            return f'data: {json.dumps({"id": call_id, "object": "chat.completion.chunk", "model": "consent-companion", "choices": [{"index": 0, "delta": {"content": content} if content else {}, "finish_reason": finish}]})}\n\n'

        # Opening role chunk
        yield f'data: {json.dumps({"id": call_id, "object": "chat.completion.chunk", "model": "consent-companion", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]})}\n\n'

        if not user_query:
            yield chunk("I didn't catch that. Could you please repeat your question?")
        elif not doc_id:
            yield chunk("No document has been uploaded yet. Please upload a document first.")
        else:
            # Yield a filler phrase immediately so Vapi keeps the call alive
            # while we do the slow embedding + Qdrant round-trip
            language = detect_language(user_query)
            filler = {
                "Hindi": "एक पल, मैं देख रहा हूँ...",
                "Kannada": "ಒಂದು ಕ್ಷಣ...",
                "Tamil": "ஒரு நிமிடம்...",
                "Telugu": "ఒక్క క్షణం...",
            }.get(language, "Let me check that for you.")
            yield chunk(filler + " ")

            # Classify both intent (clause type) and mode (standard/contradiction/negotiate)
            clause_type = classify_intent(user_query)
            mode = classify_mode(user_query)

            try:
                # Run embed + search in a thread so we don't block the event loop
                loop = asyncio.get_event_loop()
                chunks_result = await loop.run_in_executor(
                    None, retrieve_chunks, user_query, doc_id, clause_type
                )

                # Stream the actual answer with the appropriate mode
                for text_piece in synthesize_answer_stream(user_query, chunks_result, language, mode):
                    yield chunk(text_piece)
            except Exception as e:
                log.error(f"Error processing query: {e}")
                yield chunk("Sorry, I encountered an error while processing your question. Please try again.")

        # For conversational mode, don't send finish_reason to keep the call open
        yield chunk("")
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Vapi tool-call endpoint  (POST /lookup)
# ---------------------------------------------------------------------------
# Used when Vapi is configured with a "tool" (serverUrl) rather than custom LLM.
# Vapi sends a tool-call request; we run RAG and return the result synchronously.
# ---------------------------------------------------------------------------

@app.post("/lookup")
async def lookup(request: Request):
    """
    Vapi tool-call webhook. Receives a tool call payload, runs the RAG pipeline,
    and returns an OpenAI-compatible tool result so Vapi can speak the answer.
    """
    body = await request.json()
    log.info("Lookup body: %s", json.dumps(body)[:400])

    # Vapi sends either a top-level message object or a list under 'message'
    msg = body if "toolCallList" in body else body.get("message", body)

    tool_call_list = msg.get("toolCallList") or msg.get("tool_calls") or []
    call_meta      = msg.get("call", {})
    metadata       = call_meta.get("metadata", {}) or body.get("metadata", {})

    # Resolve doc_id: prefer metadata, then fall back to first loaded doc
    doc_id = metadata.get("docId") or metadata.get("doc_id")
    if not doc_id or doc_id not in DOC_REGISTRY:
        doc_id = next(iter(DOC_REGISTRY), None)

    results = []
    for tc in tool_call_list:
        tool_call_id = tc.get("id", "call_unknown")
        fn = tc.get("function", {})
        raw_args = fn.get("arguments", "{}")
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except Exception:
            args = {}

        question = (
            args.get("question")
            or args.get("query")
            or args.get("message")
            or args.get("input")
            or ""
        )

        if not question:
            result_text = "I didn't receive a question. Please try asking again."
        elif not doc_id:
            result_text = "No document has been uploaded yet. Please upload a document first."
        else:
            try:
                loop = asyncio.get_event_loop()
                result_text = await loop.run_in_executor(None, answer_query, question, doc_id)
            except Exception as e:
                log.error("Lookup error: %s", e)
                result_text = "Sorry, I had trouble finding that information. Please try again."

        results.append({"toolCallId": tool_call_id, "result": result_text})

    return JSONResponse({"results": results})


# ---------------------------------------------------------------------------
# Config endpoint — frontend fetches the Vapi phone number from here
# ---------------------------------------------------------------------------

from config import PUBLIC_URL

@app.get("/config")
async def get_config():
    """Returns public config the frontend needs (phone number, Vapi keys, demo doc, etc.)."""
    return {
        "phone": os.getenv("VAPI_PHONE_NUMBER", ""),
        "public_url": PUBLIC_URL,
        "vapi_public_key": os.getenv("VAPI_PUBLIC_KEY", ""),
        "vapi_assistant_id": os.getenv("VAPI_ASSISTANT_ID", ""),
        "demo_doc_id": os.getenv("DEMO_DOC_ID", ""),
        "demo_doc_name": os.getenv("DEMO_DOC_NAME", ""),
    }


# ---------------------------------------------------------------------------
# Serve frontend (optional — if you want single-process deployment)
# ---------------------------------------------------------------------------
import os

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
