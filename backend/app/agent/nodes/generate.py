"""generate node: findings → human-readable 심의의견서 (Markdown).

Also performs dedup: findings sharing the same (claim_id, regulation_id) are
merged into a single entry with both sources attributed. Rule + LLM double
hits become "근거 2개" rather than two near-identical bullets.
"""
from __future__ import annotations

from app.agent.state import AgentState, Claim, Finding

_SEVERITY_LABEL = {"high": "🔴 HIGH (확정 위반)", "medium": "🟠 MEDIUM (사람 판단 필요)", "low": "🟡 LOW (권고)"}
_SOURCE_LABEL = {"rule": "규칙엔진", "llm": "LLM 판정"}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _merge_two(a: Finding, b: Finding) -> Finding:
    """Merge two findings that share (claim_id, regulation_id).

    Strategy:
      - severity: take the higher (high > medium > low)
      - confidence: take the higher
      - source: keep the higher-confidence one as primary; record both in
        ``merged_sources`` (a non-schema convenience field consumed by the
        renderer below — _render_finding tolerates either shape).
      - issue: prefer rule-engine's terse issue (more canonical); fall back to LLM
      - current_text: prefer a non-placeholder value
      - suggestion: take the longer of the two (usually more specific)
      - verified: True iff both are verified
    """
    if _SEVERITY_ORDER[a["severity"]] <= _SEVERITY_ORDER[b["severity"]]:
        sev_winner, sev_loser = a, b
    else:
        sev_winner, sev_loser = b, a

    if a["confidence"] >= b["confidence"]:
        conf_winner, conf_loser = a, b
    else:
        conf_winner, conf_loser = b, a

    rule_side = a if a["source"] == "rule" else (b if b["source"] == "rule" else None)
    llm_side = a if a["source"] == "llm" else (b if b["source"] == "llm" else None)

    if a["current_text"] and not a["current_text"].startswith("("):
        current_text = a["current_text"]
    elif b["current_text"] and not b["current_text"].startswith("("):
        current_text = b["current_text"]
    else:
        current_text = a["current_text"] or b["current_text"]

    suggestion = a["suggestion"] if len(a["suggestion"]) >= len(b["suggestion"]) else b["suggestion"]
    issue = (rule_side or conf_winner)["issue"]

    merged: Finding = {
        "claim_id": a["claim_id"],
        "severity": sev_winner["severity"],
        "source": conf_winner["source"],
        "regulation_id": a["regulation_id"],
        "issue": issue,
        "current_text": current_text,
        "suggestion": suggestion,
        "confidence": max(a["confidence"], b["confidence"]),
        "verified": a["verified"] and b["verified"],
    }
    # Non-schema field — sorted distinct list of contributing sources.
    sources = sorted({a["source"], b["source"]})
    merged["merged_sources"] = sources  # type: ignore[typeddict-unknown-key]
    return merged


def _dedup_findings(findings: list[Finding]) -> list[Finding]:
    """Collapse findings sharing the same (claim_id, regulation_id)."""
    by_key: dict[tuple[str, str], Finding] = {}
    for f in findings:
        key = (f["claim_id"], f["regulation_id"])
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = dict(f)  # type: ignore[assignment]
        else:
            by_key[key] = _merge_two(existing, f)
    return list(by_key.values())


def _claim_by_id(claims: list[Claim], cid: str) -> Claim | None:
    for c in claims:
        if c["id"] == cid:
            return c
    return None


def _render_finding(idx: int, f: Finding, claims: list[Claim]) -> str:
    sev = _SEVERITY_LABEL.get(f["severity"], f["severity"])
    merged = f.get("merged_sources")  # type: ignore[typeddict-item]
    if merged and len(merged) > 1:
        src = " + ".join(_SOURCE_LABEL.get(s, s) for s in merged) + " (이중 적발)"
    else:
        src = _SOURCE_LABEL.get(f["source"], f["source"])
    verified_mark = "✅ 검증됨" if f["verified"] else "⚠️ 미검증 (근거 조항 실재 여부 확인 실패)"
    claim = _claim_by_id(claims, f["claim_id"])
    claim_block = ""
    if claim is not None:
        claim_block = (
            f"- **해당 주장 원문**: {claim['text_original']}\n"
            f"- **한국어 병기**: {claim['text_ko']}\n"
        )
    elif f["claim_id"] == "__document__":
        claim_block = "- **적용 범위**: 콘텐츠 전체 (특정 문구가 아닌 누락)\n"

    return (
        f"### {idx}. {sev} — {f['issue']}\n\n"
        f"- **근거 규정**: `{f['regulation_id']}`\n"
        f"- **판정 출처**: {src}\n"
        f"- **검증 상태**: {verified_mark}\n"
        f"- **신뢰도**: {f['confidence']:.2f}\n"
        f"{claim_block}"
        f"- **현재 표현**: {f['current_text']}\n"
        f"- **수정 제안**: {f['suggestion']}\n"
    )


def generate_node(state: AgentState) -> AgentState:
    raw_findings = state.get("findings", [])
    # Dedup by (claim_id, regulation_id). Same (claim, reg) hit by both rule
    # and LLM becomes one finding with both sources attributed.
    findings = _dedup_findings(raw_findings)
    # Persist dedup back into state so finalize / API consumers see one row per pair.
    state["findings"] = findings

    claims = state.get("claims", [])
    language = state.get("language", "")
    content_ref = state.get("content_ref", "")
    verify_passed = state.get("verify_passed", False)

    sorted_findings = sorted(
        findings,
        key=lambda f: (_SEVERITY_ORDER.get(f["severity"], 99), 0 if f["source"] == "rule" else 1),
    )

    high_n = sum(1 for f in findings if f["severity"] == "high")
    med_n = sum(1 for f in findings if f["severity"] == "medium")
    low_n = sum(1 for f in findings if f["severity"] == "low")
    unverified_n = sum(1 for f in findings if not f["verified"])
    retry_count = state.get("retry_count", 0)
    hallucinated_ids = state.get("hallucinated_ids", [])

    body_lines: list[str] = []
    body_lines.append("# ComplianceLens 심의의견서 (1차 자동 검토)")
    body_lines.append("")
    body_lines.append(f"- **콘텐츠**: `{content_ref}`")
    body_lines.append(f"- **언어**: `{language}`")
    body_lines.append(
        f"- **총 위반 소지**: {len(findings)}건 "
        f"(High {high_n} / Medium {med_n} / Low {low_n})"
    )
    body_lines.append(
        f"- **근거 검증**: {'전부 통과' if verify_passed else f'{unverified_n}건 미검증 — 가짜 조항 의심'}"
    )
    if retry_count > 0:
        ids_label = ", ".join(f"`{i}`" for i in hallucinated_ids) if hallucinated_ids else "(없음)"
        body_lines.append(
            f"- **자기수정 루프**: assess 재시도 {retry_count}회 · "
            f"환각으로 폐기된 조항: {ids_label}"
        )
    body_lines.append("")
    body_lines.append("> 본 의견서는 AI Agent의 1차 검토 결과이며, "
                      "최종 결정은 준법관리자의 검토·승인을 거칩니다.")
    body_lines.append("")

    body_lines.append("## 추출된 주장 (Claims)")
    if not claims:
        body_lines.append("_(추출된 주장 없음)_")
    else:
        for c in claims:
            body_lines.append(f"- `{c['id']}` ({c['modality']}) — "
                              f"**원문**: {c['text_original']} / **한국어**: {c['text_ko']}")
    body_lines.append("")

    body_lines.append("## 위반 소지 (Findings)")
    if not sorted_findings:
        body_lines.append("_위반 소지가 발견되지 않았습니다._")
    else:
        for i, f in enumerate(sorted_findings, start=1):
            body_lines.append(_render_finding(i, f, claims))

    report = "\n".join(body_lines).rstrip() + "\n"
    state["report_markdown"] = report
    state["stage"] = "generate"
    return state
