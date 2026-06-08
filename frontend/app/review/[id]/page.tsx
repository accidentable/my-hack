"use client";

import { useEffect, useState } from "react";
import { contentUrl, getState, reportUrl, subscribeStream } from "@/lib/api";
import type { StageEvent, StateSnapshot } from "@/types";
import { ReviewPanel } from "@/components/ReviewPanel";
import { OriginalPreview } from "@/components/OriginalPreview";

interface LogEntry {
  stage: string;
  msg: string;
}

const STAGE_LABEL: Record<string, string> = {
  start: "시작",
  ingest: "주장 추출",
  retrieve: "규정 검색",
  assess: "위반 판정",
  verify: "근거 검증",
  generate: "의견서 생성",
  __interrupt__: "사람 검토 대기",
  snapshot: "복원",
};

export default function ReviewPage({ params }: { params: { id: string } }) {
  const threadId = params.id;
  const [state, setState] = useState<StateSnapshot | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [streamError, setStreamError] = useState<string | null>(null);

  // Subscribe to the SSE stream. In React Strict Mode (Next dev) this effect
  // mounts→cleanup→mount once; each cycle opens its own EventSource and the
  // cleanup closes it, which is correct. On the second mount the backend
  // returns the replay path (existing state → snapshot + await_review), so
  // even the brief duplicate is harmless.
  useEffect(() => {
    let cancelled = false;

    const unsub = subscribeStream(threadId, {
      onStage: (e: StageEvent) => {
        if (cancelled) return;
        setLogs((prev) => [...prev, { stage: e.stage, msg: e.msg }]);
      },
      onSnapshot: (snap) => {
        // Backend's "replay" path — this thread has already run, so per-stage
        // frames aren't re-emitted. Populate state directly and leave a single
        // hint in the log so the user knows where the data came from.
        if (cancelled) return;
        setState(snap);
        setLogs((prev) => (prev.length > 0 ? prev : [
          { stage: "snapshot", msg: "이전 진행 결과를 복원했습니다" },
        ]));
      },
      onAwaitReview: async () => {
        if (cancelled) return;
        try {
          const snap = await getState(threadId);
          if (!cancelled) setState(snap);
        } catch (err) {
          if (!cancelled) setStreamError(String(err));
        }
      },
      onDone: async () => {
        if (cancelled) return;
        try {
          const snap = await getState(threadId);
          if (!cancelled) setState(snap);
        } catch {
          /* state may not exist yet — ignore */
        }
      },
      onError: (msg) => {
        if (!cancelled) setStreamError(msg);
      },
    });

    return () => {
      cancelled = true;
      unsub();
    };
  }, [threadId]);

  const stage = state?.stage ?? logs[logs.length - 1]?.stage ?? null;
  const awaiting = state?.awaiting_review ?? false;
  const finalized = !!state?.final_report_markdown;

  // 상태 신호 — 헤더 우측에 표시. 절제된 pulse는 검토 필요 시에만.
  const statusBadge = (() => {
    if (finalized) {
      return (
        <span className="inline-flex items-center gap-2 text-sm text-muted">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-sev-pass" aria-hidden />
          완료
        </span>
      );
    }
    if (awaiting) {
      return (
        <span className="inline-flex items-center gap-2 text-sm font-medium text-brand">
          <span className="relative inline-flex h-2 w-2" aria-hidden>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-brand" />
          </span>
          검토 필요
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-2 text-sm text-muted">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-soft" aria-hidden />
        진행 중
      </span>
    );
  })();

  return (
    <div>
      {/* 페이지 헤더 — 한 줄로 압축. 부연 설명은 제거. */}
      <header className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold tracking-tight">심의 진행</h1>
          {statusBadge}
        </div>
        <span className="text-xs text-soft tabular-nums">
          thread · {threadId.slice(0, 8)}
        </span>
      </header>

      {/* 좌우 분할: lg 이상에서 5:7. 좁아지면 자연스럽게 세로 스택. */}
      <div className="grid grid-cols-1 gap-10 lg:grid-cols-12">
        {/* 좌측 · 원본 (sticky) */}
        <aside className="lg:col-span-5">
          <div className="lg:sticky lg:top-8">
            <h2 className="mb-3 text-sm font-medium text-muted">심의 대상 원본</h2>
            <OriginalPreview url={contentUrl(threadId)} />
          </div>
        </aside>

        {/* 우측 · 로그 + 검토 + 결과 (상단 진행 바는 제거 — 로그가 같은 정보를 더 자세히 줌) */}
        <div className="lg:col-span-7">
          {/* 진행 로그 */}
          <section>
            <h2 className="text-sm font-medium text-muted">에이전트 로그</h2>
            <ul className="log-scroll mt-3 max-h-32 space-y-2 overflow-y-auto pr-2">
              {logs.map((l, i) => {
                const isRetry =
                  l.stage === "verify" && l.msg.includes("retry");
                return (
                  <li key={i} className="flex items-start gap-3 text-sm">
                    <span className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-line" />
                    <div className="min-w-0">
                      <span className="font-medium text-ink">
                        {STAGE_LABEL[l.stage] ?? l.stage}
                      </span>
                      <span className="ml-2 text-muted">{l.msg}</span>
                      {isRetry && (
                        <span className="ml-2 text-xs text-sev-medium">자기수정</span>
                      )}
                    </div>
                  </li>
                );
              })}
              {logs.length === 0 && (
                <li className="text-sm text-soft">에이전트 시작 대기 중...</li>
              )}
            </ul>
            {streamError && (
              <p className="mt-3 text-sm text-sev-high">스트림 오류 · {streamError}</p>
            )}
          </section>

          {/* 검토 패널 */}
          {state && state.awaiting_review && !finalized && (
            <ReviewPanel state={state} onResolved={(next) => setState(next)} />
          )}

          {/* 최종 결과 */}
          {finalized && state && (
            <section className="mt-10 border-t border-line pt-8">
              <div className="flex items-end justify-between">
                <div>
                  <h2 className="text-xl font-semibold tracking-tight">최종 심의의견서</h2>
                  <p className="mt-1 text-sm text-muted">
                    준법관리자 검토를 반영한 결과입니다.
                  </p>
                </div>
                <a
                  href={reportUrl(threadId)}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-brand hover:text-brand-hover"
                >
                  마크다운으로 열기
                </a>
              </div>
              <pre className="log-scroll mt-6 max-h-[55vh] overflow-y-auto whitespace-pre-wrap rounded-md border border-line bg-bg px-5 py-5 font-sans text-sm leading-relaxed text-ink">
                {state.final_report_markdown}
              </pre>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
