"""Config loaded from environment / .env."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()  # anthropic | openai | none
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# How many example values per column to show the LLM (keeps prompt small + private).
SAMPLE_VALUES = 5
