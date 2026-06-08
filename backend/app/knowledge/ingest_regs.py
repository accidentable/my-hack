"""Read data/regulations/*.txt into Chroma with a consistent embedding function.

Usage:
    python -m app.knowledge.ingest_regs

The collection is dropped & rebuilt each run (small dataset, hackathon-pragmatic).
"""
from __future__ import annotations

import json
import sys

from app import config
from app.knowledge.embedding import get_embedding_function


def main() -> int:
    try:
        import chromadb
    except ImportError:
        print("chromadb not installed — `pip install -r requirements.txt`", file=sys.stderr)
        return 1

    reg_files = sorted(config.REGULATIONS_DIR.glob("*.txt"))
    if not reg_files:
        print(f"No regulation files in {config.REGULATIONS_DIR}", file=sys.stderr)
        return 1

    if not config.REG_INDEX_PATH.exists():
        print(f"Missing reg_index at {config.REG_INDEX_PATH}", file=sys.stderr)
        return 1

    with config.REG_INDEX_PATH.open("r", encoding="utf-8") as f:
        index = json.load(f)

    config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    ef = get_embedding_function()

    try:
        client.delete_collection("regulations")
    except Exception:
        pass
    coll = client.create_collection("regulations", embedding_function=ef)

    # Walk the index (not the directory) — the index defines which article_id
    # corresponds to which file. File names contain underscores; article_ids
    # contain dashes, so they don't match path stems anymore.
    docs: list[str] = []
    metas: list[dict] = []
    ids: list[str] = []
    for article_id, meta in index.items():
        filename = meta.get("file") or meta.get("source_file")
        if not filename:
            print(f"skip {article_id}: no file in index", file=sys.stderr)
            continue
        src = config.REGULATIONS_DIR / filename
        if not src.exists():
            # Try as path relative to backend root (legacy source_file form).
            alt = config.BACKEND_ROOT / filename
            if alt.exists():
                src = alt
            else:
                print(f"skip {article_id}: missing {src}", file=sys.stderr)
                continue
        body = src.read_text(encoding="utf-8")
        # Prepend the title so short semantic queries still hit.
        enriched = f"{meta.get('title', article_id)}\n\n{body}"
        docs.append(enriched)
        metas.append(
            {
                "article_id": article_id,
                "title": meta.get("title", article_id),
                "scope": meta.get("scope", ""),
            }
        )
        ids.append(article_id)

    coll.add(documents=docs, metadatas=metas, ids=ids)
    ef_name = type(ef).__name__
    print(f"Ingested {len(docs)} regulations into {config.CHROMA_DIR} via {ef_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
