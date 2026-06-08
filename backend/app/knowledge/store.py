"""Regulation knowledge store.

Two functions matter to the rest of the app:

1. ``search(query, k)``      — semantic lookup of regulation chunks via Chroma,
                               returns list[Regulation] (architecture §4 shape).
2. ``article_exists(id)``    — used by the verify node to catch LLM hallucination.

Backends:
- **Chroma** (preferred). Built by ``ingest_regs.py``. Persists to ``.chroma``.
  Uses the same embedding function on both write and read paths.
- **Fallback**. Reads ``reg_index.json`` and matches by patterns when Chroma is
  absent or empty. The demo still runs end-to-end without Chroma.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app import config
from app.agent.state import Regulation


# -----------------------------------------------------------------------------
# Regulation index (verify + fallback retrieve both use this)
# -----------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_index() -> dict[str, dict[str, Any]]:
    if not config.REG_INDEX_PATH.exists():
        return {}
    with config.REG_INDEX_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def article_exists(article_id: str) -> bool:
    """Used by verify node — was this regulation_id actually in our index?"""
    return article_id in _load_index()


def get_article(article_id: str) -> dict[str, Any] | None:
    return _load_index().get(article_id)


def _load_full_text(article_id: str) -> str:
    meta = get_article(article_id)
    if meta is None:
        return ""
    # New schema (data/regulations/reg_index.json) uses "file" — a basename
    # resolved against REGULATIONS_DIR. Old schema used "source_file" — a path
    # relative to BACKEND_ROOT. Support both so future curation has slack.
    filename = meta.get("file") or meta.get("source_file")
    if not filename:
        return meta.get("title", "")
    src = config.REGULATIONS_DIR / filename
    if not src.exists():
        # Allow source_file-style relative paths as a secondary form.
        candidate = config.BACKEND_ROOT / filename
        if candidate.exists():
            src = candidate
        else:
            return meta.get("title", "")
    return src.read_text(encoding="utf-8")


# -----------------------------------------------------------------------------
# Chroma access
# -----------------------------------------------------------------------------


def _chroma_collection():
    """Return Chroma collection if it exists, else None (signals fallback)."""
    try:
        import chromadb  # noqa: WPS433
    except ImportError:
        return None

    if not config.CHROMA_DIR.exists():
        return None

    try:
        from app.knowledge.embedding import get_embedding_function
        ef = get_embedding_function()
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        return client.get_collection("regulations", embedding_function=ef)
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Search
# -----------------------------------------------------------------------------


def _fallback_search(query_terms: list[str], k: int) -> list[Regulation]:
    """Title-substring search over reg_index — used only when Chroma is absent.

    The new (JB-본업) reg_index doesn't carry keyword patterns, so we just
    surface every article. The LLM (or the rule engine) discriminates downstream.
    """
    index = _load_index()
    if not index:
        return []
    out: list[Regulation] = []
    for aid, meta in list(index.items())[:k]:
        out.append(
            Regulation(
                article_id=aid,
                title=meta.get("title", aid),
                snippet=_load_full_text(aid),
            )
        )
    return out


def search(query_terms: list[str], k: int = 5) -> list[Regulation]:
    """Find the top-k most relevant regulation chunks for the given query terms."""
    coll = _chroma_collection()
    if coll is None:
        return _fallback_search(query_terms, k)

    joined = " \n ".join(query_terms)
    try:
        res = coll.query(query_texts=[joined], n_results=k)
    except Exception:
        return _fallback_search(query_terms, k)

    documents = res.get("documents", [[]])[0]
    metadatas = res.get("metadatas", [[]])[0]
    ids = res.get("ids", [[]])[0]

    if not documents:
        return _fallback_search(query_terms, k)

    out: list[Regulation] = []
    for doc, meta, _id in zip(documents, metadatas, ids):
        article_id = (meta or {}).get("article_id") or _id
        title = (meta or {}).get("title", article_id)
        out.append(Regulation(article_id=article_id, title=title, snippet=doc))
    return out
