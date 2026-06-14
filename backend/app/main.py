"""FastAPI application entry point.

Run:
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.agent.graph import build_graph, make_sqlite_checkpointer
from app.api.review import router as review_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.CHECKPOINT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # Build the HITL-enabled graph (with interrupt_before=["finalize"]).
    checkpointer = make_sqlite_checkpointer()
    app.state.checkpointer = checkpointer
    app.state.graph = build_graph(checkpointer=checkpointer)

    yield

    # SqliteSaver wraps a sqlite3.Connection — close it on shutdown.
    try:
        checkpointer.conn.close()  # type: ignore[attr-defined]
    except Exception:
        pass


app = FastAPI(title="ComplianceLens", version="0.3.0", lifespan=lifespan)

# CORS origins: comma-separated ALLOWED_ORIGINS env wins; falls back to dev defaults.
# In prod behind a single-origin reverse proxy (Nginx → CloudFront), browser calls
# are same-origin and CORS isn't exercised — set ALLOWED_ORIGINS only when you need
# cross-origin (e.g. Vercel frontend + EC2 backend on different hosts).
_allowed = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed.split(",") if o.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(review_router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "mock_llm": config.MOCK_LLM,
        "assess_model": config.OPENAI_MODEL_ASSESS,
        "ingest_model": config.OPENAI_MODEL_INGEST,
    }
