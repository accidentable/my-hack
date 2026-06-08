"""retrieve node: claims → relevant regulation chunks via knowledge store."""
from __future__ import annotations

from app.agent.state import AgentState
from app.knowledge import store


def retrieve_node(state: AgentState) -> AgentState:
    claims = state.get("claims", [])
    query_terms = [c["text_original"] for c in claims] + [c["text_ko"] for c in claims]
    regulations = store.search(query_terms, k=5)
    state["regulations"] = regulations
    state["stage"] = "retrieve"
    return state
