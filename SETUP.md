# Consent Companion — Setup Guide

## What you need before starting

| Credential | Where to get it |
|---|---|
| OpenAI API key | platform.openai.com |
| Qdrant Cloud URL + API key | cloud.qdrant.io → free tier → create cluster |
| Vapi API key | dashboard.vapi.ai (use code `vapixhackblr` for $30 free) |

---

## Step 1 — Install dependencies

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 2 — Configure environment

```bash
cp ../.env.example .env
# Edit .env and fill in your API keys
```

Your `.env` needs:
```
OPENAI_API_KEY=sk-...
QDRANT_URL=https://xxxx.qdrant.io
QDRANT_API_KEY=...
VAPI_API_KEY=...
PUBLIC_URL=https://YOUR-DEPLOYED-URL   # see Step 3
```

---

## Step 3 — Deploy or expose publicly

Vapi needs a public HTTPS URL to call your `/chat` webhook.

**Option A — ngrok (fastest for local dev)**
```bash
# In a separate terminal:
ngrok http 8000
# Copy the https://xxxx.ngrok.io URL into PUBLIC_URL in .env
```

**Option B — Railway (recommended for demo)**
1. Push repo to GitHub
2. New project on railway.app → deploy from GitHub
3. Set environment variables in Railway dashboard
4. Copy the Railway URL into `PUBLIC_URL`

---

## Step 4 — Start the backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 — you'll see the upload UI.

---

## Step 5 — Create the Vapi assistant

After deploying (so PUBLIC_URL is set correctly):

```bash
python vapi_setup.py
```

This creates a Vapi assistant with your `/chat` webhook and provisions a phone number.
Copy the phone number into your `.env` as `VAPI_PHONE_NUMBER`.

Restart the server so the frontend picks up the phone number.

---

## Step 6 — Test it

1. Open the UI → upload the WhatsApp ToS PDF (or any legal PDF)
2. Note the phone number shown on screen
3. Call the number → ask "Can they share my location with advertisers?"
4. Try in Hindi: "डेटा किसको दिया जाएगा?"
5. Try in Kannada: "ಅವರು ನನ್ನ ಡೇಟಾವನ್ನು ಮಾರಾಟ ಮಾಡಬಹುದೇ?"

---

## Demo pre-load (do this before presenting)

To avoid ingesting live during the demo:

```bash
# With backend running:
curl -X POST http://localhost:8000/ingest \
  -F "file=@demo_docs/whatsapp_tos.pdf"
# Note the doc_id in the response
```

Then re-run vapi_setup.py with that doc_id:
```bash
python vapi_setup.py --doc-id <doc_id>
```

---

## Architecture recap for judges

```
PDF upload → pypdf extract → chunk (400 tok) → GPT-4o-mini classify
  → OpenAI embed → Qdrant upsert (with clause_type + risk_score indexes)

Voice call → Vapi STT → POST /chat → embed query
  → Qdrant filtered semantic search (clause_type filter + doc_id filter)
  → GPT-4o-mini synthesis (plain language, detected language)
  → Vapi TTS → user hears answer
```

**Why Qdrant is non-cosmetic:**
Users say "can they sell my stuff?" — not "data processing clause".
Qdrant's semantic search + `clause_type` filter bridges that gap
with low latency and zero keyword matching.
