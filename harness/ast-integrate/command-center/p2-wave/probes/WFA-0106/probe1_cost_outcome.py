#!/usr/bin/env python3
"""Probe 1: paired cost and outcome vs always-top-rung.

Live re-run. A cheaper ladder with worse labels is REJECT. A ladder that
escalates on every input is a more expensive top rung with extra steps.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import progressive as P  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0106-fusion-progressive.json"
UNIT = "WFA-0106"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable:{exc}")
    if not isinstance(doc, dict):
        return fail("artifact not an object")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:WFA-0106" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    wf = P.compose_progressive()
    report = P.evaluate(wf)
    if report.verdict != "PASS":
        return fail(f"live acceptance {report.verdict}:{report.reason}")
    if report.mismatches != 0:
        return fail(f"mismatches={report.mismatches}")
    if report.mismatch_rate > P.MAX_MISMATCH_RATE:
        return fail(f"mismatch_rate={report.mismatch_rate}")
    if report.n_cases < P.MIN_CASES:
        return fail(f"n_cases={report.n_cases}")
    if report.always_escalates:
        return fail("ladder escalates on every input")
    p_sum = sum(e["work_units"] for e in report.progressive_ledger)
    e_sum = sum(e["work_units"] for e in report.expensive_ledger)
    if p_sum != report.progressive_work or e_sum != report.expensive_work:
        return fail("work not equal to ledger entry sum")
    if report.progressive_work >= report.expensive_work:
        return fail("no measured work reduction")
    if report.reduction_ratio < P.MIN_REDUCTION:
        return fail(f"reduction_ratio={report.reduction_ratio}")
    work = (doc.get("cost_vs_outcome") or {}).get("work") or {}
    if work.get("estimated") is not False:
        return fail("artifact work is estimated, not ledger-summed")
    if work.get("source") != "budget_ledger_sum":
        return fail("artifact work source is not budget_ledger_sum")
    if work.get("progressive_ledger_total") != report.progressive_work:
        return fail("artifact progressive work stale vs live ledger")
    if work.get("expensive_only_ledger_total") != report.expensive_work:
        return fail("artifact expensive work stale vs live ledger")
    corr = (doc.get("cost_vs_outcome") or {}).get("correctness") or {}
    if corr.get("mismatches_vs_expensive") != report.mismatches:
        return fail("artifact correctness stale vs live")

    controls = P.planted_controls()
    if not controls["never_escalate_rejected_for_correctness"]:
        return fail("never-escalate mutant was not REJECT on correctness")
    if not controls["always_escalate_more_expensive"]:
        return fail("always-escalate mutant was not more expensive than top rung")
    if controls["always_escalate_verdict"] != "REJECT":
        return fail("always-escalate mutant was not REJECT")
    if not controls["good_pass"]:
        return fail("good-state evaluate is not PASS")

    pred = wf.predicate.spec()
    if pred.get("self_assessment") is not False:
        return fail("adequacy predicate is a self-assessment")

    summary = {
        "probe": "probe1-cost-outcome",
        "unit_id": UNIT,
        "pass": True,
        "n_cases": report.n_cases,
        "mismatches_vs_expensive": report.mismatches,
        "mismatch_rate": report.mismatch_rate,
        "progressive_ledger_total": report.progressive_work,
        "expensive_only_ledger_total": report.expensive_work,
        "reduction_ratio": report.reduction_ratio,
        "always_escalates": report.always_escalates,
        "work_source": "budget_ledger_sum",
        "estimated": False,
        "verdict": report.verdict,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"correctness mismatches={report.mismatches}/{report.n_cases} "
        f"work {report.progressive_work}<{report.expensive_work} "
        f"reduction={report.reduction_ratio:.4f}"
    )
    print(
        "SUCCESS:WFA-0106-probe1 equal-outcome and measured-work-reduction "
        "vs always-top-rung"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
