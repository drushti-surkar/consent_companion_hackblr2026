import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
QDRANT_URL = os.environ["QDRANT_URL"]  # full https:// URL
QDRANT_HOST = QDRANT_URL.replace("https://", "").replace("http://", "").rstrip("/")
QDRANT_API_KEY = os.environ["QDRANT_API_KEY"]
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "consent_clauses")
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000")
VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")

# Embedding model — text-embedding-3-small gives 1536-dim vectors
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536

# LLM for classification and synthesis
LLM_MODEL = "gpt-4o-mini"

CLAUSE_TYPES = [
    "data_rights",
    "cancellation",
    "liability",
    "payment",
    "termination",
    "arbitration",
    "general",
]
