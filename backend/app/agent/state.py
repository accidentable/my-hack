"""Agent state and structured-output schemas.

The TypedDicts (Claim, Regulation, Finding, ReviewInput, AgentState) are taken
verbatim from the architecture doc §4 — they are the single source of truth
that LangGraph passes between nodes.

The Pydantic models at the bottom (ClaimsResponse, FindingsResponse) are used
only at the OpenAI Structured-Outputs boundary so that GPT-4o emits valid JSON.
We convert to/from the TypedDicts at the node level.
"""
from __future__ import annotations

from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# TypedDicts — architecture §4 (verbatim)
# -----------------------------------------------------------------------------


class Claim(TypedDict):
    id: str
    text_original: str
    text_ko: str
    modality: Literal["image_text", "caption", "speech", "graphic"]


class Regulation(TypedDict):
    article_id: str
    title: str
    snippet: str


class Finding(TypedDict):
    claim_id: str
    severity: Literal["high", "medium", "low"]
    source: Literal["rule", "llm"]
    regulation_id: str
    issue: str
    current_text: str
    suggestion: str
    confidence: float
    verified: bool


class ReviewInput(TypedDict):
    finding_id: str
    decision: Literal["approve", "reject"]
    comment: str


class AgentState(TypedDict, total=False):
    # Input
    content_ref: str
    content_type: Literal["card", "poster", "video"]
    language: str
    # Stage outputs
    claims: list[Claim]
    regulations: list[Regulation]
    findings: list[Finding]
    verify_passed: bool
    retry_count: int
    # Day 2: self-correction. verify collects article_ids it couldn't verify so
    # the next assess pass can be told NOT to cite them again.
    hallucinated_ids: list[str]
    report_markdown: Optional[str]
    review_inputs: list[ReviewInput]
    final_report_markdown: Optional[str]
    stage: Literal[
        "ingest", "retrieve", "assess", "verify", "generate", "review", "done"
    ]


# -----------------------------------------------------------------------------
# Structured-Outputs schemas (Pydantic) — used at OpenAI API boundary only
# -----------------------------------------------------------------------------


class ClaimOut(BaseModel):
    id: str = Field(description="Unique id within this content, e.g. 'c1', 'c2'")
    text_original: str = Field(description="Exact text as it appears (source language)")
    text_ko: str = Field(description="Korean translation for human reviewer")
    modality: Literal["image_text", "caption", "speech", "graphic"]


class ClaimsResponse(BaseModel):
    language: str = Field(description="Primary language code, e.g. 'vi', 'ko', 'th'")
    claims: list[ClaimOut]


class FindingOut(BaseModel):
    claim_id: str = Field(description="The id of the claim this finding refers to")
    severity: Literal["high", "medium", "low"]
    regulation_id: str = Field(
        description="MUST be one of the article_id values present in the input regulations list."
    )
    issue: str = Field(description="What is wrong, in Korean")
    current_text: str = Field(description="Exact problematic text quoted from the claim (original language)")
    suggestion: str = Field(description="Rewritten text that would pass review")
    confidence: float = Field(ge=0.0, le=1.0)


class FindingsResponse(BaseModel):
    findings: list[FindingOut]
