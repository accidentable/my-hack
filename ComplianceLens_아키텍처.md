# ComplianceLens — 아키텍처 설계서

> 멀티모달·다국어 금융 콘텐츠 사전심의 AI Agent
> JB금융그룹 Fin:AI Challenge — 지정주제 2. Compliance AI
> 본 문서는 Claude Code로 구현하기 위한 기술 설계서다.

---

## 1. 설계 원칙

1. **자율 루프 + 결정론적 가드레일**
   에이전트가 흐름을 주도(다음에 어떤 도구를 쓸지 판단)하되, 규제 판정 같은 책임 있는 결정은 결정론적 규칙엔진이 담당한다. 판단의 *자율성*은 오케스트레이션에, 판정의 *신뢰성*은 규칙에 둔다.

2. **모든 판정은 근거를 동반한다 (설명가능성)**
   LLM 출력은 자유 텍스트가 아니라 구조화 스키마로 강제한다. `근거 규정`이 없는 판정은 폐기하거나 신뢰도를 낮춘다.

3. **사람이 최종 결정 (HITL)**
   에이전트는 "보좌"다. 심의의견서 생성 후 **사람 검토 단계에서 정지**하고, 승인/반려/코멘트를 받아 재개한다. 책임 소재는 사람에게 남긴다.

4. **자기수정 (Self-Correction)**
   검증(verify)에서 근거 조항이 실재하지 않으면 해당 판정을 폐기하고 되돌아가 재판정한다. 이 루프백이 단순 파이프라인과 에이전트를 가르는 지점이다.

5. **다국어는 원문 직접 심의**
   외국어를 한국어로 번역해 심의하지 않는다. 원문 그대로 판정하고 화면엔 원문/번역/근거를 병기한다.

6. **Vertical Slice 우선**
   각 단계를 따로 완성하지 않는다. ①~⑥이 허접하게라도 관통하는 한 줄을 먼저 만들고 품질을 올린다.

---

## 2. 기술 스택 (결정 + 사유)

| 영역 | 선택 | 사유 |
|---|---|---|
| 백엔드 | **Python + FastAPI** | LLM/RAG 생태계가 가장 두텁고, 비동기 스트리밍(SSE) 지원, 빠른 프로토타이핑 |
| 에이전트 | **LangGraph** | 상태(State)·노드·조건부 엣지가 1급 개념 → 자기수정 루프와 HITL 정지를 구조적으로 표현. "Agent다움"을 그래프 그림으로 발표에 그대로 활용 |
| 멀티모달 LLM | **GPT-4o 계열 (OpenAI API)** | 비전으로 카드뉴스 텍스트를 직접 읽음(별도 OCR 불필요), **Structured Outputs(JSON Schema 강제)** 로 근거 동반 판정 구현이 깔끔, 다국어 지원. 비용 절감용 보조 판정은 mini 계열 혼용 가능 |
| 벡터 DB | **Chroma** (로컬 임베딩) | 의존성 가볍고 파일 기반, 4일 데모에 충분. 규정 청크 검색용 |
| 규칙엔진 | **YAML 규칙 + Python 평가기** | 필수 고지 누락 등 결정론적 규칙을 코드 밖(YAML)에 두어 추가·수정 용이 |
| 프론트엔드 | **Next.js + TypeScript + Tailwind** | 업로드/진행 스트리밍/검토 UI를 한 번에. App Router + SSE 소비 |
| 통신 | **REST + SSE(Server-Sent Events)** | 에이전트 단계 진행을 실시간 스트리밍. WebSocket까지 갈 필요 없음 |

> MVP 단순화: 카드뉴스(이미지)는 GPT-4o 비전으로 직접 읽으므로 **별도 OCR 불필요**. 단, 깨알 고지(작은 글씨)·다국어 정확도가 약하면 OCR(예: Google Vision/Tesseract)을 한 겹 붙이는 폴백을 둔다. 영상(STT)·실시간은 확장 항목으로 분리한다.

---

## 3. 시스템 구성도

```
┌──────────────────────────────────────────────────────────────────┐
│  [1] Web UI  — Next.js + TS + Tailwind                            │
│   · 제작자 화면 : 콘텐츠 업로드 → 진행상황 스트리밍 → 결과         │
│   · 준법관리자 화면 : 체크리스트 검토 → 승인/반려/코멘트 → 문서     │
└───────────────▲────────────────────────────────┬─────────────────┘
                │ SSE (단계 진행 스트리밍)         │ REST (업로드/검토 제출)
┌───────────────┴────────────────────────────────▼─────────────────┐
│  [2] Backend — FastAPI                                            │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │ Agent Orchestrator (LangGraph)                            │   │
│   │  State를 들고 노드를 진행, 조건부 엣지로 분기/자기수정      │   │
│   │                                                            │   │
│   │  ingest → retrieve → assess → verify ──pass──→ generate    │   │
│   │                         ▲           │                      │   │
│   │                         └──fail(재판정)┘                   │   │
│   │                                          │                 │   │
│   │                              generate → [INTERRUPT: 사람검토]│   │
│   │                                          │                 │   │
│   │                              review(resume) → finalize → done│  │
│   └───────────┬───────────────────────────────┬──────────────┘   │
│      Tools 호출 │                               │ LLM 호출          │
│   ┌────────────▼─────────┐          ┌──────────▼──────────┐       │
│   │ ingest / retrieve /   │          │  GPT-4o (멀티모달)   │       │
│   │ assess / verify /     │          │  + Structured Output │       │
│   │ generate              │          └─────────────────────┘       │
│   └───────────┬───────────┘                                        │
└───────────────┼────────────────────────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────────────────────────┐
│  [3] Knowledge & Rules                                             │
│   · Chroma 벡터DB : 규정 청크(금소법 광고규제·협회 심의기준) + 임베딩│
│   · 규칙엔진 : rules.yaml (필수고지 등 결정론적 규칙) + 평가기        │
│   · 규정 원문 색인 : 조항ID → 원문 (verify의 실재 검증용)            │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4. 에이전트 상태 (State)

LangGraph가 노드 사이에 들고 다니는 단일 상태 객체. UI 스트리밍·디버깅·검토 재개를 전부 단순화한다.

```python
# backend/app/agent/state.py
from typing import TypedDict, Literal, Optional

class Claim(TypedDict):
    id: str
    text_original: str        # 원문(예: 베트남어)
    text_ko: str              # 한국어 병기(검증 보조용, 심의 기준 아님)
    modality: Literal["image_text", "caption", "speech", "graphic"]

class Regulation(TypedDict):
    article_id: str           # 예: "금소법-광고-제17조"
    title: str
    snippet: str              # 검색된 근거 청크

class Finding(TypedDict):
    claim_id: str
    severity: Literal["high", "medium", "low"]   # high=확정위반, medium=사람판단
    source: Literal["rule", "llm"]               # 규칙엔진 / LLM
    regulation_id: str                            # 근거 조항
    issue: str                                    # 무엇이 문제인지
    current_text: str                             # 현재 표현(원문)
    suggestion: str                               # 수정안
    confidence: float                             # 0.0~1.0
    verified: bool                                # verify 통과 여부

class ReviewInput(TypedDict):
    finding_id: str
    decision: Literal["approve", "reject"]
    comment: str

class AgentState(TypedDict):
    # 입력
    content_ref: str                  # 업로드된 콘텐츠 경로/ID
    content_type: Literal["card", "poster", "video"]
    language: str                     # "vi", "ko", "th" ...
    # 단계별 산출
    claims: list[Claim]
    regulations: list[Regulation]
    findings: list[Finding]
    verify_passed: bool
    retry_count: int                  # 자기수정 루프 횟수 제한용
    report_markdown: Optional[str]    # 심의의견서(생성물)
    review_inputs: list[ReviewInput]  # 사람 검토 결과
    final_report_markdown: Optional[str]
    stage: Literal["ingest","retrieve","assess","verify","generate","review","done"]
```

---

## 5. 에이전트 그래프 (노드 & 엣지)

```python
# backend/app/agent/graph.py (의사코드)
graph = StateGraph(AgentState)

graph.add_node("ingest",   ingest_node)     # 멀티모달 → 주장 추출
graph.add_node("retrieve", retrieve_node)   # 규정 RAG
graph.add_node("assess",   assess_node)     # 규칙 + LLM 하이브리드 판정
graph.add_node("verify",   verify_node)     # 근거 조항 실재 검증
graph.add_node("generate", generate_node)   # 심의의견서 생성
graph.add_node("finalize", finalize_node)   # 검토 반영 → 최종본

graph.set_entry_point("ingest")
graph.add_edge("ingest", "retrieve")
graph.add_edge("retrieve", "assess")
graph.add_edge("assess", "verify")

# 조건부 엣지: 검증 실패 시 자기수정(재판정), 단 retry 한도
graph.add_conditional_edges("verify", route_after_verify, {
    "pass": "generate",
    "retry": "assess",     # ← 자기수정 루프백
})

# 생성 후 사람 검토 대기(INTERRUPT) → resume 시 finalize로
graph.add_edge("generate", END)        # interrupt_before=["review"] 형태로 정지
graph.add_edge("finalize", END)

def route_after_verify(state):
    if state["verify_passed"]:
        return "pass"
    if state["retry_count"] < 2:        # 무한루프 방지
        return "retry"
    return "pass"                        # 한도 초과 시 미검증 항목은 신뢰도 낮춰 통과
```

> HITL 정지: LangGraph의 `interrupt`(checkpointer 사용)로 `generate` 후 멈춘다.
> 사람이 검토를 제출하면 같은 thread를 resume 하여 `finalize`를 실행한다.

### 노드별 책임

| 노드 | 입력 | 출력 | 비고 |
|---|---|---|---|
| `ingest` | content_ref | `claims[]` | GPT-4o 비전으로 카드 이미지에서 주장 추출(원문+한국어 병기). OCR 불필요(폴백만 대비) |
| `retrieve` | claims | `regulations[]` | 콘텐츠 유형 판별 → Chroma에서 적용 규정 청크 검색 |
| `assess` | claims, regulations | `findings[]` | **규칙엔진(A) + LLM(B) 병합** (아래 6장) |
| `verify` | findings | `verify_passed`, 갱신된 findings | 각 finding의 `regulation_id`가 규정 색인에 실재하는지 확인. 가짜 조항이면 verified=false |
| `generate` | findings | `report_markdown` | 구조화 findings → 심의의견서(MD/표) 렌더 후 **정지** |
| `finalize` | review_inputs | `final_report_markdown` | 승인/반려/코멘트 반영해 수정사항 정리본 재출력 |

---

## 6. assess — 규칙 + LLM 하이브리드 (핵심)

```python
# backend/app/agent/nodes/assess.py (의사코드)
def assess_node(state):
    findings = []

    # (A) 결정론적 규칙 — 놓치면 안 되는 것 (필수 고지 누락 등)
    for rule in load_rules("rules.yaml"):
        hit = rule.check(state["claims"], state["content_ref"])
        if hit.violated:
            findings.append(Finding(
                source="rule", severity="high", confidence=1.0,
                regulation_id=rule.regulation_id, issue=hit.issue,
                current_text=hit.evidence, suggestion=rule.suggestion,
                verified=False,
            ))

    # (B) LLM 판정 — 모호한 것 (과장·오해 소지). Structured Outputs로 형식 강제
    llm_findings = openai_structured(
        model="gpt-4o",                       # 멀티모달·판정
        prompt=ASSESS_PROMPT,                 # "근거 조항을 반드시 인용"
        claims=state["claims"],
        regulations=state["regulations"],
        response_format=FindingsSchema,       # JSON Schema 강제, 근거 없으면 무효
    )
    for f in llm_findings:
        f["source"] = "llm"
        findings.append(f)

    state["findings"] = findings
    state["stage"] = "assess"
    return state
```

- **(A) 규칙**: 답이 정해진 검사. 신뢰도 1.0, 절대 누락 없음. `rules.yaml`로 분리.
- **(B) LLM**: 맥락 판단이 필요한 것만. 반드시 근거 규정 인용을 구조화 스키마로 강제.
- 병합 결과가 체크리스트가 된다.

### rules.yaml 예시
```yaml
- id: mandatory_disclosure_principal_loss
  regulation_id: "금소법-광고-원금손실고지"
  description: "투자성 상품 광고에 원금손실 가능성 고지 필수"
  check:
    type: "must_contain_any"
    patterns: ["원금손실", "원금 손실", "투자원금", "rủi ro mất vốn"]  # 다국어 패턴
  on_missing:
    severity: high
    issue: "원금손실 가능성 필수 고지가 누락됨"
    suggestion: "‘투자원금 손실이 발생할 수 있습니다’ 고지를 명시적으로 추가"
- id: prohibited_guarantee_expression
  regulation_id: "금소법-광고-수익보장금지"
  description: "확정적 수익·원금보장 오인 표현 금지"
  check:
    type: "must_not_contain_any"
    patterns: ["확정수익", "원금보장", "무조건", "đảm bảo lợi nhuận"]
  on_hit:
    severity: high
    issue: "수익 보장으로 오인될 수 있는 표현 사용"
    suggestion: "단정적 표현을 ‘과거 성과이며 미래를 보장하지 않습니다’로 완화"
```

---

## 7. API 설계 (FastAPI)

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/api/review` | 콘텐츠 업로드 → 에이전트 실행 시작, `thread_id` 반환 |
| `GET` | `/api/review/{thread_id}/stream` | **SSE**: 단계 진행(ingest→…→generate) 실시간 스트리밍 |
| `GET` | `/api/review/{thread_id}` | 현재 상태/심의의견서 조회 |
| `POST` | `/api/review/{thread_id}/resume` | 사람 검토(review_inputs) 제출 → finalize 재개 |
| `GET` | `/api/review/{thread_id}/report` | 최종 심의의견서(MD/PDF) 다운로드 |

SSE 이벤트 예:
```
event: stage   data: {"stage":"assess","msg":"규칙 2건·LLM 3건 판정"}
event: stage   data: {"stage":"verify","msg":"근거 조항 검증, 1건 폐기 후 재판정"}
event: result  data: {"findings":[...],"report_markdown":"..."}
event: await_review  data: {"thread_id":"..."}
```

---

## 8. 프론트엔드 (Next.js)

| 라우트 | 화면 | 내용 |
|---|---|---|
| `/` | 업로드 | 콘텐츠(카드 이미지) 업로드, 언어 선택 |
| `/review/[id]` | 진행 + 결과 | SSE로 단계 진행 표시 → 체크리스트(원문/번역/근거/심각도/신뢰도) |
| `/review/[id]` (검토 모드) | 준법관리자 검토 | 항목별 승인/반려 토글 + 코멘트 → 제출 → 최종 정리본 |

UI 포인트
- 진행 단계를 6스텝 프로그레스로 시각화(에이전트가 "스스로 진행"하는 느낌 = 데모 임팩트).
- 체크리스트는 심각도별 색상(high=빨강, medium=주황). 각 항목에 **근거 조항** 항상 노출.
- 다국어 항목은 원문/번역 토글.

---

## 9. 폴더 구조

```
compliancelens/
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 # FastAPI 엔트리, 라우트
│  │  ├─ api/
│  │  │  ├─ review.py            # /api/review 엔드포인트들
│  │  │  └─ sse.py               # SSE 스트리밍 유틸
│  │  ├─ agent/
│  │  │  ├─ state.py             # AgentState 등 스키마
│  │  │  ├─ graph.py             # LangGraph 그래프 정의
│  │  │  └─ nodes/
│  │  │     ├─ ingest.py
│  │  │     ├─ retrieve.py
│  │  │     ├─ assess.py         # 규칙 + LLM
│  │  │     ├─ verify.py
│  │  │     ├─ generate.py
│  │  │     └─ finalize.py
│  │  ├─ rules/
│  │  │  ├─ rules.yaml           # 결정론적 규칙
│  │  │  └─ engine.py            # 규칙 평가기
│  │  ├─ knowledge/
│  │  │  ├─ ingest_regs.py       # 규정 문서 → 청크 → Chroma 적재 스크립트
│  │  │  ├─ store.py             # Chroma 검색 래퍼
│  │  │  └─ reg_index.json       # 조항ID → 원문 (verify용)
│  │  ├─ llm/
│  │  │  ├─ client.py            # OpenAI API 래퍼(GPT-4o 비전·Structured Outputs)
│  │  │  └─ prompts.py           # ASSESS_PROMPT 등
│  │  └─ config.py
│  ├─ data/
│  │  ├─ regulations/            # 규정 원문(텍스트)
│  │  └─ samples/                # 데모용 베트남어 카드뉴스(위반 3종 심은 것)
│  └─ requirements.txt
├─ frontend/
│  ├─ app/
│  │  ├─ page.tsx                # 업로드
│  │  └─ review/[id]/page.tsx    # 진행+결과+검토
│  ├─ components/                # ProgressSteps, FindingCard, ReviewPanel
│  ├─ lib/api.ts                 # 백엔드 호출 + SSE 구독
│  └─ types.ts                   # State/Finding TS 타입(백엔드와 동기화)
└─ README.md
```

---

## 10. 데이터 흐름 (한 사이클)

```
제작자 ─업로드─▶ POST /api/review ─▶ 에이전트 시작(thread_id)
   │
   └─ GET .../stream (SSE 구독)
        ◀─ ingest  : 베트남어 카드 → 주장 5개
        ◀─ retrieve: 적용 규정 청크 N개
        ◀─ assess  : 규칙 2 + LLM 3 = findings 5
        ◀─ verify  : 가짜 조항 1건 폐기 → assess 재실행(retry) → 통과
        ◀─ generate: 심의의견서 생성 ─▶ [정지: await_review]
   │
준법관리자 ─검토─▶ POST .../resume {승인/반려/코멘트}
        ◀─ finalize: 수정사항 정리본(final_report) 출력
   │
   └─ GET .../report (다운로드)  ─▶ 제작자 수정 반영 후 게시
```

---

## 11. MVP 범위 (실제 구현 vs 목업 vs 본선)

| 항목 | 예선 MVP (실제 동작) | 본선 고도화 |
|---|---|---|
| 입력 | 카드뉴스(이미지) 1~2장 | 영상(STT)·포스터·실시간 |
| 언어 | 베트남어 + 한국어 | 태국어·캄보디아어 등 |
| ingest | GPT-4o 비전 직접(이미지 입력) | 영상 프레임/음성 파이프라인 |
| retrieve | Chroma + 규정 일부(광고규제 핵심) | 규정 전체 색인 |
| assess | 규칙 3~5개 + LLM | 규칙셋 확대, 콘텐츠 유형별 분기 |
| verify | 근거 조항 실재 검증 | 정합성·상충 검증 강화 |
| 사람 검토 | 승인/반려/코멘트 → 정리본 재출력 | **검토 의견 학습(재학습)** |
| 규제 추적 | (발표/다이어그램) | 규정 변경 감지 → 영향 콘텐츠 재심의 |

---

## 12. 구현 순서 (4일)

- **Day 1 — Vertical Slice 관통**
  데모용 베트남어 카드 제작(위반 3종 심기) → ingest~generate를 *허접하게라도* 한 번에 통과시켜 심의의견서 출력. 프론트는 결과 텍스트만.
- **Day 2 — 핵심 품질**
  규칙엔진(rules.yaml) + LLM 구조화 출력 분리, Chroma에 규정 적재, verify 근거 검증 + 자기수정 루프.
- **Day 3 — Agent답게 + UI**
  LangGraph 그래프 정리(조건부 엣지·INTERRUPT), SSE 진행 스트리밍, 검토 화면(토글·코멘트→재출력).
- **Day 4 — 다듬기 + 산출물**
  체크리스트 UI(심각도 색상·원문/번역 병기), 데모 리허설, 시연영상 녹화, 제안서·기능명세서와 기능 일치 점검.

---

## 13. 기술 리스크 & 대응

| 리스크 | 대응 |
|---|---|
| LLM 환각(가짜 조항) | verify 노드에서 조항 실재 검증 + 규칙엔진 병행 + 신뢰도 표기 |
| 자기수정 무한루프 | `retry_count` 한도(2회), 초과 시 미검증 항목 신뢰도 낮춰 통과 |
| 다국어 판정 흔들림 | 원문 직접 판정 + 한국어 병기로 사람이 검증, 데모는 베트남어로 한정 |
| 데모 불안정(라이브 API) | 샘플 입력 고정 + 결과 캐시 옵션, 네트워크 실패 시 폴백 |
| GPT 비전 깨알 고지 누락 | Day1 테스트 → 약하면 OCR(Google Vision/Tesseract) 한 겹 추가, 규칙엔진 패턴 보강 |
| 규정 데이터 부족 | 광고규제 핵심 조항만 추려 적재(전체 불필요), 출처·라이선스 부록 명시 |
| 스코프 초과 | Vertical Slice 우선, 영상/재학습/다언어는 본선으로 이관 |

---

## 14. 평가 루브릭 → 아키텍처 매핑

| 평가항목(20점×5) | 아키텍처 근거 |
|---|---|
| 1. 주제적합성·문제정의 | 수작업·다국어 심의 병목을 정조준, 실증 Pain Point |
| 2. 사업연계·고객가치 | JB 외국인 금융 1위 ↔ 다국어 심의, PII 마스킹·내부통제 인식 |
| 3. AI Agent 설계 | LangGraph 상태/노드/조건부 엣지 + verify 자기수정 + HITL 정지 |
| 4. MVP 완성도 | Vertical Slice 한 사이클 동작, 문서·코드·영상 일관 |
| 5. 혁신·확장·리스크 | 수작업→사전심의 전환, 환각·책임소재(HITL)·설명가능성·출처 |

---

## 15. To-Do (구현 전 확정)

- [ ] OpenAI API 키 발급, GPT-4o 비전·Structured Outputs 호출 확인
- [ ] **Day1 점검**: GPT-4o가 베트남어 카드의 깨알 고지(작은 글씨)를 잘 읽는지 테스트 → 약하면 OCR 폴백 결정
- [ ] 규정 원문 확보 — 금소법 광고규제·금융투자협회 광고심의기준 핵심 조항
- [ ] 데모용 베트남어 카드뉴스 2장 제작(위반 3종 심기)
- [ ] rules.yaml 초안(규칙 3~5개, 다국어 패턴 포함)
- [ ] 백엔드/프론트 타입 동기화 규칙(State/Finding)
- [ ] LangGraph checkpointer(메모리/SQLite) 선택 — HITL resume용
- [ ] LangGraph ↔ OpenAI 연동(`langchain-openai`의 ChatOpenAI 또는 OpenAI SDK 직접) 방식 확정
