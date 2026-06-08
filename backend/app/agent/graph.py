"""LangGraph wiring.

Day 1: ingest → retrieve → assess → verify → generate (straight line).
Day 2: + verify→assess self-correction loop (retry max 2).
Day 3: + generate→[INTERRUPT]→finalize for HITL review, SQLite checkpointer
       so the same thread_id can be resumed across HTTP requests.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from app import config
from app.agent.nodes.assess import assess_node
from app.agent.nodes.finalize import finalize_node
from app.agent.nodes.generate import generate_node
from app.agent.nodes.ingest import ingest_node
from app.agent.nodes.retrieve import retrieve_node
from app.agent.nodes.verify import verify_node
from app.agent.state import AgentState


def route_after_verify(state: AgentState) -> str:
    if state.get("verify_passed", False):
        return "pass"
    if state.get("retry_count", 0) >= config.MAX_VERIFY_RETRIES:
        return "pass"
    return "retry"


def _build_uncompiled() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("assess", assess_node)
    graph.add_node("verify", verify_node)
    graph.add_node("generate", generate_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "retrieve")
    graph.add_edge("retrieve", "assess")
    graph.add_edge("assess", "verify")
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {"pass": "generate", "retry": "assess"},
    )
    # generate → finalize, but with interrupt_before=["finalize"] the graph
    # pauses here so a human can submit review_inputs. Resume by invoking
    # with input=None on the same thread_id.
    graph.add_edge("generate", "finalize")
    graph.add_edge("finalize", END)
    return graph


def build_graph(checkpointer: Optional[BaseCheckpointSaver] = None):
    """Compile the graph.

    - With ``checkpointer``: HITL mode. Pauses before ``finalize`` so review
      can be submitted and resumed via the same thread_id.
    - Without ``checkpointer``: straight-through mode used by ``scripts.run_demo``
      and tests — finalize is skipped (no review_inputs), the CLI just reads
      ``report_markdown`` after the run.
    """
    uncompiled = _build_uncompiled()
    if checkpointer is None:
        # CLI path: end at ``generate``; ``finalize`` is unreachable without
        # human input, so we splice it out by recompiling a minimal variant.
        cli = StateGraph(AgentState)
        cli.add_node("ingest", ingest_node)
        cli.add_node("retrieve", retrieve_node)
        cli.add_node("assess", assess_node)
        cli.add_node("verify", verify_node)
        cli.add_node("generate", generate_node)
        cli.set_entry_point("ingest")
        cli.add_edge("ingest", "retrieve")
        cli.add_edge("retrieve", "assess")
        cli.add_edge("assess", "verify")
        cli.add_conditional_edges(
            "verify", route_after_verify, {"pass": "generate", "retry": "assess"}
        )
        cli.add_edge("generate", END)
        return cli.compile()
    return uncompiled.compile(
        checkpointer=checkpointer,
        interrupt_before=["finalize"],
    )


# -----------------------------------------------------------------------------
# Checkpointer factory — used by the FastAPI lifespan
# -----------------------------------------------------------------------------


def make_sqlite_checkpointer() -> SqliteSaver:
    """Open the project's SQLite checkpoint store.

    Uses ``check_same_thread=False`` so the connection can be shared across
    ASGI workers (Starlette runs sync routes in a threadpool).
    """
    conn = sqlite3.connect(str(config.CHECKPOINT_DB_PATH), check_same_thread=False)
    return SqliteSaver(conn)
