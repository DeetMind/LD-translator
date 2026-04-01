"""
Vercel serverless entry point.
Re-exports the FastAPI app for Vercel's Python runtime.
"""
import sys
from pathlib import Path

# Ensure the project root is on the path so engine/ imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app
