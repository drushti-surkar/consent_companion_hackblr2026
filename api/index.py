"""
Vercel Python serverless entry point.
Vercel imports this file and looks for an ASGI-compatible `app` object.
"""
import sys
import os

# Make the backend package importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.main import app   # noqa: F401  — Vercel picks this up as the ASGI handler
