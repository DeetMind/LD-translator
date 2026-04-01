"""
Vercel serverless entry point for LDT v2.
"""
import sys
from pathlib import Path

# Add v2/ to the path so engine/ and main imports work
v2_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(v2_dir))

from main import app
