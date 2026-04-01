"""
Vercel entry point — imports the LDT v2 FastAPI app.
"""
import sys
from pathlib import Path

# Add v2/ to path so engine/ imports work
sys.path.insert(0, str(Path(__file__).resolve().parent / "v2"))

from main import app  # noqa: F401 — Vercel looks for `app` here
