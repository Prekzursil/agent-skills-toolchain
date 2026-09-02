#!/usr/bin/env python3
"""Named probe 1: correctness vs expensive AND measured work reduction (both required).

Re-runs the live progressive fusion on the matched benchmark set. Failure to meet
either declared bar is REJECT. Receipt numbers must match this live recompute.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fusion import (  # noqa: E402
    MAX_MISMATCH_RATE,
    MIN_WORK_REDUCTION,
    compose_progressive,
    evaluate,
    planted_mismatch_is_rejected,
)

ART = REPO / "command-center/receipts/IMP-0188.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0188-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt unparseable:{exc}")
    if not isinstance(doc, dict):
        return fail("receipt not an object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if "SUCCESS:IMP-0188" not in text:
        return fail("sentinel-absent")

    wf = compose_progressive()
    report = evaluate(wf)
    payload = report.as_dict()

    if report.verdict != "PASS":
        print(json.dumps({k: payload[k] for k in ("verdict", "reason", "n_cases", "work") if k in payload}, indent=2))
        return fail(f"acceptance {report.verdict}:{report.reason}")
    if report.mismatch_rate > MAX_MISMATCH_RATE:
        return fail(f"mismatch_rate={report.mismatch_rate}")
    if report.reduction_ratio < MIN_WORK_REDUCTION:
        return fail(f"reduction_ratio={report.reduction_ratio}")
    if report.mismatches != 0:
        return fail(f"mismatches={report.mismatches}")

    p_sum = sum(e["work_units"] for e in report.progressive_ledger)
    e_sum = sum(e["work_units"] for e in report.expensive_ledger)
    if p_sum != report.progressive_work or e_sum != report.expensive_work:
        return fail("work not equal to ledger entry sum")
    if report.progressive_work >= report.expensive_work:
        return fail("no measured work reduction")

    rec_c = doc.get("correctness") or {}
    rec_w = doc.get("work") or {}
    if rec_c.get("mismatches_vs_expensive") != report.mismatches:
        return fail("receipt correctness stale vs live")
    if rec_w.get("estimated") is not False:
        return fail("receipt work is estimated, not ledger-summed")
    if rec_w.get("source") != "budget_ledger_sum":
        return fail("receipt work source is not budget_ledger_sum")
    if rec_w.get("progressive_ledger_total") != report.progressive_work:
        return fail("receipt progressive work stale vs live ledger")
    if rec_w.get("expensive_only_ledger_total") != report.expensive_work:
        return fail("receipt expensive work stale vs live ledger")

    if not planted_mismatch_is_rejected():
        return fail("detector silent: never-escalate was not REJECT")

    summary = {
        "probe": "probe1-correctness-work",
        "unit_id": "IMP-0188",
        "pass": True,
        "n_cases": report.n_cases,
        "mismatches_vs_expensive": report.mismatches,
        "mismatch_rate": report.mismatch_rate,
        "progressive_ledger_total": report.progressive_work,
        "expensive_only_ledger_total": report.expensive_work,
        "reduction_ratio": report.reduction_ratio,
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
    print("SUCCESS:IMP-0188-probe1 correctness-within-tolerance and measured-work-reduction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
