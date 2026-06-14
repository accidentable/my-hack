"use client";

import { useState } from "react";
import type { ReactNode } from "react";

/** 한 줄의 로그 — 부모(page)가 SSE stage 이벤트를 모아 전달. */
export interface LogEntry {
  stage: string;
  msg: string;
  details?: Record<string, unknown> | null;
}

const STAGE_LABEL: Record<string, string> = {
  start: "시작",
  ingest: "주장 추출",
  retrieve: "규정 검색",
  assess: "위반 판정",
  verify: "근거 검증",
  generate: "의견서 생성",
  finalize: "최종본 생성",
  __interrupt__: "사람 검토 대기",
  snapshot: "복원",
};

// ---------------------------------------------------------------------------
// 작은 UI 파츠 — 토스 톤 (라벨-값, 점, 잔잔한 배경)
// ---------------------------------------------------------------------------

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <>
      <dt className="text-xs text-soft">{label}</dt>
      <dd className="text-xs text-ink">{value}</dd>
    </>
  );
}

function Pill({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "warn" | "ok" }) {
  const dot =
    tone === "warn" ? "bg-sev-medium" : tone === "ok" ? "bg-sev-pass" : "bg-soft";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-bg px-2 py-0.5 text-xs text-ink">
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden />
      {children}
    </span>
  );
}

// ---------------------------------------------------------------------------
// stage별 details 렌더링
// ---------------------------------------------------------------------------

function IngestDetails({ d }: { d: Record<string, unknown> }) {
  const claims = (d.claims as Array<Record<string, string>>) ?? [];
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-[88px_1fr] gap-x-4 gap-y-1.5">
        <DetailRow label="주 언어" value={String(d.language || "—")} />
        <DetailRow label="모델" value={String(d.model || "—")} />
        <DetailRow label="추출 수" value={`${claims.length}건`} />
      </dl>
      {claims.length > 0 && (
        <ul className="space-y-1.5">
          {claims.map((c) => (
            <li key={c.id} className="flex items-start gap-2 text-xs">
              <span className="mt-0.5 inline-flex shrink-0 rounded bg-bg px-1.5 py-0.5 text-[10px] font-medium text-muted">
                {c.id}
              </span>
              <span className="shrink-0 text-soft">{c.modality}</span>
              <span className="min-w-0 text-ink">
                {c.text_original}
                {c.text_ko && c.text_ko !== c.text_original && (
                  <span className="text-muted"> · {c.text_ko}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RetrieveDetails({ d }: { d: Record<string, unknown> }) {
  const regs = (d.regulations as Array<Record<string, string>>) ?? [];
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-[88px_1fr] gap-x-4 gap-y-1.5">
        <DetailRow label="검색 백엔드" value={String(d.backend || "—")} />
        <DetailRow label="결과" value={`${regs.length}건 (top-k)`} />
      </dl>
      {regs.length > 0 && (
        <ul className="space-y-1.5">
          {regs.map((r, i) => (
            <li key={i} className="flex items-start gap-2 text-xs">
              <span className="text-soft tabular-nums">{i + 1}.</span>
              <code className="shrink-0 rounded bg-bg px-1.5 py-0.5 text-[11px] text-ink">
                {r.article_id}
              </code>
              <span className="min-w-0 text-muted">{r.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AssessDetails({ d }: { d: Record<string, unknown> }) {
  const by = (d.by_source as Record<string, number>) ?? { rule: 0, llm: 0 };
  const retry = (d.retry_attempt as number) ?? 0;
  return (
    <div className="space-y-2">
      <dl className="grid grid-cols-[88px_1fr] gap-x-4 gap-y-1.5">
        <DetailRow label="총 발견" value={`${d.total}건`} />
        <DetailRow
          label="발견 출처"
          value={
            <span className="flex items-center gap-1.5">
              <Pill>규칙엔진 {by.rule}</Pill>
              <Pill>LLM {by.llm}</Pill>
            </span>
          }
        />
        <DetailRow
          label="시도"
          value={retry === 0 ? "1차 판정" : `자기수정 ${retry}차 (이전 환각 ID 회피)`}
        />
        <DetailRow label="엔진" value={String(d.model || "—")} />
      </dl>
    </div>
  );
}

function VerifyDetails({ d }: { d: Record<string, unknown> }) {
  const passed = Boolean(d.passed);
  const hallucinated = (d.hallucinated_ids as string[]) ?? [];
  return (
    <div className="space-y-2">
      <dl className="grid grid-cols-[88px_1fr] gap-x-4 gap-y-1.5">
        <DetailRow
          label="결과"
          value={
            passed ? (
              <Pill tone="ok">근거 조항 전부 실재 확인</Pill>
            ) : (
              <Pill tone="warn">환각 의심 — 폐기 후 재판정</Pill>
            )
          }
        />
        <DetailRow label="검증 통과" value={`${d.verified_count ?? 0}건`} />
        <DetailRow label="retry_count" value={String(d.retry_count ?? 0)} />
        <DetailRow label="다음 단계" value={String(d.next || "—")} />
      </dl>
      {hallucinated.length > 0 && (
        <div>
          <p className="mb-1 text-xs text-soft">폐기된 article_id (인덱스 미존재)</p>
          <ul className="space-y-1">
            {hallucinated.map((id) => (
              <li key={id}>
                <code className="rounded bg-bg px-1.5 py-0.5 text-[11px] text-sev-medium">
                  {id}
                </code>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] leading-relaxed text-soft">
            인덱스에 존재하지 않는 article_id가 인용되어 자기수정 루프로 진입했습니다.
            (`store.article_exists()` 결과 False)
          </p>
        </div>
      )}
    </div>
  );
}

function GenerateDetails({ d }: { d: Record<string, unknown> }) {
  const bySev = (d.by_severity as Record<string, number>) ?? { high: 0, medium: 0, low: 0 };
  return (
    <div className="space-y-2">
      <dl className="grid grid-cols-[88px_1fr] gap-x-4 gap-y-1.5">
        <DetailRow label="dedup 후" value={`${d.findings_after_dedup ?? 0}건`} />
        <DetailRow
          label="심각도"
          value={
            <span className="flex items-center gap-1.5">
              <Pill>HIGH {bySev.high}</Pill>
              <Pill>MED {bySev.medium}</Pill>
              {bySev.low > 0 && <Pill>LOW {bySev.low}</Pill>}
            </span>
          }
        />
        <DetailRow label="보고서 길이" value={`${d.report_chars ?? 0}자`} />
      </dl>
    </div>
  );
}

function DetailsBody({ stage, details }: { stage: string; details: Record<string, unknown> }) {
  if (stage === "ingest") return <IngestDetails d={details} />;
  if (stage === "retrieve") return <RetrieveDetails d={details} />;
  if (stage === "assess") return <AssessDetails d={details} />;
  if (stage === "verify") return <VerifyDetails d={details} />;
  if (stage === "generate") return <GenerateDetails d={details} />;
  // 기타 노드 (snapshot, finalize 등) — 키-값 일반 렌더
  return (
    <dl className="grid grid-cols-[88px_1fr] gap-x-4 gap-y-1.5">
      {Object.entries(details).map(([k, v]) => (
        <DetailRow key={k} label={k} value={typeof v === "object" ? JSON.stringify(v) : String(v)} />
      ))}
    </dl>
  );
}

// ---------------------------------------------------------------------------
// 한 로그 라인 + 토글
// ---------------------------------------------------------------------------

function LogLine({ entry }: { entry: LogEntry }) {
  const [open, setOpen] = useState(false);
  const canExpand = entry.details && Object.keys(entry.details).length > 0;
  const isRetry = entry.stage === "verify" && entry.msg.includes("retry");

  return (
    <li className="border-l border-line pl-3">
      <button
        type="button"
        onClick={() => canExpand && setOpen((v) => !v)}
        className={`flex w-full items-start gap-3 py-1.5 text-left text-sm ${
          canExpand ? "cursor-pointer" : "cursor-default"
        }`}
        aria-expanded={open}
      >
        <span
          className={`mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
            isRetry ? "bg-sev-medium" : "bg-line"
          }`}
          aria-hidden
        />
        <span className="min-w-0 flex-1">
          <span className="font-medium text-ink">
            {STAGE_LABEL[entry.stage] ?? entry.stage}
          </span>
          <span className="ml-2 text-muted">{entry.msg}</span>
          {isRetry && <span className="ml-2 text-xs text-sev-medium">자기수정</span>}
        </span>
        {canExpand && (
          <span
            className={`mt-0.5 shrink-0 text-xs text-soft transition-transform ${
              open ? "rotate-90" : ""
            }`}
            aria-hidden
          >
            ›
          </span>
        )}
      </button>
      {open && entry.details && (
        <div className="mb-3 mt-1.5 rounded-md bg-bg px-3 py-3">
          <DetailsBody stage={entry.stage} details={entry.details} />
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// 본 컴포넌트
// ---------------------------------------------------------------------------

export function AgentLog({
  logs,
  emptyText = "에이전트 시작 대기 중...",
  maxHeightClass = "max-h-[40vh]",
}: {
  logs: LogEntry[];
  emptyText?: string;
  maxHeightClass?: string;
}) {
  return (
    <ul className={`log-scroll space-y-0 overflow-y-auto pr-2 ${maxHeightClass}`}>
      {logs.length === 0 ? (
        <li className="text-sm text-soft">{emptyText}</li>
      ) : (
        logs.map((l, i) => <LogLine key={i} entry={l} />)
      )}
    </ul>
  );
}
