"""
Run this ONCE after your backend is deployed to:
  1. Create the Vapi assistant with your webhook as the custom LLM
  2. Print the phone number to add to .env

Usage:
  python vapi_setup.py --doc-id <doc_id_from_ingest>

If you don't pass --doc-id, it creates a generic assistant that works
with whatever document is currently loaded in the server's DOC_REGISTRY.
"""

import argparse
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

VAPI_API_KEY = os.environ["VAPI_API_KEY"]
PUBLIC_URL = os.environ["PUBLIC_URL"].rstrip("/")


SYSTEM_PROMPT_TEMPLATE = """You are Consent Companion, a voice assistant that helps people understand legal documents in plain language.

You answer questions about a specific document that has already been uploaded and indexed.
DOC_ID:{doc_id}

Rules:
- Always answer in the language the user is speaking
- Use the simplest words possible — no legal jargon
- Keep answers to 4 sentences or less
- If a clause is risky or limits the user's rights, say so clearly
- If you cannot find the answer, say: "I couldn't find that in the document. Try asking about data sharing, cancellation, or payment terms."
"""


def create_assistant(doc_id: str = "LATEST"):
    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "name": "Consent Companion",
        "model": {
            "provider": "custom-llm",
            "model": "consent-companion",
            "url": f"{PUBLIC_URL}/chat",
            "systemPrompt": SYSTEM_PROMPT_TEMPLATE.format(doc_id=doc_id),
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "paula",  # warm, clear voice
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "multi",  # multilingual STT
        },
        "firstMessage": "Hello! I'm here to help you understand this document. What would you like to know?",
        "endCallMessage": "Thank you for using Consent Companion. Stay informed!",
        "endCallFunctionEnabled": False,
        "hipaaEnabled": False,
        "recordingEnabled": False,
    }

    resp = requests.post(
        "https://api.vapi.ai/assistant",
        headers=headers,
        json=payload,
    )
    if not resp.ok:
        print(f"Failed to create assistant: {resp.status_code} {resp.text}")
        sys.exit(1)

    assistant = resp.json()
    assistant_id = assistant["id"]
    print(f"\nAssistant created: {assistant_id}")

    # Buy / assign a phone number
    phone_resp = requests.post(
        "https://api.vapi.ai/phone-number",
        headers=headers,
        json={
            "provider": "twilio",
            "assistantId": assistant_id,
            # Vapi will auto-provision a US number if none specified
        },
    )
    if phone_resp.ok:
        phone_data = phone_resp.json()
        phone_number = phone_data.get("number", "check Vapi dashboard")
        print(f"Phone number: {phone_number}")
        print(f"\nAdd to your .env file:")
        print(f"  VAPI_PHONE_NUMBER={phone_number}")
    else:
        print(f"Phone provisioning response: {phone_resp.status_code} {phone_resp.text}")
        print("Go to dashboard.vapi.ai → Phone Numbers to assign a number manually.")

    print(f"\nDone! Your Vapi assistant ID: {assistant_id}")
    return assistant_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc-id", default="LATEST", help="doc_id from /ingest response")
    args = parser.parse_args()
    create_assistant(args.doc_id)
