"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { contentUrl, listThreads } from "@/lib/api";
import type { ThreadMeta } from "@/types";

function shortId(tid: string): string {
  return tid.slice(0, 8);
}

function relativeTime(ts: number): string {
  const now = Date.now() / 1000;
  const diff = Math.max(0, now - ts);
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return `${Math.floor(diff / 86400)}일 전`;
}

function statusLabel(t: ThreadMeta): { text: string; tone: "muted" | "brand" | "ink" } {
  if (t.done) return { text: "완료", tone: "muted" };
  if (t.awaiting_review) return { text: "검토 대기", tone: "brand" };
  return { text: "진행 중", tone: "ink" };
}

/**
 * 헤더 바로 아래 가로 탭. 과거 심의 thread들을 최신순으로 나열.
 * 현재 활성 thread는 아래쪽 brand 색 밑줄로 표시. 항목 클릭 시 라우팅.
 *
 * 데이터는 mount 시 한 번 + 사용자가 다른 탭을 누를 때 자동 갱신
 * (포커스/리프레시 등 더 능동적인 갱신은 데모 범위 밖).
 */
export function ThreadHistoryTabs() {
  const router = useRouter();
  const pathname = usePathname();
  const [threads, setThreads] = useState<ThreadMeta[] | null>(null);

  // Extract the currently active thread_id from /review/[id], if any.
  const activeId = (() => {
    const m = pathname?.match(/^\/review\/([^/]+)/);
    return m ? m[1] : null;
  })();

  async function refresh() {
    try {
      setThreads(await listThreads());
    } catch {
      setThreads([]);
    }
  }

  useEffect(() => {
    refresh();
    // Refresh whenever the route changes (a new upload lands on a new thread).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  if (!threads) {
    return <div className="h-10" aria-hidden />;
  }

  if (threads.length === 0) {
    return (
      <div className="flex h-10 items-center text-xs text-soft">
        과거 심의 기록이 아직 없습니다.
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="log-scroll flex items-stretch gap-1 overflow-x-auto">
        {threads.map((t) => {
          const isActive = t.thread_id === activeId;
          const status = statusLabel(t);
          const toneClass =
            status.tone === "brand"
              ? "text-brand"
              : status.tone === "ink"
                ? "text-ink"
                : "text-muted";
          return (
            <button
              key={t.thread_id}
              type="button"
              onClick={() => router.push(`/review/${t.thread_id}`)}
              className={`group relative flex shrink-0 items-center gap-3 border-b-2 px-3 py-2.5 transition-colors ${
                isActive
                  ? "border-brand"
                  : "border-transparent hover:border-line"
              }`}
            >
              {/* 작은 썸네일 */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={contentUrl(t.thread_id)}
                alt=""
                className="h-8 w-8 shrink-0 rounded border border-line bg-bg object-cover"
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).style.visibility = "hidden";
                }}
              />
              <div className="flex flex-col items-start leading-tight">
                <span
                  className={`text-sm tabular-nums ${
                    isActive ? "font-semibold text-ink" : "text-ink"
                  }`}
                >
                  {shortId(t.thread_id)}
                </span>
                <span className="mt-0.5 flex items-center gap-2 text-xs">
                  <span className="text-soft">{relativeTime(t.created_at)}</span>
                  <span className="text-soft">·</span>
                  <span className="text-muted">{t.findings_count}건</span>
                  <span className="text-soft">·</span>
                  <span className={toneClass}>{status.text}</span>
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
