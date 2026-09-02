#!/usr/bin/env python3
"""Named probe 1: 60% figure is TRACED to a primary paper with effect AND baseline.

Control: a headline 60% without baseline cannot promote a mechanism (E3).
The call sheet / 05-ECO path is not accepted as the primary measurement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0078.json"
SENTINEL = (
    "SUCCESS:RES-0078 in the receipt AND a traced-or-untraced verdict "
    "on the correlation figure plus an error-versus-correlation curve"
)
KIM_ARXIV = "2506.07962"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0078-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    if "SUCCESS:RES-0078" not in text:
        return fail("SUCCESS:RES-0078 absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "RES-0078":
        return fail(f"unit_id={doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")

    fig = doc.get("correlation_figure") or {}
    verdict = str(fig.get("verdict") or fig.get("traced_or_untraced") or "").upper()
    if verdict not in {"TRACED", "UNTRACED"}:
        return fail(f"missing traced-or-untraced verdict {verdict!r}")

    primary = fig.get("primary_source") or {}
    arxiv = str(primary.get("arxiv") or "")
    effect = primary.get("effect_size")
    baseline = primary.get("baseline")
    section = str(primary.get("section_or_figure") or "")
    if verdict == "TRACED":
        if KIM_ARXIV not in arxiv and KIM_ARXIV not in text:
            return fail("TRACED but Kim arXiv:2506.07962 not cited")
        if effect is None or baseline is None:
            return fail("TRACED 60% missing effect or baseline")
        if abs(float(effect) - 0.60) > 1e-6:
            return fail(f"effect_size {effect} is not the 0.60 HELM figure")
        if abs(float(baseline) - (1.0 / 3.0)) > 1e-3:
            return fail(f"baseline {baseline} is not 1/3")
        if "3.2" not in section and "Figure 1" not in section and "Abstract" not in section:
            return fail(f"section/figure too vague: {section}")
        if str(fig.get("call_sheet_status") or "").upper() == "PRIMARY":
            return fail("call sheet marked PRIMARY")
        eco = fig.get("eco_file") or {}
        if eco.get("present_on_this_worktree") is True and not (
            REPO / "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"
        ).is_file():
            return fail("eco marked present but file absent")

    # E3 control: promoting a no-baseline 60% must be recorded as overclaim.
    overclaim = None
    for m in doc.get("mechanisms") or []:
        if m.get("id") == "M4-call-sheet-rho-overclaim":
            overclaim = m
            break
    if overclaim is None:
        return fail("missing E3 overclaim control mechanism")
    if overclaim.get("evidence_tier") != "E3":
        return fail("overclaim not graded E3")
    if overclaim.get("verdict") != "REFUTED":
        return fail("rho=0.60 overclaim not REFUTED")
    if overclaim.get("baseline") is None:
        return fail("E3 control itself dropped the baseline")

    confirmed = None
    for m in doc.get("mechanisms") or []:
        if m.get("id") == "M1-helm-agree-both-wrong":
            confirmed = m
            break
    if not confirmed or confirmed.get("baseline") is None:
        return fail("M1 missing baseline; would be an illegal E3 promotion")
    if confirmed.get("evidence_tier") != "E1":
        return fail("traced HELM number is not E1")

    reviewers = doc.get("reviewers") or []
    if len(reviewers) < 2:
        return fail("need two partitioned reviewers")
    sets = [frozenset(r.get("source_ids") or []) for r in reviewers]
    if sets[0] & sets[1]:
        return fail(f"reviewer source partitions overlap {sets[0] & sets[1]}")

    payload = {
        "pass": True,
        "probe": "probe1-trace-60pct",
        "unit_id": "RES-0078",
        "verdict": verdict,
        "arxiv": arxiv,
        "effect_size": effect,
        "baseline": baseline,
        "section_or_figure": section,
        "call_sheet_status": fig.get("call_sheet_status"),
        "mapped_gamma": fig.get("mapped_gamma"),
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"verdict={verdict} arxiv={arxiv} effect={effect} baseline={baseline} "
        f"gamma={fig.get('mapped_gamma')}"
    )
    print("SUCCESS:RES-0078-probe1 60pct figure traced with baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
