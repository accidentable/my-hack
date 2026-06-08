import type { Severity } from "@/types";

const LABEL: Record<Severity, string> = {
  high: "HIGH",
  medium: "MEDIUM",
  low: "LOW",
};

/**
 * 작은 점 + 텍스트 라벨. 이모지 없음. 색은 의미(심각도)에만.
 */
export function SeverityChip({ severity }: { severity: Severity }) {
  const color =
    severity === "high"
      ? "bg-sev-high"
      : severity === "medium"
        ? "bg-sev-medium"
        : "bg-sev-low";

  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium tracking-wide text-ink">
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${color}`} aria-hidden />
      {LABEL[severity]}
    </span>
  );
}
