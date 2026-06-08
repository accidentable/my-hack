/**
 * Backend type mirror — keep in sync with `backend/app/agent/state.py` and
 * `backend/app/api/review.py`.
 */

export type Severity = "high" | "medium" | "low";
export type Source = "rule" | "llm";
export type Decision = "approve" | "reject";

export interface Claim {
  id: string;
  text_original: string;
  text_ko: string;
  modality: "image_text" | "caption" | "speech" | "graphic";
}

export interface Finding {
  claim_id: string;
  severity: Severity;
  source: Source;
  regulation_id: string;
  issue: string;
  current_text: string;
  suggestion: string;
  confidence: number;
  verified: boolean;
  /** generate 노드의 dedup이 양쪽(rule+llm) 적발을 병합했을 때 채움. */
  merged_sources?: Source[];
}

export interface ReviewInput {
  finding_id: string;
  decision: Decision;
  comment: string;
}

export interface StateSnapshot {
  thread_id: string;
  stage: string | null;
  verify_passed: boolean | null;
  retry_count: number | null;
  hallucinated_ids: string[];
  claims: Claim[];
  findings: Finding[];
  report_markdown: string | null;
  final_report_markdown: string | null;
  awaiting_review: boolean;
}

export interface StartResponse {
  thread_id: string;
  content_ref: string;
  language: string;
}

/** SSE stage event (one of many) — emitted by backend during graph execution. */
export interface StageEvent {
  stage: string;        // "ingest" | "retrieve" | "assess" | "verify" | "generate" | "__interrupt__" | "start"
  msg: string;
}

/** SSE await_review event — fired once when the graph pauses for HITL. */
export interface AwaitReviewEvent {
  thread_id: string;
  findings_count: number;
  report_preview_len: number;
}

/** One row in the thread-history tab bar. */
export interface ThreadMeta {
  thread_id: string;
  language: string;
  stage: string | null;
  findings_count: number;
  awaiting_review: boolean;
  done: boolean;
  created_at: number;
}
