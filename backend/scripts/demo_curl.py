"""Walk one card through the live FastAPI service:

    1) POST /api/review                       — upload, get thread_id
    2) GET  /api/review/{tid}/stream          — SSE stage events + await_review
    3) GET  /api/review/{tid}                 — inspect findings
    4) POST /api/review/{tid}/resume          — submit reviewer decisions
    5) GET  /api/review/{tid}/report          — final markdown

Uses urllib + the multipart-encoding shim below so it has zero deps beyond stdlib
(this is intentional — the script doubles as a demo of how to call the API).

Run (server must already be up on http://127.0.0.1:8000):
    python -m scripts.demo_curl data/samples/vi_loan_card.png
"""
from __future__ import annotations

import json
import mimetypes
import sys
import uuid
from pathlib import Path
from urllib import request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8000"


def _multipart(file_path: Path, language: str) -> tuple[bytes, str]:
    boundary = "----CLB" + uuid.uuid4().hex
    mime, _ = mimetypes.guess_type(file_path.name)
    mime = mime or "application/octet-stream"
    chunks: list[bytes] = []
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(b'Content-Disposition: form-data; name="file"; filename="' +
                  file_path.name.encode("utf-8") + b'"\r\n')
    chunks.append(f"Content-Type: {mime}\r\n\r\n".encode())
    chunks.append(file_path.read_bytes())
    chunks.append(f"\r\n--{boundary}\r\n".encode())
    chunks.append(b'Content-Disposition: form-data; name="language"\r\n\r\n')
    chunks.append(language.encode("utf-8"))
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def upload(file_path: Path, language: str = "vi") -> dict:
    body, ctype = _multipart(file_path, language)
    req = request.Request(f"{BASE}/api/review", data=body, headers={"Content-Type": ctype})
    with request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def stream(thread_id: str) -> None:
    req = request.Request(f"{BASE}/api/review/{thread_id}/stream",
                          headers={"Accept": "text/event-stream"})
    with request.urlopen(req) as r:
        for raw in r:
            line = raw.decode("utf-8").rstrip("\n")
            if line:
                print("  " + line)
            else:
                print()


def get_state(thread_id: str) -> dict:
    with request.urlopen(f"{BASE}/api/review/{thread_id}") as r:
        return json.loads(r.read().decode("utf-8"))


def resume(thread_id: str, review_inputs: list[dict]) -> dict:
    body = json.dumps({"review_inputs": review_inputs}, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{BASE}/api/review/{thread_id}/resume",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_report(thread_id: str) -> str:
    with request.urlopen(f"{BASE}/api/review/{thread_id}/report") as r:
        return r.read().decode("utf-8")


def _build_review_inputs(findings: list[dict]) -> list[dict]:
    """Approve all except the urgency/긴급성 finding (reject as illustrative example)."""
    out: list[dict] = []
    for f in findings:
        fid = f"{f['claim_id']}:{f['regulation_id']}"
        if "긴급" in f["issue"] or "한정" in f["issue"]:
            out.append({"finding_id": fid, "decision": "reject",
                        "comment": "긴급성 표현이나 통상 마케팅 범주로 판단 — 별도 수정 불필요"})
        elif "원금손실" in f["issue"] or "설명의무" in f["issue"] or "중요사항" in f["issue"]:
            out.append({"finding_id": fid, "decision": "approve",
                        "comment": "외국어 콘텐츠 핵심 누락 — 베트남어 고지문 추가 필수"})
        elif "100%" in f["issue"] or "단정" in f["issue"]:
            out.append({"finding_id": fid, "decision": "approve",
                        "comment": "100% 표현 제거 후 심사 조건 명시"})
        elif "일 단위" in f["issue"] or "하루" in f["issue"]:
            out.append({"finding_id": fid, "decision": "approve",
                        "comment": "연이자율(APR) + 적용 조건 명시 후 재심의"})
        else:
            out.append({"finding_id": fid, "decision": "approve",
                        "comment": "수정 권고"})
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m scripts.demo_curl <card_image_path>", file=sys.stderr)
        return 2
    card = Path(argv[1])
    if not card.exists():
        print(f"not found: {card}", file=sys.stderr)
        return 2

    print("="*72)
    print("[1] POST /api/review — upload card")
    print("="*72)
    started = upload(card, language="vi")
    tid = started["thread_id"]
    print(json.dumps(started, ensure_ascii=False, indent=2))

    print()
    print("="*72)
    print(f"[2] GET /api/review/{tid}/stream — SSE stages")
    print("="*72)
    stream(tid)

    print("="*72)
    print(f"[3] GET /api/review/{tid} — inspect findings")
    print("="*72)
    state = get_state(tid)
    print(f"awaiting_review={state['awaiting_review']}  stage={state['stage']}  "
          f"retry={state['retry_count']}  findings={len(state['findings'])}")
    for f in state["findings"]:
        fid = f"{f['claim_id']}:{f['regulation_id']}"
        src = "+".join(f.get("merged_sources", [f["source"]]))
        print(f"  · {fid}")
        print(f"      sev={f['severity']:6}  src={src:9}  conf={f['confidence']:.2f}")
        print(f"      issue: {f['issue']}")

    review_inputs = _build_review_inputs(state["findings"])
    print()
    print("="*72)
    print(f"[4] POST /api/review/{tid}/resume — submit reviewer decisions")
    print("="*72)
    for r in review_inputs:
        print(f"  {r['decision']:7} {r['finding_id']}   // {r['comment']}")
    final_state = resume(tid, review_inputs)
    print()
    print(f"  stage={final_state['stage']}  awaiting_review={final_state['awaiting_review']}")
    print(f"  final_report length={len(final_state['final_report_markdown'] or '')}")

    print()
    print("="*72)
    print(f"[5] GET /api/review/{tid}/report — final markdown")
    print("="*72)
    print(fetch_report(tid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
