"use client";

import type { Finding, Severity } from "@/types";
import { findingId } from "./FindingRow";

const SEV_ORDER: Record<Severity, number> = { high: 0, medium: 1, low: 2 };

const SEV_DOT: Record<Severity, string> = {
  high: "bg-sev-high",
  medium: "bg-sev-medium",
  low: "bg-sev-low",
};

const SEV_LABEL: Record<Severity, string> = {
  high: "HIGH",
  medium: "MED",
  low: "LOW",
};

/**
 * 좌측 미니 목차 — 우측 검토 패널의 같은 finding 행으로 스크롤.
 *
 * `scrollIntoView`는 가장 가까운 스크롤 가능 조상(여기선 ReviewPanel의 내부
 * 스크롤 박스)을 자동으로 잡으므로, 우측 패널 안에서 해당 행이 위쪽에
 * 정렬됩니다.
 */
export function FindingsIndex({ findings }: { findings: Finding[] }) {
  if (findings.length === 0) {
    return (
      <p className="text-sm text-soft">아직 결과가 없습니다.</p>
    );
  }

  const sorted = [...findings].sort(
    (a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9),
  );

  function jump(fid: string) {
    const el = document.getElementById(`finding-${fid}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    // 잠깐 강조해서 어디로 이동했는지 알려주는 절제된 시각 신호.
    el.classList.add("ring-1", "ring-brand/40", "rounded");
    window.setTimeout(() => {
      el.classList.remove("ring-1", "ring-brand/40", "rounded");
    }, 900);
  }

  return (
    <nav aria-label="결과 목차" className="space-y-1">
      {sorted.map((f) => {
        const fid = findingId(f);
        return (
          <button
            key={fid}
            type="button"
            onClick={() => jump(fid)}
            className="group flex w-full items-start gap-2.5 rounded px-2 py-1.5 text-left transition-colors hover:bg-bg focus:bg-bg"
          >
            <span
              className={`mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full ${SEV_DOT[f.severity]}`}
              aria-hidden
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm text-ink group-hover:text-brand">
                {f.issue}
              </span>
              <span className="mt-0.5 block truncate text-xs text-soft">
                {SEV_LABEL[f.severity]} · {f.regulation_id}
              </span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
