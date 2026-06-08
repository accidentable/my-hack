"""FastAPI endpoints for the ComplianceLens review pipeline.

Endpoints (architecture §7):
    POST /api/review                          → upload + thread_id
    GET  /api/review/{thread_id}/stream       → SSE: agent stage events
    GET  /api/review/{thread_id}              → current state snapshot
    POST /api/review/{thread_id}/resume       → submit review_inputs → finalize
    GET  /api/review/{thread_id}/report       → final/intermediate report markdown

The graph object and SQLite checkpointer are constructed once in main.py and
exposed via app.state.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from app import config
from app.agent.state import AgentState

router = APIRouter(prefix="/api/review", tags=["review"])


# -----------------------------------------------------------------------------
# Pydantic request/response models
# -----------------------------------------------------------------------------


class StartResponse(BaseModel):
    thread_id: str
    content_ref: str
    language: str


class ReviewInputModel(BaseModel):
    finding_id: str
    decision: str  # "approve" | "reject"
    comment: str = ""


class ResumeRequest(BaseModel):
    review_inputs: list[ReviewInputModel]


class ThreadMeta(BaseModel):
    """Compact metadata for the thread-history tab bar."""
    thread_id: str
    language: str
    stage: str | None
    findings_count: int
    awaiting_review: bool
    done: bool
    created_at: float        # uploaded file mtime (unix seconds)


class StateSnapshot(BaseModel):
    thread_id: str
    stage: str | None
    verify_passed: bool | None
    retry_count: int | None
    hallucinated_ids: list[str]
    claims: list[dict]
    findings: list[dict]
    report_markdown: str | None
    final_report_markdown: str | None
    awaiting_review: bool


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _initial_state(content_ref: str, language: str) -> AgentState:
    return {
        "content_ref": content_ref,
        "content_type": "card",
        "language": language,
        "claims": [],
        "regulations": [],
        "findings": [],
        "verify_passed": False,
        "retry_count": 0,
        "hallucinated_ids": [],
        "report_markdown": None,
        "review_inputs": [],
        "final_report_markdown": None,
        "stage": "ingest",
    }


def _sse(event: str, data: Any) -> bytes:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


def _snapshot(graph_app, thread_id: str) -> StateSnapshot:
    snap = graph_app.get_state(_thread_config(thread_id))
    if not snap or not snap.values:
        raise HTTPException(404, f"unknown thread_id: {thread_id}")
    values = dict(snap.values)
    # ``next`` is a tuple of the upcoming nodes — non-empty means we paused.
    awaiting = bool(snap.next) and "finalize" in snap.next
    return StateSnapshot(
        thread_id=thread_id,
        stage=values.get("stage"),
        verify_passed=values.get("verify_passed"),
        retry_count=values.get("retry_count"),
        hallucinated_ids=values.get("hallucinated_ids", []),
        claims=values.get("claims", []),
        findings=values.get("findings", []),
        report_markdown=values.get("report_markdown"),
        final_report_markdown=values.get("final_report_markdown"),
        awaiting_review=awaiting,
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.get("/list", response_model=list[ThreadMeta])
async def list_threads(request: Request) -> list[ThreadMeta]:
    """Return all threads that actually started running, newest first.

    Walks UPLOADS_DIR for thread_id from filename, then asks the checkpointer
    whether that thread has any state. Threads that received POST but never
    triggered ``stream`` are skipped (no values yet).
    """
    graph_app = request.app.state.graph
    out: list[ThreadMeta] = []
    for path in config.UPLOADS_DIR.glob("*.*"):
        tid = path.stem
        snap = graph_app.get_state(_thread_config(tid))
        if not snap or not snap.values:
            continue
        values = dict(snap.values)
        awaiting = bool(snap.next) and "finalize" in snap.next
        out.append(
            ThreadMeta(
                thread_id=tid,
                language=values.get("language", ""),
                stage=values.get("stage"),
                findings_count=len(values.get("findings", [])),
                awaiting_review=awaiting,
                done=bool(values.get("final_report_markdown")),
                created_at=path.stat().st_mtime,
            )
        )
    out.sort(key=lambda t: -t.created_at)
    return out


@router.post("", response_model=StartResponse)
async def start_review(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form(""),
) -> StartResponse:
    """Persist the uploaded card and create a fresh thread_id.

    The graph is NOT executed here — call GET /stream to drive it and receive
    stage events. This separation lets the client subscribe to SSE before any
    stage runs (so the first ``ingest`` event isn't missed).
    """
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    thread_id = uuid.uuid4().hex

    suffix = ""
    if file.filename and "." in file.filename:
        suffix = "." + file.filename.rsplit(".", 1)[-1]
    out_path = config.UPLOADS_DIR / f"{thread_id}{suffix}"
    content = await file.read()
    out_path.write_bytes(content)

    return StartResponse(
        thread_id=thread_id,
        content_ref=str(out_path),
        language=language,
    )


@router.get("/{thread_id}/stream")
async def stream_review(request: Request, thread_id: str) -> StreamingResponse:
    """Execute the graph and stream each stage's outcome as SSE events.

    Pauses at ``interrupt_before=["finalize"]``. When the pause is reached, an
    ``await_review`` event is emitted and the connection closes — client
    then calls /resume.
    """
    graph_app = request.app.state.graph

    # Find this thread's upload (start_review wrote {thread_id}.<ext}).
    candidates = list(config.UPLOADS_DIR.glob(f"{thread_id}.*"))
    if not candidates:
        raise HTTPException(404, f"no upload for thread_id={thread_id}")
    content_ref = str(candidates[0])

    cfg = _thread_config(thread_id)

    # If we already have state for this thread (re-subscribe / page refresh),
    # don't restart — just replay the current snapshot then close.
    existing = graph_app.get_state(cfg)
    if existing and existing.values:
        async def replay():
            snap = _snapshot(graph_app, thread_id)
            yield _sse("snapshot", snap.model_dump())
            if snap.awaiting_review:
                yield _sse("await_review", {"thread_id": thread_id})
        return StreamingResponse(replay(), media_type="text/event-stream")

    state = _initial_state(content_ref, "")

    def runner():
        try:
            yield _sse("stage", {"stage": "start", "msg": "에이전트 시작"})
            # stream_mode="updates" yields per-node delta dicts: {node_name: state_delta}
            for chunk in graph_app.stream(state, config=cfg, stream_mode="updates"):
                for node_name, delta in chunk.items():
                    msg = _stage_message(node_name, delta)
                    yield _sse("stage", {"stage": node_name, "msg": msg})
            # If we land here, either: (a) the graph completed without an
            # interrupt (shouldn't happen — finalize is interrupt_before), or
            # (b) we hit the interrupt and the iterator finishes.
            snap = _snapshot(graph_app, thread_id)
            if snap.awaiting_review:
                yield _sse(
                    "await_review",
                    {
                        "thread_id": thread_id,
                        "findings_count": len(snap.findings),
                        "report_preview_len": len(snap.report_markdown or ""),
                    },
                )
            else:
                yield _sse("done", {"thread_id": thread_id, "stage": snap.stage})
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {"type": type(e).__name__, "message": str(e)})

    return StreamingResponse(runner(), media_type="text/event-stream")


def _stage_message(node_name: str, delta: dict) -> str:
    if node_name == "ingest":
        return f"주장 {len(delta.get('claims', []))}건 추출"
    if node_name == "retrieve":
        return f"규정 {len(delta.get('regulations', []))}건 검색"
    if node_name == "assess":
        return f"위반 후보 {len(delta.get('findings', []))}건 판정 (규칙 + LLM)"
    if node_name == "verify":
        if delta.get("verify_passed"):
            return "근거 조항 검증 통과"
        return f"환각 의심 폐기·재판정 (retry={delta.get('retry_count')})"
    if node_name == "generate":
        return "심의의견서 생성 — 사람 검토 대기"
    return node_name


@router.post("/{thread_id}/resume", response_model=StateSnapshot)
async def resume_review(request: Request, thread_id: str, body: ResumeRequest) -> StateSnapshot:
    graph_app = request.app.state.graph
    cfg = _thread_config(thread_id)

    snap_before = graph_app.get_state(cfg)
    if not snap_before or not snap_before.values:
        raise HTTPException(404, f"unknown thread_id: {thread_id}")
    if not snap_before.next or "finalize" not in snap_before.next:
        raise HTTPException(409, "thread is not awaiting review")

    review_inputs = [r.model_dump() for r in body.review_inputs]
    graph_app.update_state(cfg, {"review_inputs": review_inputs})
    # Resume by invoking with input=None — LangGraph continues from where it
    # paused, running ``finalize`` to completion.
    graph_app.invoke(None, config=cfg)

    return _snapshot(graph_app, thread_id)


@router.get("/{thread_id}", response_model=StateSnapshot)
async def get_state_snapshot(request: Request, thread_id: str) -> StateSnapshot:
    graph_app = request.app.state.graph
    return _snapshot(graph_app, thread_id)


@router.get("/{thread_id}/content")
async def get_content(thread_id: str) -> FileResponse:
    """Serve the uploaded source file (image or video) for side-by-side review.

    Looks up ``{thread_id}.<ext>`` in UPLOADS_DIR. FileResponse fills in the
    right media-type from the extension, so <img> / <video> elements work
    out of the box.
    """
    candidates = list(config.UPLOADS_DIR.glob(f"{thread_id}.*"))
    if not candidates:
        raise HTTPException(404, f"no content for thread_id={thread_id}")
    path = candidates[0]
    return FileResponse(path, filename=path.name)


@router.get("/{thread_id}/report", response_class=PlainTextResponse)
async def get_report(request: Request, thread_id: str) -> PlainTextResponse:
    graph_app = request.app.state.graph
    snap = _snapshot(graph_app, thread_id)
    body = snap.final_report_markdown or snap.report_markdown
    if not body:
        raise HTTPException(404, "no report yet")
    return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")
