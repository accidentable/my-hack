"""Environment / runtime configuration.

Single source of paths and settings. Other modules import from here.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/ root (this file lives at backend/app/config.py)
BACKEND_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = BACKEND_ROOT / "app"

# Load .env from backend/.env if present
load_dotenv(BACKEND_ROOT / ".env")

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

# Two-tier model split:
#   ASSESS  — compliance judgment (precision-critical, Structured Outputs)
#   INGEST  — vision claim extraction from card images (cost-sensitive)
# Backward-compat: if only OPENAI_MODEL / OPENAI_MODEL_MINI are present in .env,
# we still honor them as fallbacks so existing setups keep working.
OPENAI_MODEL_ASSESS: str = os.getenv(
    "OPENAI_MODEL_ASSESS",
    os.getenv("OPENAI_MODEL", "gpt-5.4"),
)
OPENAI_MODEL_INGEST: str = os.getenv(
    "OPENAI_MODEL_INGEST",
    os.getenv("OPENAI_MODEL_MINI", "gpt-5.4-mini"),
)
# Deprecated single-model knobs (kept for any straggler imports).
OPENAI_MODEL: str = OPENAI_MODEL_ASSESS
OPENAI_MODEL_MINI: str = OPENAI_MODEL_INGEST

# Mock mode: when set, the LLM client returns canned fixtures instead of
# calling OpenAI. Useful for offline development and smoke tests on Day 1.
MOCK_LLM: bool = os.getenv("COMPLIANCELENS_MOCK_LLM", "0") == "1"

# Data locations
DATA_DIR = BACKEND_ROOT / "data"
REGULATIONS_DIR = DATA_DIR / "regulations"
SAMPLES_DIR = DATA_DIR / "samples"

# Chroma persistent directory (relative to backend root)
CHROMA_DIR = BACKEND_ROOT / os.getenv("CHROMA_DIR", ".chroma")

# LangGraph SQLite checkpointer (HITL resume) — Day 3
CHECKPOINT_DB_PATH = BACKEND_ROOT / os.getenv("CHECKPOINT_DB", ".checkpoints.sqlite")

# Uploaded content goes here so resume can re-open the original file by path.
UPLOADS_DIR = BACKEND_ROOT / "data" / "uploads"

# Knowledge artifacts
# reg_index.json lives alongside the regulation text files so curating the
# regulation set is one cohesive directory edit.
REG_INDEX_PATH = REGULATIONS_DIR / "reg_index.json"
RULES_PATH = APP_ROOT / "rules" / "rules.yaml"

# Agent runtime
MAX_VERIFY_RETRIES = 2  # used Day 2+; Day 1 graph is straight-line


def require_openai_key() -> str:
    if MOCK_LLM:
        return "MOCK"
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy backend/.env.example to backend/.env "
            "and fill in your key, or set COMPLIANCELENS_MOCK_LLM=1 to run offline."
        )
    return OPENAI_API_KEY
