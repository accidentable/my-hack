# ComplianceLens

> 멀티모달·다국어 금융 콘텐츠 사전심의 AI Agent
> JB금융그룹 Fin:AI Challenge — 지정주제 2. Compliance AI

카드뉴스·릴스·포스터 등 대고객 콘텐츠를 게시 전에 자동 사전심의하여,
위반 소지·근거 규정·수정안을 정리하고 **준법관리자는 검토·승인만** 하도록 전환하는 AI Agent.

기준 문서 — `ComplianceLens_기획.md`, `ComplianceLens_아키텍처.md`, `ComplianceLens_프롬프트_README.md`.

---

## 핵심 동작

```
① 수집 → ② 검색 → ③ 판단 → ④ 검증 → ⑤ 의견서 → ⑥ 사람 검토
              규제 RAG    규칙엔진+LLM  근거 조항 실재 검증            HITL · resume
                          (이중 적발)  실패 시 ↺ 자기수정 (retry≤2)
```

- **모든 판정은 근거 규정 동반**: LLM 응답을 OpenAI Structured Outputs로 강제, 근거 없는 판정은 폐기.
- **규칙엔진 + LLM 하이브리드**: 필수 고지 누락 같은 결정론적 규칙은 `rules.yaml`, 과장·오해 등 맥락 판단은 LLM.
- **자기수정 루프**: `verify` 노드가 가짜 조항을 적발하면 `assess`로 되돌아가 재판정, 한도 2회.
- **HITL 정지**: `generate` 직후 `interrupt_before=["finalize"]`로 정지, 사람 검토 제출 후 `finalize` 재개.
- **다국어 원문 직접 심의**: 외국어를 한국어로 번역해 심의하지 않고, 원문 기준으로 판정하고 한국어를 병기.

---

## 기술 스택

- **백엔드**: Python + FastAPI + LangGraph + SQLite checkpointer
- **LLM**: OpenAI — `gpt-5.4`(assess, 정확도), `gpt-5.4-mini`(ingest, 비용)
- **벡터 DB**: Chroma (`text-embedding-3-small`)
- **규칙엔진**: YAML 규칙 + Python 평가기 (`applies_when` 콘텐츠 유형 게이팅)
- **프론트엔드**: Next.js (App Router) + TypeScript + Tailwind + Pretendard, SSE 단계 스트리밍

---

## 빠른 시작

### 사전 요구
- Python 3.11+, Node 18+
- OpenAI API 키

### 백엔드

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate    # Windows
# . .venv/bin/activate                              # macOS/Linux
pip install -r requirements.txt

cp .env.example .env       # OPENAI_API_KEY 입력
python -m app.knowledge.ingest_regs                  # 규정 → Chroma 적재 (최초 1회)

# CLI로 한 사이클 확인
python -m scripts.run_demo data/samples/vi_loan_card.png

# API 서버 (HITL + SSE)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

오프라인/비용 회피 모드: `COMPLIANCELENS_MOCK_LLM=1`. 단, mock은 고정 픽스처(베트남어 자동차 대출 시나리오)만 반환합니다.

### 프론트엔드

```bash
cd frontend
npm install
cp .env.local.example .env.local                     # NEXT_PUBLIC_BACKEND_URL
npm run dev                                          # http://localhost:3000
```

### 데모 흐름

1. 브라우저에서 `http://localhost:3000` 접속
2. 카드뉴스(이미지/영상) 드래그앤드롭 또는 클릭 업로드 → "심의 시작"
3. SSE 로그로 ingest → retrieve → assess → verify → generate 진행 관찰 (자기수정 시 retry 라벨)
4. 위반 소지 검토 패널에서 항목별 "위반 확인 / 위반 아님" 결정 + 코멘트
5. 검토 제출 → 최종 심의의견서 출력 (다운로드 가능)
6. 상단 탭에서 이전 thread를 클릭해 재진입 가능

---

## API (FastAPI · 아키텍처 §7)

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/review` | 멀티파트 업로드 → `thread_id` |
| GET | `/api/review/list` | 과거 thread 목록 (히스토리 탭) |
| GET | `/api/review/{tid}/stream` | SSE 단계 진행 |
| GET | `/api/review/{tid}` | 현재 state snapshot |
| GET | `/api/review/{tid}/content` | 업로드된 원본 (image/video) |
| POST | `/api/review/{tid}/resume` | review_inputs → `finalize` |
| GET | `/api/review/{tid}/report` | 최종/중간 의견서 (Markdown) |

---

## 폴더 구조

```
backend/
├─ app/
│  ├─ agent/                # LangGraph 상태·그래프·노드
│  │  ├─ state.py           # AgentState / Claim / Finding (TypedDict)
│  │  ├─ graph.py           # ingest→retrieve→assess→verify→generate→[INTERRUPT]→finalize
│  │  └─ nodes/
│  ├─ api/review.py         # FastAPI 라우터
│  ├─ knowledge/            # Chroma 적재 + 검색 (`store.py`, `ingest_regs.py`)
│  ├─ rules/                # rules.yaml + 평가기
│  ├─ llm/                  # OpenAI 단일 진입점 + 프롬프트 (`prompts.py` ASSESS_PROMPT)
│  └─ main.py               # FastAPI 엔트리 + lifespan(checkpointer)
├─ data/
│  ├─ regulations/          # 규정 원문 (금소법 광고규제 핵심 6건)
│  └─ samples/              # 데모 카드 (vi_loan_card.png + spec)
└─ scripts/                 # run_demo, demo_curl, ingest_regs, make_dummy_sample, check_models

frontend/
├─ app/
│  ├─ page.tsx              # 업로드 (drag-and-drop)
│  └─ review/[id]/page.tsx  # 좌: 원본 sticky / 우: 로그·검토 패널·최종 의견서
├─ components/              # ThreadHistoryTabs, ReviewPanel, FindingRow, OriginalPreview
└─ lib/api.ts               # 백엔드 호출 + SSE 구독
```

---

## 데이터 & 규정 출처

- 금융소비자 보호에 관한 법률 (국가법령정보센터)
- 금융투자협회 「금융투자회사의 영업 및 업무에 관한 규정」
- 금융위원회 「금융광고규제 가이드라인」

본 저장소의 `backend/data/regulations/*.txt`는 공개 법령·규정의 **데모용 요약**이며 원문 전체가 아닙니다.
실제 적용 시 위 출처의 최신 원문을 확인하세요.

---

## 책임 / 한계

- 본 에이전트는 **1차 보조 검토**입니다. 최종 결정과 책임은 **사람 준법관리자**에게 있습니다.
- 환각 대응: 규칙엔진 병행 + 근거 조항 실재 검증 + 자기수정 루프 + 신뢰도 표기.
- PII 마스킹은 콘텐츠 외 입력에 한해 운영 시점 적용을 권장.
