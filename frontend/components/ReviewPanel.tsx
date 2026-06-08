"use client";

import { useMemo, useState } from "react";
import type { Finding, Decision, ReviewInput, StateSnapshot } from "@/types";
import { FindingRow, findingId } from "./FindingRow";
import { submitReview } from "@/lib/api";

interface RowState {
  decision: Decision | null;
  comment: string;
}

const SEV_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 };

const SEV_CHIP_LABEL: Record<string, string> = {
  high: "HIGH",
  medium: "MED",
  low: "LOW",
};
const SEV_CHIP_DOT: Record<string, string> = {
  high: "bg-sev-high",
  medium: "bg-sev-medium",
  low: "bg-sev-low",
};

function SeverityCountChips({ counts }: { counts: Record<string, number> }) {
  const order: Array<"high" | "medium" | "low"> = ["high", "medium", "low"];
  const shown = order.filter((k) => (counts[k] ?? 0) > 0);
  if (shown.length === 0) return null;
  return (
    <div className="flex items-center gap-2">
      {shown.map((sev) => (
        <span
          key={sev}
          className="inline-flex items-center gap-1.5 rounded-full bg-bg px-2 py-0.5 text-xs font-medium text-ink"
        >
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${SEV_CHIP_DOT[sev]}`}
            aria-hidden
          />
          {SEV_CHIP_LABEL[sev]} {counts[sev]}
        </span>
      ))}
    </div>
  );
}

export function ReviewPanel({
  state,
  onResolved,
}: {
  state: StateSnapshot;
  onResolved: (next: StateSnapshot) => void;
}) {
  const sorted = useMemo(
    () =>
      [...state.findings].sort(
        (a, b) =>
          (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9),
      ),
    [state.findings],
  );

  const [rows, setRows] = useState<Record<string, RowState>>(() =>
    Object.fromEntries(
      sorted.map((f) => [findingId(f), { decision: null, comment: "" }]),
    ),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const total = sorted.length;
  const decided = Object.values(rows).filter((r) => r.decision !== null).length;
  const allDecided = decided === total;

  async function handleSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      const payload: ReviewInput[] = sorted
        .map((f) => {
          const fid = findingId(f);
          const row = rows[fid];
          if (!row.decision) return null;
          return { finding_id: fid, decision: row.decision, comment: row.comment };
        })
        .filter((x): x is ReviewInput => x !== null);
      const next = await submitReview(state.thread_id, payload);
      onResolved(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  function bulkApprove() {
    setRows((prev) => {
      const out = { ...prev };
      for (const f of sorted) {
        const fid = findingId(f);
        if (!out[fid].decision) {
          out[fid] = { decision: "approve", comment: out[fid].comment };
        }
      }
      return out;
    });
  }

  // 심각도별 카운트 — 헤더 옆 칩으로 보여서 한눈에 들어오도록.
  const sevCounts = sorted.reduce(
    (acc, f) => {
      acc[f.severity] = (acc[f.severity] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <section className="mt-8">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold tracking-tight">위반 소지 검토</h2>
          <SeverityCountChips counts={sevCounts} />
        </div>
        <span className="text-sm text-muted tabular-nums">
          {decided} / {total}
        </span>
      </div>

      {/* findings 목록만 내부 스크롤 — 진행·로그·이 패널의 헤더/푸터가
          한 viewport에 함께 보이도록 하기 위한 처리. */}
      <div className="log-scroll mt-3 max-h-[58vh] overflow-y-auto pr-2">
        {sorted.map((f) => {
          const fid = findingId(f);
          const row = rows[fid];
          return (
            <FindingRow
              key={fid}
              finding={f}
              decision={row.decision}
              comment={row.comment}
              onChange={(next) =>
                setRows((prev) => ({ ...prev, [fid]: next }))
              }
            />
          );
        })}
      </div>

      {error && (
        <p className="mt-4 text-sm text-sev-high">제출 실패 · {error}</p>
      )}

      <div className="mt-8 flex items-center justify-between border-t border-line pt-6">
        <button
          type="button"
          onClick={bulkApprove}
          className="text-sm font-medium text-muted hover:text-ink"
          disabled={submitting}
        >
          미결정 항목 일괄 ‘위반 확인’
        </button>

        <button
          type="button"
          onClick={handleSubmit}
          disabled={!allDecided || submitting}
          className="rounded-md bg-brand px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-hover disabled:bg-soft disabled:text-white"
        >
          {submitting ? "처리 중..." : "검토 제출 · 최종 의견서 생성"}
        </button>
      </div>
    </section>
  );
}
