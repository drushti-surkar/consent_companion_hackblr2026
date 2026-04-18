# Consent Companion

A voice-first tool that helps people understand legal documents in plain language. Upload a PDF, then ask questions by voice in any language and get clear answers.

Built for HackBlr 2026 — Problem Statement 3: Voice AI for Accessibility and Societal Impact.

---

## What it does

- Upload any legal document (terms of service, privacy policy, rental agreement)
- Ask questions by voice in English, Hindi, Kannada, Tamil, or Telugu
- Get plain-language answers spoken back to you
- See a clause-by-clause risk breakdown in the UI

---

## Stack

| Layer | Technology |
|---|---|
| Voice AI | Vapi (STT, TTS, conversation orchestration) |
| LLM | OpenAI GPT-4o-mini |
| Embeddings | OpenAI text-embedding-3-small |
| Vector DB | Qdrant Cloud |
| Backend | FastAPI (Python 3.11) |
| Frontend | Vanilla HTML/CSS/JS |
| Deployment | Railway |

---

## Architecture

```
PDF upload
  -> extract text (pypdf)
  -> chunk into 400-token segments
  -> classify each chunk by clause type (GPT-4o-mini)
  -> embed each chunk (text-embedding-3-small)
  -> store in Qdrant with clause_type + risk_score metadata

Voice query
  -> Vapi receives speech, transcribes it
  -> calls /lookup as a tool with the user's question
  -> backend classifies intent (keyword-based, instant)
  -> embeds query, filtered semantic search in Qdrant
  -> GPT-4o-mini synthesizes a plain-language answer
  -> Vapi speaks the answer back
```

---

## Local setup

### Requirements

- Python 3.11+
- Node.js (for bundling the Vapi web SDK, only needed once)
- Accounts: OpenAI, Qdrant Cloud, Vapi

### Environment variables

Create `backend/.env`:

```
OPENAI_API_KEY=sk-...
QDRANT_URL=https://xxxx.us-east-2-0.aws.cloud.qdrant.io
QDRANT_API_KEY=...
QDRANT_COLLECTION=consent_clauses
VAPI_API_KEY=...
VAPI_PUBLIC_KEY=...
VAPI_ASSISTANT_ID=...
VAPI_PHONE_NUMBER=+1...
PUBLIC_URL=https://your-deployed-url
DEMO_DOC_ID=
DEMO_DOC_NAME=
```

### Install and run

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000

---

## Deployment on Railway

1. Push repo to GitHub
2. Create a new project on railway.app, connect the repo
3. Set all environment variables in the Railway dashboard
4. Railway uses the `Dockerfile` at the repo root
5. Healthcheck runs at `/health`

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | /ingest | Upload a PDF, returns doc_id and clause summary |
| POST | /lookup | Vapi tool call handler — runs RAG and returns answer |
| POST | /chat | Legacy streaming SSE endpoint |
| GET | /docs/{doc_id} | Fetch clause summary for an ingested document |
| GET | /config | Returns Vapi keys and demo doc info for the frontend |
| GET | /health | Health check |

---

## Multilingual support

Intent classification uses keyword matching in English, Hindi, Kannada, and Tamil so the system works without an extra LLM call for language detection on the query path. Answer synthesis detects the user's language and responds in kind.
