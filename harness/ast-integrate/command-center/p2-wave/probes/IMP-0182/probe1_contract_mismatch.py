#!/usr/bin/env python3
"""Probe 1: contract mismatch refused; matching contract accepted (both-states).

Also proves the check runs BEFORE emit: shipped trace is
contract-check then refuse/emit, and the emit-first mutant still carries a
fusion object on mismatch (detector is live).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    DONOR_INDEX,
    HOST_INDEX,
    host_workflow,
    matching_donor,
    mismatch_donor,
    successor_mismatch_donor,
)
from stage_splice import emit_first_mutant, stage_splice  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0182.json"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0182-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"receipt self-declared {doc.get('state')}")
    if "SUCCESS:IMP-0182" not in text:
        return _fail("sentinel absent")

    host = host_workflow()
    match = matching_donor()
    bad = mismatch_donor()
    bad_succ = successor_mismatch_donor()

    good = stage_splice(host, match, HOST_INDEX, DONOR_INDEX)
    if good.get("status") != "emitted" or good.get("fusion") is None:
        return _fail(f"matching contract was refused: {good.get('reason')}")
    if good.get("trace") != ["contract-check", "emit"]:
        return _fail(f"matching trace {good.get('trace')!r} is not check-then-emit")

    refused = stage_splice(host, bad, HOST_INDEX, DONOR_INDEX)
    if refused.get("status") != "refused" or refused.get("reason") != "contract-mismatch":
        return _fail(f"input mismatch not refused: {refused.get('status')} {refused.get('reason')}")
    if refused.get("fusion") is not None:
        return _fail("mismatch still emitted a fusion object")
    if refused.get("trace") != ["contract-check", "refuse"]:
        return _fail(f"mismatch trace {refused.get('trace')!r} is not check-then-refuse")
    contracts = (refused.get("preconditions") or {}).get("contracts") or {}
    if contracts.get("input_cover_ok") is not False:
        return _fail("input mismatch did not fail input cover")

    refused_out = stage_splice(host, bad_succ, HOST_INDEX, DONOR_INDEX)
    if refused_out.get("status") != "refused" or refused_out.get("fusion") is not None:
        return _fail("successor mismatch not refused")
    out_c = (refused_out.get("preconditions") or {}).get("contracts") or {}
    if out_c.get("output_cover_ok") is not False:
        return _fail("successor mismatch did not fail output cover")

    mutant = emit_first_mutant(host, bad, HOST_INDEX, DONOR_INDEX)
    if mutant.get("fusion") is None:
        return _fail("emit-first mutant did not produce a fusion (detector silent)")
    if "emit" not in (mutant.get("trace") or []) or (mutant.get("trace") or [None])[0] != "emit":
        return _fail(f"mutant trace {mutant.get('trace')!r} did not emit first")
    if mutant.get("status") != "refused":
        return _fail("mutant did not later refuse; control is not both-states")

    summary = {
        "probe": "probe1-contract-mismatch",
        "unit_id": "IMP-0182",
        "pass": True,
        "matching_accepted": True,
        "input_mismatch_refused": True,
        "successor_mismatch_refused": True,
        "shipped_fusion_none_on_mismatch": True,
        "mutant_fusion_present_on_mismatch": True,
        "shipped_trace_good": good.get("trace"),
        "shipped_trace_bad": refused.get("trace"),
        "mutant_trace": mutant.get("trace"),
        "missing_inputs": contracts.get("missing_inputs"),
        "missing_outputs": out_c.get("missing_outputs"),
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0182-probe1 contract mismatch refused; matching accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
