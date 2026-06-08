"""Probe the configured OpenAI models before wiring them into the agent.

Why this exists: we're switching from gpt-4o family to gpt-5.4 family. Newer
model generations sometimes change response semantics (Responses API,
default sampling, Structured-Outputs nuances). This script does three checks
per model so any breakage shows up here — not deep inside the LangGraph run.

Run:
    python -m scripts.check_models

Output is intentionally short — one OK/FAIL line per probe.
"""
from __future__ import annotations

import sys
import traceback

from openai import OpenAI
from pydantic import BaseModel, Field

# Force UTF-8 stdout for Windows consoles (cp949 by default).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app import config


class Ping(BaseModel):
    """Tiny Structured-Outputs target."""
    ok: bool = Field(description="literal true")
    message: str = Field(description="exactly the word: pong")


def _probe(label: str, model: str, client: OpenAI) -> None:
    # ── 1. plain chat completion ────────────────────────────────────────
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly the word: pong"}],
        )
        content = (resp.choices[0].message.content or "").strip()
        print(f"OK   [{label}] {model} chat → {content!r}")
    except Exception as e:
        print(f"FAIL [{label}] {model} chat → {type(e).__name__}: {e}")
        return  # if plain chat fails, structured will too — skip the rest.

    # ── 2. Structured Outputs via beta.parse ────────────────────────────
    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": "Return ok=true and message='pong'."},
                {"role": "user", "content": "ping"},
            ],
            response_format=Ping,
        )
        parsed = completion.choices[0].message.parsed
        print(f"OK   [{label}] {model} structured → {parsed}")
    except Exception as e:
        print(f"FAIL [{label}] {model} structured → {type(e).__name__}: {e}")
        traceback.print_exc(limit=2)

    # ── 3. Vision (only matters for the ingest model) ───────────────────
    if label != "ingest":
        return
    try:
        # 1×1 transparent PNG as data URL — we're only checking the call shape.
        tiny_png = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkAAIAAAUAAeImBZsAAAAASUVORK5CYII="
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What modality is this input? Reply with one word."},
                        {"type": "image_url", "image_url": {"url": tiny_png}},
                    ],
                }
            ],
            max_tokens=20,
        )
        content = (resp.choices[0].message.content or "").strip()
        print(f"OK   [{label}] {model} vision → {content!r}")
    except Exception as e:
        print(f"FAIL [{label}] {model} vision → {type(e).__name__}: {e}")


def main() -> int:
    if config.MOCK_LLM:
        print("COMPLIANCELENS_MOCK_LLM=1 — skipping live probes.")
        return 0

    api_key = config.require_openai_key()
    client = OpenAI(api_key=api_key)

    print(f"assess model = {config.OPENAI_MODEL_ASSESS}")
    print(f"ingest model = {config.OPENAI_MODEL_INGEST}")
    print("-" * 60)

    _probe("assess", config.OPENAI_MODEL_ASSESS, client)
    print()
    _probe("ingest", config.OPENAI_MODEL_INGEST, client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
