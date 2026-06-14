"""finalize node: 사람 검토 결과를 반영해 '수정사항 정리본'을 다시 출력.

예선 범위: 검토 의견 **취합·정리만** 한다. 학습/재학습은 본선 고도화.

입력:
  - state["findings"]        — generate에서 dedup된 발견 목록
  - state["review_inputs"]   — 항목별 {finding_id, decision, comment}
                               finding_id 표준 형식: "{claim_id}:{regulation_id}"
출력:
  - state["final_report_markdown"] — 최종 의견서 (Markdown)
"""
from __future__ import annotations

from app.agent.state import AgentState, Finding, ReviewInput

_SEVERITY_LABEL = {
    "high": "🔴 HIGH",
    "medium": "🟠 MEDIUM",
    "low": "🟡 LOW",
}
_DECISION_LABEL = {
    "approve": "위반 확인",
    "reject": "위반 아님",
}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _finding_id(f: Finding) -> str:
    return f"{f['claim_id']}:{f['regulation_id']}"


def _index_reviews(reviews: list[ReviewInput]) -> dict[str, ReviewInput]:
    return {r["finding_id"]: r for r in reviews}


def finalize_node(state: AgentState) -> AgentState:
    findings = state.get("findings", [])
    review_inputs_list = state.get("review_inputs", [])
    reviews = _index_reviews(review_inputs_list)
    content_ref = state.get("content_ref", "")
    language = state.get("language", "")

    # decision 값은 API 계약상 approve/reject 그대로지만, 의미는
    #   approve = "위반 확인" (사람이 위반 판정에 동의)
    #   reject  = "위반 아님" (사람이 위반 판정을 거부)
    confirmed = [f for f in findings if reviews.get(_finding_id(f), {}).get("decision") == "approve"]
    not_violations = [f for f in findings if reviews.get(_finding_id(f), {}).get("decision") == "reject"]
    untouched = [f for f in findings if _finding_id(f) not in reviews]

    sort_key = lambda f: _SEVERITY_ORDER.get(f["severity"], 99)
    confirmed.sort(key=sort_key)
    not_violations.sort(key=sort_key)
    untouched.sort(key=sort_key)

    lines: list[str] = []
    lines.append("# ComplianceLens 심의의견서 (최종본 · 사람 검토 반영)")
    lines.append("")
    lines.append(f"- **콘텐츠**: `{content_ref}`")
    lines.append(f"- **언어**: `{language}`")
    lines.append(
        f"- **검토 결과**: 위반 확인 {len(confirmed)}건 · 위반 아님 {len(not_violations)}건 · 미검토 {len(untouched)}건"
    )
    lines.append("")
    lines.append("> 본 의견서는 준법관리자의 검토를 반영한 최종 결과입니다. "
                 "‘위반 확인’ 항목은 콘텐츠 게시 전 수정이 필요합니다.")
    lines.append("")

    # ── 위반 확인 항목: 게시 전 수정 필요 ─────────────────────────
    lines.append("## 1. 게시 전 수정 필요 (위반 확인 항목)")
    if not confirmed:
        lines.append("_없음_")
    else:
        for i, f in enumerate(confirmed, 1):
            fid = _finding_id(f)
            sev = _SEVERITY_LABEL.get(f["severity"], f["severity"])
            comment = reviews[fid].get("comment", "").strip()
            lines.append(f"### {i}. {sev} — {f['issue']}")
            lines.append("")
            lines.append(f"- **근거 규정**: `{f['regulation_id']}`")
            lines.append(f"- **현재 표현**: {f['current_text']}")
            lines.append(f"- **수정 제안**: {f['suggestion']}")
            if comment:
                lines.append(f"- **준법관리자 코멘트**: {comment}")
            lines.append("")

    # ── 위반 아님으로 결론된 항목 ───────────────────────────────────
    lines.append("## 2. 위반 아님으로 결론된 항목")
    if not not_violations:
        lines.append("_없음_")
    else:
        for i, f in enumerate(not_violations, 1):
            fid = _finding_id(f)
            sev = _SEVERITY_LABEL.get(f["severity"], f["severity"])
            comment = reviews[fid].get("comment", "").strip()
            lines.append(f"- **{i}.** {sev} `{f['regulation_id']}` — {f['issue']}")
            if comment:
                lines.append(f"   - 위반 아님으로 본 사유: {comment}")

    # ── 미검토(검토 시간 부족 등) ──────────────────────────────────
    if untouched:
        lines.append("")
        lines.append("## 3. 미검토 항목 (사람 검토 누락)")
        for i, f in enumerate(untouched, 1):
            sev = _SEVERITY_LABEL.get(f["severity"], f["severity"])
            lines.append(f"- **{i}.** {sev} `{f['regulation_id']}` — {f['issue']}")

    final = "\n".join(lines).rstrip() + "\n"
    state["final_report_markdown"] = final
    # Echo review_inputs back so it survives in the checkpointed state and is
    # visible to the API snapshot (FinalReportView reads from there to render
    # structured cards instead of parsing markdown).
    state["review_inputs"] = review_inputs_list
    state["stage"] = "done"
    return state
