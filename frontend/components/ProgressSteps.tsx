/**
 * 6단계 진행 표시. 활성/완료/대기를 굵기·점 채움으로만 구분.
 * 가로 라인 위 점 6개 → 절제된 느낌.
 */

const STEPS = [
  { key: "ingest", label: "수집" },
  { key: "retrieve", label: "검색" },
  { key: "assess", label: "판단" },
  { key: "verify", label: "검증" },
  { key: "generate", label: "의견서" },
  { key: "review", label: "사람 검토" },
] as const;

type StepKey = (typeof STEPS)[number]["key"];

const ORDER: Record<StepKey, number> = {
  ingest: 0,
  retrieve: 1,
  assess: 2,
  verify: 3,
  generate: 4,
  review: 5,
};

export function ProgressSteps({
  currentStage,
  awaitingReview,
  done,
}: {
  currentStage: string | null;
  awaitingReview: boolean;
  done: boolean;
}) {
  // Map various backend stage names → step keys.
  const normalized: StepKey | null = (() => {
    if (done) return "review";
    if (awaitingReview) return "review";
    if (!currentStage) return null;
    if (currentStage === "start") return null;
    if (currentStage === "__interrupt__") return "review";
    if (currentStage in ORDER) return currentStage as StepKey;
    return null;
  })();

  const currentIdx = normalized ? ORDER[normalized] : -1;

  return (
    <ol className="flex w-full items-center justify-between gap-2">
      {STEPS.map((s, i) => {
        const isDone = i < currentIdx || (done && i <= ORDER.review);
        const isActive = i === currentIdx && !done;
        const dotColor = isDone
          ? "bg-brand"
          : isActive
            ? "bg-brand"
            : "bg-line";
        const textColor = isDone || isActive ? "text-ink" : "text-soft";
        const weight = isActive ? "font-semibold" : "font-medium";
        return (
          <li key={s.key} className="flex flex-1 flex-col items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${dotColor} ${
                isActive ? "ring-2 ring-brand/30 ring-offset-2 ring-offset-white" : ""
              }`}
              aria-hidden
            />
            <span className={`text-xs ${weight} ${textColor}`}>{s.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
