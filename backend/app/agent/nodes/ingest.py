"""ingest node: image → claims[] via GPT-4o vision."""
from __future__ import annotations

from pathlib import Path

from app.agent.state import AgentState, Claim
from app.llm.client import extract_claims_from_image


def ingest_node(state: AgentState) -> AgentState:
    image_path = Path(state["content_ref"])
    if not image_path.exists():
        raise FileNotFoundError(f"content_ref does not exist: {image_path}")

    resp = extract_claims_from_image(image_path)

    claims: list[Claim] = [
        Claim(
            id=c.id,
            text_original=c.text_original,
            text_ko=c.text_ko,
            modality=c.modality,
        )
        for c in resp.claims
    ]

    state["claims"] = claims
    # If caller didn't pre-set language, take the detected one.
    if not state.get("language"):
        state["language"] = resp.language
    state["stage"] = "ingest"
    return state
