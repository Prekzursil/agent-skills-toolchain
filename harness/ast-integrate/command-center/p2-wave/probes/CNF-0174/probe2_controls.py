#!/usr/bin/env python3
"""Probe 2: both-states, known-broken averaging, production census.

Mechanically different from probe 1: does not score the disagreement fixture.
It (a) runs agreeing subcouncils and forbids spurious escalation, (b) disables
the split detector and asserts the split-surface test goes red, (c) censuses
production nested.py by path existence rather than by invoking fan_in.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import fanin as F  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0174.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0174-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("confirmation artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0174":
        return fail("unit_id")
    src = doc.get("source_probe") or {}
    ver = doc.get("verifier_probe") or {}
    if not src or not ver:
        return fail("source_probe or verifier_probe missing")
    if src.get("fingerprint") == ver.get("fingerprint"):
        return fail("same-probe-rerun: fingerprints identical")
    if src.get("command") == ver.get("command"):
        return fail("source and verifier commands identical")

    agree = F.fan_in(S.agree_complete(), split_detector=True, attempt=1)
    if agree.get("split_surfaced"):
        return fail("agreeing councils produced a spurious split")
    if agree.get("escalation") is not None:
        return fail(f"spurious escalation {agree.get('escalation')}")
    if agree.get("parent_completion") != "COMPLETE":
        return fail(f"agree parent {agree.get('parent_completion')}")
    if agree.get("parent_verdict") != "COMPLETE":
        return fail("agree parent_verdict")

    agree_b = F.fan_in(S.agree_blocked(), split_detector=True, attempt=1)
    if agree_b.get("split_surfaced") or agree_b.get("escalation") is not None:
        return fail("agree-blocked spuriously escalated")
    if agree_b.get("parent_completion") != "BLOCKED":
        return fail(f"agree-blocked parent {agree_b.get('parent_completion')}")

    split_children = S.split_two()
    on = F.fan_in(split_children, split_detector=True, attempt=1)
    off = F.fan_in(split_children, split_detector=False, attempt=1)
    surface_test_on = bool(on.get("split_surfaced") and on.get("parent_verdict") == "SPLIT")
    surface_test_off = bool(off.get("split_surfaced") and off.get("parent_verdict") == "SPLIT")
    if not surface_test_on:
        return fail("control baseline: detector-on did not surface split")
    if surface_test_off:
        return fail("known-broken: detector-off still surfaced split (control did not go red)")
    if not off.get("averaged"):
        return fail("detector-off did not average")
    if off.get("minority_reports"):
        return fail("detector-off kept minority reports")
    if off.get("parent_completion") != "COMPLETE":
        return fail("detector-off should majority-mean to COMPLETE")
    # Midpoint must be visible on the broken path and forbidden on the good path.
    if off.get("mean_completion") is None:
        return fail("broken path hid its mean")
    if on.get("mean_completion") is not None:
        return fail("good path emitted a midpoint mean")
    off_ids = {r["completion"] for r in off.get("subcouncil_verdicts") or []}
    if off_ids != {"COMPLETE"}:
        return fail(f"broken path did not erase split; completions={off_ids}")

    live_census = C.census()
    art_census = doc.get("census") or {}
    if live_census.get("production_nested_present") != art_census.get("production_nested_present"):
        return fail("census mismatch vs artifact")
    if live_census.get("production_nested_present"):
        return fail("unexpected production nested.py; re-bind object under test")
    nested = REPO / "tools/council/topology/nested.py"
    if nested.is_file():
        return fail("nested.py appeared on disk but census missed it")

    prod_claim = next(
        (c for c in doc.get("claims") or [] if c.get("id") == "C-PRODUCTION-NESTED"),
        None,
    )
    if not prod_claim or prod_claim.get("verdict") != "REFUTED":
        return fail("artifact overclaims production nested fan-in")
    if str(doc.get("verdict") or "").upper() == "CONFIRMED":
        return fail("record-level CONFIRMED while production nested is absent")
    if str(doc.get("verdict") or "").upper() in {"BLOCKED", "FAILED"}:
        return fail(f"record verdict {doc.get('verdict')}")

    fc = live_census.get("failure_modes_fc11343") or {}
    if not fc.get("names_fc11343"):
        return fail("FC-11343 snippet missing from FAILURE-MODES.json")

    payload = {
        "agree_complete_no_escalation": True,
        "agree_blocked_no_escalation": True,
        "known_broken_went_red": True,
        "mean_completion_broken": off.get("mean_completion"),
        "production_nested_present": False,
        "pass": True,
        "probe": "probe2-controls",
        "unit_id": "CNF-0174",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"agree_ok=True broken_red=True nested_present=False "
        f"mean={off.get('mean_completion')}"
    )
    print("SUCCESS:CNF-0174-probe2 both-states and known-broken averaging control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
