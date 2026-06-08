"""YAML rule engine.

Two rule types are supported on Day 1:

- ``must_contain_any``: violation = NONE of the patterns appears anywhere in the
  combined claim text. (e.g. mandatory disclosure missing)
- ``must_not_contain_any``: violation = ANY of the patterns appears in some
  claim's text. (e.g. forbidden guarantee phrase used)

Each rule that fires produces one or more Findings. Day 2 expands the rule
vocabulary (regex, image-region checks, etc).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from app import config
from app.agent.state import Claim, Finding


@dataclass(frozen=True)
class _Rule:
    id: str
    regulation_id: str
    check_type: str
    patterns: tuple[str, ...]
    on_severity: str
    on_issue: str
    on_suggestion: str
    # Optional gating: rule only fires if at least one of these patterns
    # appears somewhere in the claim haystack. Used so that loan-specific
    # rules don't fire on deposit ads (and vice versa).
    applies_when: tuple[str, ...]


def _load_rules() -> list[_Rule]:
    if not config.RULES_PATH.exists():
        return []
    with config.RULES_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []

    rules: list[_Rule] = []
    for r in raw:
        check = r["check"]
        check_type = check["type"]
        outcome_key = "on_missing" if check_type == "must_contain_any" else "on_hit"
        outcome = r.get(outcome_key, {})

        applies = r.get("applies_when") or {}
        applies_patterns: tuple[str, ...] = ()
        if applies:
            if applies.get("type") == "any_claim_contains":
                applies_patterns = tuple(applies.get("patterns", []))

        rules.append(
            _Rule(
                id=r["id"],
                regulation_id=r["regulation_id"],
                check_type=check_type,
                patterns=tuple(check.get("patterns", [])),
                on_severity=outcome.get("severity", "medium"),
                on_issue=outcome.get("issue", ""),
                on_suggestion=outcome.get("suggestion", ""),
                applies_when=applies_patterns,
            )
        )
    return rules


def _rule_applies(rule: _Rule, haystack_lower: str) -> bool:
    """True if the rule is in scope for this content.

    If no ``applies_when`` patterns are configured, the rule applies to
    everything (current default for non-product-specific rules).
    """
    if not rule.applies_when:
        return True
    return any(p.lower() in haystack_lower for p in rule.applies_when)


def _claim_haystack(claims: list[Claim]) -> str:
    return " \n ".join(c["text_original"] + " " + c.get("text_ko", "") for c in claims)


def _find_hits(pattern: str, claims: list[Claim]) -> list[Claim]:
    p = pattern.lower()
    return [c for c in claims if p in (c["text_original"] + " " + c.get("text_ko", "")).lower()]


def evaluate(claims: list[Claim]) -> list[Finding]:
    """Run every rule against the claim list, return findings."""
    findings: list[Finding] = []
    rules = _load_rules()
    haystack = _claim_haystack(claims).lower()

    for rule in rules:
        # Skip rules that don't apply to this content type (e.g. loan rules
        # on a deposit ad). Without this gate, must_contain_any rules
        # fire on any unrelated content because the loan disclosure
        # keywords are trivially absent.
        if not _rule_applies(rule, haystack):
            continue

        if rule.check_type == "must_contain_any":
            present = any(p.lower() in haystack for p in rule.patterns)
            if present:
                continue
            # Violation: required text missing. Attach to a synthetic claim_id
            # since there is no specific offending claim.
            findings.append(
                Finding(
                    claim_id="__document__",
                    severity=_severity(rule.on_severity),
                    source="rule",
                    regulation_id=rule.regulation_id,
                    issue=rule.on_issue,
                    current_text="(해당 고지 문구 없음)",
                    suggestion=rule.on_suggestion,
                    confidence=1.0,
                    verified=False,
                )
            )
        elif rule.check_type == "must_not_contain_any":
            # One finding per (rule, claim) pair, regardless of how many of the
            # rule's patterns happen to match. Without this dedup we get
            # combinatorial duplicate findings (e.g. both "an toàn 100%" and
            # "100% 안전" matching the same claim → 2 identical findings).
            seen_claims: set[str] = set()
            for pattern in rule.patterns:
                for hit in _find_hits(pattern, claims):
                    if hit["id"] in seen_claims:
                        continue
                    seen_claims.add(hit["id"])
                    findings.append(
                        Finding(
                            claim_id=hit["id"],
                            severity=_severity(rule.on_severity),
                            source="rule",
                            regulation_id=rule.regulation_id,
                            issue=rule.on_issue,
                            current_text=hit["text_original"],
                            suggestion=rule.on_suggestion,
                            confidence=1.0,
                            verified=False,
                        )
                    )
        else:
            # Unknown rule type — skip silently in Day 1; surface as warning later.
            continue

    return findings


def _severity(s: str) -> Any:
    if s in ("high", "medium", "low"):
        return s
    return "medium"
