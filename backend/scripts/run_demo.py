"""Day 1 demo CLI: run one sample card through the full vertical slice.

Usage:
    # use first card in data/samples/
    python -m scripts.run_demo

    # explicit path
    python -m scripts.run_demo path/to/card.png

    # offline mode (no OpenAI calls, uses mocked GPT responses)
    COMPLIANCELENS_MOCK_LLM=1 python -m scripts.run_demo
"""
from __future__ import annotations

import sys
from pathlib import Path

# Force UTF-8 stdout so Windows consoles (cp949 by default) can print
# Vietnamese diacritics and the report's emoji severity markers.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app import config
from app.agent.graph import build_graph
from app.agent.state import AgentState


def _resolve_sample(argv: list[str]) -> Path:
    if len(argv) > 1:
        p = Path(argv[1])
        if not p.exists():
            print(f"file not found: {p}", file=sys.stderr)
            sys.exit(2)
        return p
    candidates = sorted(config.SAMPLES_DIR.glob("*.png")) + sorted(
        config.SAMPLES_DIR.glob("*.jpg")
    )
    if not candidates:
        print(
            f"No sample images in {config.SAMPLES_DIR}.\n"
            f"Generate the placeholder:  python -m scripts.make_dummy_sample",
            file=sys.stderr,
        )
        sys.exit(2)
    return candidates[0]


def main(argv: list[str]) -> int:
    sample = _resolve_sample(argv)

    init_state: AgentState = {
        "content_ref": str(sample),
        "content_type": "card",
        "language": "",      # ingest will fill if empty
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

    print(f"[demo] running ComplianceLens vertical slice on: {sample}")
    print(f"[demo] mock LLM mode: {config.MOCK_LLM}")
    print("-" * 72)

    app = build_graph()
    final_state: AgentState = app.invoke(init_state)

    print("\n[demo] graph: ingest → retrieve → assess → verify (↺ on hallucination) → generate")
    print(f"[demo] claims:        {len(final_state.get('claims', []))}")
    print(f"[demo] regulations:   {len(final_state.get('regulations', []))}")
    print(f"[demo] findings:      {len(final_state.get('findings', []))}")
    print(f"[demo] verify_passed: {final_state.get('verify_passed')}")
    print(f"[demo] retry_count:   {final_state.get('retry_count', 0)}")
    halluc = final_state.get("hallucinated_ids", [])
    if halluc:
        print(f"[demo] hallucinated:  {halluc}")
    print("-" * 72)
    print()

    report = final_state.get("report_markdown") or "(no report generated)"
    print(report)

    # Persist alongside the sample for inspection.
    out = sample.with_suffix(".report.md")
    out.write_text(report, encoding="utf-8")
    print(f"\n[demo] report saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
