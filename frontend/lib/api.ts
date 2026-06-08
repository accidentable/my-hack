import type {
  AwaitReviewEvent,
  ReviewInput,
  StageEvent,
  StartResponse,
  StateSnapshot,
  ThreadMeta,
} from "@/types";

const BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function listThreads(): Promise<ThreadMeta[]> {
  const r = await fetch(`${BASE}/api/review/list`);
  if (!r.ok) throw new Error(`listThreads failed: ${r.status}`);
  return r.json();
}

export async function uploadCard(file: File, language = "vi"): Promise<StartResponse> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("language", language);
  const r = await fetch(`${BASE}/api/review`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(`upload failed: ${r.status}`);
  return r.json();
}

export async function getState(threadId: string): Promise<StateSnapshot> {
  const r = await fetch(`${BASE}/api/review/${threadId}`);
  if (!r.ok) throw new Error(`getState failed: ${r.status}`);
  return r.json();
}

export async function submitReview(
  threadId: string,
  reviewInputs: ReviewInput[],
): Promise<StateSnapshot> {
  const r = await fetch(`${BASE}/api/review/${threadId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ review_inputs: reviewInputs }),
  });
  if (!r.ok) throw new Error(`resume failed: ${r.status}`);
  return r.json();
}

export function streamUrl(threadId: string): string {
  return `${BASE}/api/review/${threadId}/stream`;
}

export function reportUrl(threadId: string): string {
  return `${BASE}/api/review/${threadId}/report`;
}

export function contentUrl(threadId: string): string {
  return `${BASE}/api/review/${threadId}/content`;
}

/** Cheap "is this a video?" check using URL extension or File mime-type. */
export function isVideoSource(src: { url?: string; file?: File }): boolean {
  if (src.file) return src.file.type.startsWith("video/");
  if (src.url) {
    const lower = src.url.toLowerCase();
    return /\.(mp4|mov|webm|m4v|avi|mkv)(\?|$)/.test(lower);
  }
  return false;
}

/**
 * Subscribe to the SSE stage stream. EventSource handles reconnection and
 * line-buffered parsing for us, so we only translate to typed callbacks.
 *
 * Backend has two response modes:
 *  - **first call** for a fresh thread → many `event: stage` frames as the
 *    graph runs, then `event: await_review`.
 *  - **subsequent calls** for the same thread (e.g. React Strict Mode's
 *    second mount, or a page refresh) → one `event: snapshot` with the full
 *    current state, then `event: await_review`. No per-stage frames are
 *    replayed. Handle this with `onSnapshot` so the UI is populated on
 *    re-entry without re-running the graph.
 */
export function subscribeStream(
  threadId: string,
  handlers: {
    onStage?: (e: StageEvent) => void;
    onSnapshot?: (e: StateSnapshot) => void;
    onAwaitReview?: (e: AwaitReviewEvent) => void;
    onDone?: () => void;
    onError?: (msg: string) => void;
  },
): () => void {
  const es = new EventSource(streamUrl(threadId));

  es.addEventListener("stage", (ev: MessageEvent) => {
    try {
      handlers.onStage?.(JSON.parse(ev.data));
    } catch {
      /* ignore malformed */
    }
  });
  es.addEventListener("snapshot", (ev: MessageEvent) => {
    try {
      handlers.onSnapshot?.(JSON.parse(ev.data));
    } catch {
      /* ignore */
    }
  });
  es.addEventListener("await_review", (ev: MessageEvent) => {
    try {
      handlers.onAwaitReview?.(JSON.parse(ev.data));
    } catch {
      /* ignore */
    }
    es.close();
    handlers.onDone?.();
  });
  es.addEventListener("done", () => {
    es.close();
    handlers.onDone?.();
  });
  es.addEventListener("error", (ev: MessageEvent) => {
    // SSE 'error' fires both for transport errors (no data) and our explicit
    // 'event: error' frames. Only the latter has data.
    if (ev.data) {
      try {
        const parsed = JSON.parse(ev.data);
        handlers.onError?.(parsed.message ?? "unknown");
      } catch {
        handlers.onError?.("unknown");
      }
      es.close();
    }
  });

  return () => es.close();
}
