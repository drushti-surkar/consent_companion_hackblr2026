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

from ingest import ingest_document
from retrieval import retrieve_chunks, classify_intent, detect_language, synthesize_answer_stream
from config import OPENAI_API_KEY, QDRANT_HOST, QDRANT_API_KEY
from openai import OpenAI

app = FastAPI(title="Consent Companion", version="1.0.0")


@app.on_event("startup")
async def preload_demo_doc():
    """Pre-register the demo doc so voice queries work immediately on startup."""
    demo_id = os.getenv("DEMO_DOC_ID")
    demo_name = os.getenv("DEMO_DOC_NAME", "demo.pdf")
    if demo_id:
        DOC_REGISTRY[demo_id] = {
            "doc_id": demo_id,
            "filename": demo_name,
            "total_chunks": 7,
            "clause_counts": {
                "data_rights": 2, "cancellation": 1, "payment": 1,
                "arbitration": 1, "liability": 1, "general": 1,
            },
            "risk_flags": [],
        }

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

@app.get("/docs/{doc_id}")
async def get_doc(doc_id: str):
    if doc_id not in DOC_REGISTRY:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DOC_REGISTRY[doc_id]


# ---------------------------------------------------------------------------
# /lookup — called by Vapi as a tool when user asks a question
# Vapi POSTs: { "message": { "toolCallList": [{ "function": { "name": "lookup_clause", "arguments": {"question": "...", "doc_id": "..."} } }] } }
# We return: { "results": [{ "toolCallId": "...", "result": "plain text answer" }] }
# ---------------------------------------------------------------------------

@app.post("/lookup")
async def lookup(request: Request):
    body = await request.json()
    log.info("LOOKUP body: %s", json.dumps(body)[:500])

    try:
        # Vapi tool call format
        msg = body.get("message", {})
        tool_calls = msg.get("toolCallList", [])
        if not tool_calls:
            raise ValueError("no toolCallList")

        tc = tool_calls[0]
        tc_id   = tc.get("id", "tc1")
        args    = tc.get("function", {}).get("arguments", {})
        if isinstance(args, str):
            args = json.loads(args)

        question = args.get("question", "")
        doc_id   = args.get("doc_id", "") or next(iter(DOC_REGISTRY), None)

        log.info("LOOKUP question=%r doc_id=%r", question, doc_id)

        if not question:
            answer = "Please ask a question about the document."
        elif not doc_id or doc_id not in DOC_REGISTRY:
            doc_id = next(iter(DOC_REGISTRY), None)
            if not doc_id:
                answer = "No document has been uploaded yet."
            else:
                answer = await _run_rag(question, doc_id)
        else:
            answer = await _run_rag(question, doc_id)

        log.info("LOOKUP answer=%r", answer[:120])
        return {"results": [{"toolCallId": tc_id, "result": answer}]}

    except Exception as e:
        log.exception("LOOKUP error: %s", e)
        return {"results": [{"toolCallId": "tc1", "result": "Sorry, I had trouble looking that up. Please try again."}]}


async def _run_rag(question: str, doc_id: str) -> str:
    """Run the full RAG pipeline in a thread pool so we don't block the event loop."""
    from retrieval import retrieve_chunks, classify_intent, detect_language, synthesize_answer
    loop = asyncio.get_event_loop()

    def _rag():
        language    = detect_language(question)
        clause_type = classify_intent(question)
        chunks      = retrieve_chunks(question, doc_id, clause_type)
        return synthesize_answer(question, chunks, language)

    return await loop.run_in_executor(None, _rag)


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

    # Resolve doc_id — fall back to any loaded doc
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
            from retrieval import retrieve_chunks, classify_intent, detect_language, synthesize_answer_stream

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

            # Now do the heavy lifting
            clause_type = classify_intent(user_query)

            try:
                # Run embed + search in a thread so we don't block the event loop
                loop = asyncio.get_event_loop()
                chunks_result = await loop.run_in_executor(
                    None, retrieve_chunks, user_query, doc_id, clause_type
                )

                # Stream the actual answer
                for text_piece in synthesize_answer_stream(user_query, chunks_result, language):
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
# Config endpoint — frontend fetches the Vapi phone number from here
# ---------------------------------------------------------------------------

from config import PUBLIC_URL

@app.get("/config")
async def get_config():
    """Returns public config the frontend needs (phone number, Vapi keys, etc.)."""
    demo_id   = os.getenv("DEMO_DOC_ID", "")
    demo_name = os.getenv("DEMO_DOC_NAME", "")
    demo_doc  = DOC_REGISTRY.get(demo_id, {})
    return {
        "phone":            os.getenv("VAPI_PHONE_NUMBER", ""),
        "public_url":       PUBLIC_URL,
        "vapi_public_key":  os.getenv("VAPI_PUBLIC_KEY", ""),
        "vapi_assistant_id": os.getenv("VAPI_ASSISTANT_ID", ""),
        "demo_doc_id":      demo_id,
        "demo_doc_name":    demo_name,
        "demo_risk_flags":  demo_doc.get("risk_flags", []),
    }


# ---------------------------------------------------------------------------
# Serve frontend (optional — if you want single-process deployment)
# ---------------------------------------------------------------------------
import os

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
