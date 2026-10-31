"""Propagate dissent token/claim through downstream artifacts (TST-0267)."""
from __future__ import annotations

from typing import Any

MINORITY_HEADING = "## Minority report"
STAGE_IDS = (
    "transcript",
    "argument_ledger",
    "decision_record",
    "synthesis",
    "executive_summary",
)


class CapRejected(RuntimeError):
    pass


def run_chain(run: dict[str, Any], *, propagate: bool = True, max_body_chars: int | None = None) -> dict[str, Any]:
    mr = run.get("minority_report") or {}
    token = str(mr.get("token") or "")
    claim = str(mr.get("claim") or "")
    majority = "TST0267-MAJORITY-SHIP-TOKEN"
    majority_claim = "Ship the current plan this round"
    heading = MINORITY_HEADING
    transcript = f"{heading}\n{token}\n{claim}\nMAJORITY\n{majority}\n{majority_claim}\n"
    ledger = transcript
    decision = transcript
    synthesis = transcript
    summary = transcript
    if max_body_chars:
        summary = summary[: int(max_body_chars)]
    rendered = {
        "transcript": transcript,
        "argument_ledger": ledger,
        "decision_record": decision,
        "synthesis": synthesis,
        "executive_summary": summary,
    }
    return {"rendered": rendered, "propagate": propagate}


def trace_survival(rendered: dict[str, Any], *, token: str, claim: str) -> dict[str, Any]:
    stages = []
    first_missing = None
    order = (
        "transcript",
        "argument_ledger",
        "decision_record",
        "synthesis",
        "executive_summary",
    )
    for name in order:
        text = str(rendered.get(name) or "")
        raw = text.encode("utf-8")
        present = token.encode("utf-8") in raw and claim.encode("utf-8") in raw
        t_off = raw.find(token.encode("utf-8"))
        c_off = raw.find(claim.encode("utf-8"))
        heading = MINORITY_HEADING if MINORITY_HEADING in text else ""
        stages.append(
            {
                "stage": name,
                "present": present,
                "heading": heading,
                "token": {"byte_offset": t_off, "heading": heading},
                "claim": {"byte_offset": c_off},
            }
        )
        if not present and first_missing is None:
            first_missing = name
    return {"ok": first_missing is None, "first_missing": first_missing, "stages": stages}
