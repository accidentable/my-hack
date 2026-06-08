"""verify node: catch hallucinated regulation_ids and trigger self-correction.

Each finding claims to be grounded in some ``regulation_id``. We look that id
up in the regulation index (``reg_index.json``). If it doesn't exist, the
finding is treated as hallucinated.

Two outcomes:

- **All verified** → ``verify_passed=True``. Graph proceeds to ``generate``.
- **Some hallucinated** → ``verify_passed=False``. Two sub-cases:

    a) ``retry_count < MAX_VERIFY_RETRIES``:
       Drop the hallucinated findings (so they don't pollute the next pass),
       record their ids in ``hallucinated_ids`` (so ``assess`` knows what NOT
       to cite), bump ``retry_count``, and the graph's conditional edge will
       loop back to ``assess``.

    b) Retry budget exhausted:
       Keep the unverified findings but halve their confidence — let the human
       reviewer see them with a clear warning. ``verify_passed`` stays False
       so the report header reflects reality.

Rule-engine findings are trivially verified (their regulation_id comes from
rules.yaml, which only references real articles). The hallucination risk is
on the LLM side.
"""
from __future__ import annotations

from app import config
from app.agent.state import AgentState, Finding
from app.knowledge import store


def verify_node(state: AgentState) -> AgentState:
    findings = state.get("findings", [])
    retry_count = state.get("retry_count", 0)

    verified_ok: list[Finding] = []
    hallucinated: list[Finding] = []

    for f in findings:
        if store.article_exists(f["regulation_id"]):
            verified_ok.append(Finding(**{**f, "verified": True}))
        else:
            hallucinated.append(f)

    if not hallucinated:
        state["findings"] = verified_ok
        state["verify_passed"] = True
        # Preserve any historically-rejected ids so the report can show that
        # self-correction actually ran. Don't overwrite to [].
        state["hallucinated_ids"] = state.get("hallucinated_ids", [])
        state["retry_count"] = retry_count
        state["stage"] = "verify"
        return state

    hallucinated_ids = sorted({f["regulation_id"] for f in hallucinated})

    if retry_count < config.MAX_VERIFY_RETRIES:
        # Trigger self-correction: drop bogus findings, accumulate forbidden ids,
        # bump the retry counter. The graph edge re-runs assess.
        prior = state.get("hallucinated_ids", [])
        merged = sorted(set(prior) | set(hallucinated_ids))
        state["findings"] = verified_ok
        state["verify_passed"] = False
        state["hallucinated_ids"] = merged
        state["retry_count"] = retry_count + 1
        state["stage"] = "verify"
        return state

    # Retry budget exhausted — keep the unverified findings, but cut their
    # confidence in half so generate/UI surfaces the doubt prominently.
    softened = [
        Finding(
            **{**f, "verified": False, "confidence": round(f["confidence"] * 0.5, 2)}
        )
        for f in hallucinated
    ]
    state["findings"] = verified_ok + softened
    state["verify_passed"] = False
    state["hallucinated_ids"] = hallucinated_ids
    state["retry_count"] = retry_count
    state["stage"] = "verify"
    return state
