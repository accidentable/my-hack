"use client";

import { useState } from "react";
import type { Finding, Decision } from "@/types";
import { SeverityChip } from "./SeverityChip";

const SOURCE_LABEL: Record<string, string> = {
  rule: "규칙엔진",
  llm: "LLM 판정",
};

function sourceText(f: Finding): string {
  const merged = f.merged_sources;
  if (merged && merged.length > 1) {
    return merged.map((s) => SOURCE_LABEL[s] ?? s).join(" + ") + " · 이중 적발";
  }
  return SOURCE_LABEL[f.source] ?? f.source;
}

export function findingId(f: Finding): string {
  return `${f.claim_id}:${f.regulation_id}`;
}

/**
 * 한 위반 항목의 단일 행. 결정/코멘트는 부모 상태에서 관리.
 */
export function FindingRow({
  finding,
  decision,
  comment,
  onChange,
}: {
  finding: Finding;
  decision: Decision | null;
  comment: string;
  onChange: (next: { decision: Decision | null; comment: string }) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isDocument = finding.claim_id === "__document__";

  return (
    <div
      id={`finding-${findingId(finding)}`}
      className="scroll-mt-2 border-b border-line py-5 last:border-b-0"
    >
      <div className="flex items-start justify-between gap-6">
        {/* 본문 */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <SeverityChip severity={finding.severity} />
            <span className="text-xs text-muted">{sourceText(finding)}</span>
            {!finding.verified && (
              <span className="text-xs text-sev-medium">미검증</span>
            )}
          </div>

          <p className="mt-2 text-base font-medium leading-snug text-ink">
            {finding.issue}
          </p>

          {!isDocument && (
            <p className="mt-1.5 text-sm text-muted">
              <span className="text-soft">현재 표현 · </span>
              <span className="text-ink">{finding.current_text}</span>
            </p>
          )}

          {expanded && (
            <div className="mt-3 space-y-2 text-sm">
              <p>
                <span className="text-soft">근거 규정 · </span>
                <code className="rounded bg-bg px-1.5 py-0.5 text-[13px] text-ink">
                  {finding.regulation_id}
                </code>
              </p>
              <p>
                <span className="text-soft">수정 제안 · </span>
                <span className="text-ink">{finding.suggestion}</span>
              </p>
              <p>
                <span className="text-soft">신뢰도 · </span>
                <span className="text-ink">{(finding.confidence * 100).toFixed(0)}%</span>
              </p>
            </div>
          )}

          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-3 text-xs font-medium text-brand hover:text-brand-hover"
          >
            {expanded ? "접기" : "근거·수정안 보기"}
          </button>
        </div>

        {/* 결정 토글 */}
        <div className="flex shrink-0 flex-col items-end gap-2">
          <div className="inline-flex rounded-md border border-line overflow-hidden">
            <button
              type="button"
              onClick={() =>
                onChange({
                  decision: decision === "approve" ? null : "approve",
                  comment,
                })
              }
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                decision === "approve"
                  ? "bg-brand text-white"
                  : "bg-white text-muted hover:text-ink"
              }`}
            >
              위반 확인
            </button>
            <button
              type="button"
              onClick={() =>
                onChange({
                  decision: decision === "reject" ? null : "reject",
                  comment,
                })
              }
              className={`border-l border-line px-3 py-1.5 text-xs font-medium transition-colors ${
                decision === "reject"
                  ? "bg-ink text-white"
                  : "bg-white text-muted hover:text-ink"
              }`}
            >
              위반 아님
            </button>
          </div>
        </div>
      </div>

      {/* 코멘트 — 결정 후 노출 */}
      {decision && (
        <div className="mt-3">
          <input
            type="text"
            value={comment}
            onChange={(e) => onChange({ decision, comment: e.target.value })}
            placeholder={
              decision === "approve" ? "수정 권고 메모 (선택)" : "위반 아님으로 본 사유"
            }
            className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-soft focus:border-brand focus:outline-none"
          />
        </div>
      )}
    </div>
  );
}
