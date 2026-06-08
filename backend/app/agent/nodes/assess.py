"""assess node: rules engine (deterministic) + LLM (contextual) → findings[]."""
from __future__ import annotations

from app.agent.state import AgentState, Finding
from app.llm.client import assess_with_llm
from app.rules import engine as rules_engine


def assess_node(state: AgentState) -> AgentState:
    claims = state.get("claims", [])
    regulations = state.get("regulations", [])

    # (A) Deterministic rules — never miss the non-negotiables.
    rule_findings: list[Finding] = rules_engine.evaluate(claims)

    # (B) LLM — contextual judgment (exaggeration, misleading framing).
    claims_json = [dict(c) for c in claims]
    regs_json = [dict(r) for r in regulations]
    hallucinated_ids = state.get("hallucinated_ids", [])
    llm_resp = assess_with_llm(claims_json, regs_json, hallucinated_ids=hallucinated_ids)

    llm_findings: list[Finding] = []
    for f in llm_resp.findings:
        llm_findings.append(
            Finding(
                claim_id=f.claim_id,
                severity=f.severity,
                source="llm",
                regulation_id=f.regulation_id,
                issue=f.issue,
                current_text=f.current_text,
                suggestion=f.suggestion,
                confidence=f.confidence,
                verified=False,
            )
        )

    state["findings"] = rule_findings + llm_findings
    state["stage"] = "assess"
    return state
