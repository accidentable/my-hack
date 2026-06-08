"""Shared Chroma embedding function.

Both ingest_regs.py (write) and store.py (read) MUST use the same EF or Chroma
will complain. This single getter is the source of truth.

Strategy:
- Real mode with OPENAI_API_KEY → OpenAI ``text-embedding-3-small`` (cheap, multilingual,
  ~5¢ per million tokens — negligible for 3 regulations).
- Mock mode or missing key → Chroma's bundled ONNX MiniLM (no network beyond
  first-run model fetch). Embedding quality lower but the demo still passes.
"""
from __future__ import annotations

from app import config


def get_embedding_function():
    from chromadb.utils import embedding_functions

    if config.OPENAI_API_KEY and not config.MOCK_LLM:
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=config.OPENAI_API_KEY,
            model_name="text-embedding-3-small",
        )
    return embedding_functions.DefaultEmbeddingFunction()
