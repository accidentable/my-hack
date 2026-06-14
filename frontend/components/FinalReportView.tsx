"use client";

import { useState } from "react";
import type { Finding, Severity, StateSnapshot } from "@/types";
import { SeverityChip } from "./SeverityChip";
import { findingId } from "./FindingRow";
import { reportUrl } from "@/lib/api";

const SEV_ORDER: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

const LANG_LABEL: Record<string, string> = {
  ko: "한국어",
  vi: "베트남어",
  th: "태국어",
};

function languageLabel(code: string): string {
  if (!code) return "자동 판별";
  return LANG_LABEL[code] ?? code.toUpperCase();
}

/** Date-fns 없이도 가볍게 — 결재 문서 헤더 한 줄에 들어갈 정도. */
function formatNow(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

interface ReviewMap {
  [findingId: string]: { decision: "approve" | "reject"; comment: string };
}

function bucket(findings: Finding[], reviews: ReviewMap) {
  const sorted = [...findings].sort(
    (a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9),
  );
  const confirmed: Finding[] = [];
  const notViolations: Finding[] = [];
  const untouched: Finding[] = [];
  for (const f of sorted) {
    const r = reviews[findingId(f)];
    if (!r) untouched.push(f);
    else if (r.decision === "approve") confirmed.push(f);
    else if (r.decision === "reject") notViolations.push(f);
    else untouched.push(f);
  }
  return { confirmed, notViolations, untouched };
}

// ---------------------------------------------------------------------------
// 소형 UI 파츠
// ---------------------------------------------------------------------------

function CountBadge({
  label,
  count,
  tone,
}: {
  label: string;
  count: number;
  tone: "confirmed" | "rejected" | "untouched";
}) {
  const dot =
    tone === "confirmed"
      ? "bg-sev-high"
      : tone === "rejected"
        ? "bg-sev-pass"
        : "bg-sev-low";
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-bg px-2.5 py-1 text-xs font-medium text-ink">
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden />
      {label}
      <span className="tabular-nums text-muted">{count}</span>
    </span>
  );
}

function LabelValueRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-xs text-soft">{label}</dt>
      <dd className="text-sm leading-relaxed text-ink">{value}</dd>
    </>
  );
}

function FindingCard({
  finding,
  comment,
  decisionTone,
}: {
  finding: Finding;
  comment?: string;
  decisionTone?: "confirmed" | "rejected" | "untouched";
}) {
  const sourceLabel = (() => {
    const merged = finding.merged_sources;
    if (merged && merged.length > 1) return "규칙엔진 + LLM 판정 (이중 적발)";
    return finding.source === "rule" ? "규칙엔진" : "LLM 판정";
  })();

  return (
    <article className="border-b border-line py-5 last:border-b-0">
      <div className="flex items-center gap-3">
        <SeverityChip severity={finding.severity} />
        <span className="text-xs text-muted">{sourceLabel}</span>
        {!finding.verified && (
          <span className="text-xs text-sev-medium">미검증</span>
        )}
      </div>

      <h4 className="mt-2 text-base font-medium leading-snug text-ink">
        {finding.issue}
      </h4>

      <dl className="mt-3 grid grid-cols-[88px_1fr] gap-x-4 gap-y-2">
        <LabelValueRow label="근거 규정" value={finding.regulation_id} />
        {finding.claim_id !== "__document__" && finding.current_text && (
          <LabelValueRow label="현재 표현" value={finding.current_text} />
        )}
        {/* 수정 제안은 위반 확인 항목에서만 의미 있음. 나머지는 생략. */}
        {decisionTone === "confirmed" && (
          <LabelValueRow label="수정 제안" value={finding.suggestion} />
        )}
        {comment && (
          <LabelValueRow label="준법관리자 코멘트" value={comment} />
        )}
      </dl>
    </article>
  );
}

// ---------------------------------------------------------------------------
// 본 컴포넌트
// ---------------------------------------------------------------------------

export function FinalReportView({ state }: { state: StateSnapshot }) {
  const reviewMap: ReviewMap = Object.fromEntries(
    state.review_inputs.map((r) => [r.finding_id, { decision: r.decision, comment: r.comment }]),
  );
  const { confirmed, notViolations, untouched } = bucket(state.findings, reviewMap);

  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!state.final_report_markdown) return;
    try {
      await navigator.clipboard.writeText(state.final_report_markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard API 거부 시 fallback (selection + execCommand는 deprecated). 무시.
    }
  }

  function handlePrint() {
    window.print();
  }

  const reportPrintableId = "final-report-printable";

  return (
    <section
      id={reportPrintableId}
      className="mt-10 border-t border-line pt-8 print:mt-0 print:border-0 print:pt-0"
    >
      {/* 헤더 — 액션 버튼은 인쇄 시 숨김 */}
      <header className="flex flex-wrap items-end justify-between gap-y-3">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold tracking-tight">최종 심의의견서</h2>
          <p className="mt-1 text-xs text-soft tabular-nums">
            심의 ID · {state.thread_id.slice(0, 8)}
            <span className="mx-2 text-line">·</span>
            언어 · {languageLabel(state.language ?? "")}
            <span className="mx-2 text-line">·</span>
            출력 · {formatNow()}
          </p>
        </div>

        <div className="flex items-center gap-2 print:hidden" data-no-print>
          <button
            type="button"
            onClick={handleCopy}
            className="rounded-md border border-line bg-white px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-soft hover:text-ink"
          >
            {copied ? "복사됨" : "복사하기"}
          </button>
          <button
            type="button"
            onClick={handlePrint}
            className="rounded-md border border-line bg-white px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-soft hover:text-ink"
          >
            PDF로 저장
          </button>
          <a
            href={reportUrl(state.thread_id)}
            target="_blank"
            rel="noreferrer"
            className="rounded-md px-3 py-1.5 text-xs font-medium text-muted hover:text-ink"
          >
            마크다운으로 열기
          </a>
        </div>
      </header>

      {/* 요약 배지 */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <CountBadge label="위반 확인" count={confirmed.length} tone="confirmed" />
        <CountBadge label="위반 아님" count={notViolations.length} tone="rejected" />
        <CountBadge label="미검토" count={untouched.length} tone="untouched" />
      </div>

      <p className="mt-3 text-sm text-muted">
        본 의견서는 준법관리자 검토를 반영한 최종 결과입니다. ‘위반 확인’ 항목은 콘텐츠 게시 전 수정이 필요합니다.
      </p>

      {/* 1. 위반 확인 */}
      <section className="mt-8">
        <header className="flex items-baseline gap-3">
          <h3 className="text-base font-semibold text-ink">1. 게시 전 수정 필요</h3>
          <span className="text-xs text-soft tabular-nums">{confirmed.length}건</span>
        </header>
        <div className="mt-2">
          {confirmed.length === 0 ? (
            <p className="py-4 text-sm text-soft">없음</p>
          ) : (
            confirmed.map((f) => (
              <FindingCard
                key={findingId(f)}
                finding={f}
                comment={reviewMap[findingId(f)]?.comment}
                decisionTone="confirmed"
              />
            ))
          )}
        </div>
      </section>

      {/* 2. 위반 아님 */}
      <section className="mt-8">
        <header className="flex items-baseline gap-3">
          <h3 className="text-base font-semibold text-ink">2. 위반 아님으로 결론</h3>
          <span className="text-xs text-soft tabular-nums">{notViolations.length}건</span>
        </header>
        <div className="mt-2">
          {notViolations.length === 0 ? (
            <p className="py-4 text-sm text-soft">없음</p>
          ) : (
            notViolations.map((f) => (
              <FindingCard
                key={findingId(f)}
                finding={f}
                comment={reviewMap[findingId(f)]?.comment}
                decisionTone="rejected"
              />
            ))
          )}
        </div>
      </section>

      {/* 3. 미검토 — 있을 때만 */}
      {untouched.length > 0 && (
        <section className="mt-8">
          <header className="flex items-baseline gap-3">
            <h3 className="text-base font-semibold text-ink">3. 미검토 항목</h3>
            <span className="text-xs text-soft tabular-nums">{untouched.length}건</span>
          </header>
          <div className="mt-2">
            {untouched.map((f) => (
              <FindingCard
                key={findingId(f)}
                finding={f}
                decisionTone="untouched"
              />
            ))}
          </div>
        </section>
      )}
    </section>
  );
}
