"""Vercel serverless entrypoint.

Adds backend/ to the import path and flags serverless mode so the app skips
background polling loops (they can't run in short-lived functions).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SERVERLESS", "1")

from main import app  # noqa: E402  (FastAPI ASGI app)
