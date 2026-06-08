"""Single entry point for OpenAI calls.

Every LLM call in the project goes through here so we have one place to:
  - swap models
  - inject mock responses for offline dev
  - centralize Structured-Outputs parsing
"""
from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app import config
from app.agent.state import ClaimsResponse, FindingsResponse
from app.llm.prompts import ASSESS_PROMPT, INGEST_PROMPT

T = TypeVar("T", bound=BaseModel)


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.require_openai_key())
    return _client


def _image_to_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime is None:
        mime = "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def extract_claims_from_image(image_path: Path) -> ClaimsResponse:
    """ingest node: vision → ClaimsResponse. Uses the cost-tier INGEST model."""
    if config.MOCK_LLM:
        return _mock_claims()

    client = _get_client()
    completion = client.beta.chat.completions.parse(
        model=config.OPENAI_MODEL_INGEST,
        messages=[
            {"role": "system", "content": INGEST_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "이 카드뉴스에서 모든 문구를 추출해줘."},
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_to_data_url(image_path)},
                    },
                ],
            },
        ],
        response_format=ClaimsResponse,
        temperature=0,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("OpenAI returned no parsed ClaimsResponse")
    return parsed


def assess_with_llm(
    claims_json: list[dict],
    regulations_json: list[dict],
    hallucinated_ids: list[str] | None = None,
) -> FindingsResponse:
    """assess node (LLM half): claims + regulations → FindingsResponse.

    If ``hallucinated_ids`` is non-empty, those article_ids are flagged in the
    user message so the model knows NOT to cite them again. This is what closes
    the self-correction loop on retry.
    """
    if config.MOCK_LLM:
        return _mock_findings(claims_json, regulations_json, hallucinated_ids or [])

    user_payload = {
        "claims": claims_json,
        "regulations": regulations_json,
    }
    if hallucinated_ids:
        user_payload["forbidden_regulation_ids"] = hallucinated_ids
        user_payload["__retry_note__"] = (
            "이전 시도에서 다음 regulation_id는 실재하지 않는 것으로 검증되어 폐기되었습니다. "
            "이번 응답에서는 이 id들을 절대 인용하지 마십시오. "
            "반드시 'regulations' 목록 안에 실제로 있는 article_id만 사용하십시오."
        )

    client = _get_client()
    completion = client.beta.chat.completions.parse(
        model=config.OPENAI_MODEL_ASSESS,
        messages=[
            {"role": "system", "content": ASSESS_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        response_format=FindingsResponse,
        temperature=0,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise RuntimeError("OpenAI returned no parsed FindingsResponse")
    return parsed


# -----------------------------------------------------------------------------
# Mock fixtures — used when COMPLIANCELENS_MOCK_LLM=1
# Lets us smoke-test the whole graph offline. Will be replaced by real calls
# once the demo card and OPENAI_API_KEY are in place.
# -----------------------------------------------------------------------------


def _mock_claims() -> ClaimsResponse:
    # JB 본업 데모: 베트남어 자동차 대출 카드.
    return ClaimsResponse.model_validate(
        {
            "language": "vi",
            "claims": [
                {
                    "id": "c1",
                    "text_original": "VAY MUA Ô TÔ JB VIỆT NAM",
                    "text_ko": "JB 베트남 자동차 대출",
                    "modality": "image_text",
                },
                {
                    "id": "c2",
                    "text_original": "Chỉ 9.900 đồng/ngày",
                    "text_ko": "하루 단 9,900동",
                    "modality": "image_text",
                },
                {
                    "id": "c3",
                    "text_original": "100% chấp thuận — không cần thẩm định",
                    "text_ko": "100% 승인 · 심사 불필요",
                    "modality": "image_text",
                },
                {
                    "id": "c4",
                    "text_original": "Đăng ký ngay hôm nay",
                    "text_ko": "오늘 바로 신청",
                    "modality": "caption",
                },
            ],
        }
    )


_FAKE_ID = "금소법-제99조-가짜조항"


def _mock_findings(claims_json, regulations_json, hallucinated_ids: list[str]) -> FindingsResponse:
    """Deterministic mock for offline smoke tests — JB-본업 대출 시나리오.

    Behavior:
    - First attempt: emits one finding with a fabricated regulation_id so the
      verify node has something to catch (exercises the self-correction loop).
    - Retry attempt: drops the bogus finding, demonstrating loop convergence.
    """
    valid_ids = {r["article_id"] for r in regulations_json}
    findings: list[dict] = []
    if "금소법-제22조-대출성상품-광고" in valid_ids:
        findings.append(
            {
                "claim_id": "c2",
                "severity": "high",
                "regulation_id": "금소법-제22조-대출성상품-광고",
                "issue": "대출이자를 일(日) 단위 금액으로 표시 — 연이자율 환산 시 결코 저렴하지 않은데 저렴해 보이도록 오인 유도",
                "current_text": "Chỉ 9.900 đồng/ngày",
                "suggestion": "‘연이자율 X%, 적용 조건: ...’ 형태로 연 단위 금리와 조건을 동등 가시성으로 명시",
                "confidence": 0.93,
            }
        )
    if "금소법-제21조-부당권유금지" in valid_ids:
        findings.append(
            {
                "claim_id": "c3",
                "severity": "high",
                "regulation_id": "금소법-제21조-부당권유금지",
                "issue": "심사 없이 누구나 승인되는 듯한 단정·과장 표현 — 부당권유 금지에 해당",
                "current_text": "100% chấp thuận — không cần thẩm định",
                "suggestion": "‘심사 결과에 따라 한도·금리·승인 여부가 달라질 수 있습니다’ 등 사실 기반 표현으로 완화",
                "confidence": 0.95,
            }
        )
    if "금소법-제19조-설명의무" in valid_ids:
        findings.append(
            {
                "claim_id": "c1",
                "severity": "medium",
                "regulation_id": "금소법-제19조-설명의무",
                "issue": "외국어(베트남어) 콘텐츠에서 연체이자율·부수비용·심사 조건 등 중요사항 고지가 누락 — 외국인 소비자가 위험을 인지하기 어려움",
                "current_text": "VAY MUA Ô TÔ JB VIỆT NAM",
                "suggestion": "베트남어로 연이자율(APR), 연체이자율(lãi quá hạn), 부수비용(phí), 심사 조건 등을 동등 가시성으로 명시",
                "confidence": 0.72,
            }
        )
    if _FAKE_ID not in (hallucinated_ids or []):
        findings.append(
            {
                "claim_id": "c4",
                "severity": "low",
                "regulation_id": _FAKE_ID,
                "issue": "긴급성 강조로 충동 신청 유도 (가짜 근거 인용 사례)",
                "current_text": "Đăng ký ngay hôm nay",
                "suggestion": "긴급성 강조 표현 완화",
                "confidence": 0.4,
            }
        )
    return FindingsResponse.model_validate({"findings": findings})
