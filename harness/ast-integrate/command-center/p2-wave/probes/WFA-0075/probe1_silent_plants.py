#!/usr/bin/env python3
"""Probe 1: three planted silent disposition changes are all caught.

Negative control: the silent pair is the state the monitor is meant to
reject. Mutants that drop the reason gate or the evidence-field gate each
miss one of the three plants.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import monitor as M  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0075-disposition-drift-monitor.json"
FIX = HERE / "fixtures"
PLANTED = [
    "wf-silent-both",
    "wf-silent-reason-hole",
    "wf-silent-evidence-hole",
]


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0075-probe1 {msg}")
    return 1


def main() -> int:
    v1, v2, mp = FIX / "v1_baseline.json", FIX / "v2_silent.json", FIX / "id_migration_map.json"
    live = M.compare_paths(v1, v2, mp)
    ids = live["silent_drift_ids"]
    print(
        "verbatim_fire fixture=v2_silent "
        f"fail={live['fail']} silent_drift_ids={ids} "
        f"documented_ids={live['documented_ids']}"
    )
    if not live["fail"]:
        return fail("silent pair did not fail")
    if sorted(ids) != sorted(PLANTED):
        return fail(f"planted ids mismatch got={ids}")

    by_id = {f["canonical_id"]: f for f in live["findings"]}
    both = by_id["wf-silent-both"]
    if both["evidence_fields_changed"]:
        return fail("silent-both must have empty evidence delta")
    if both["has_reason"]:
        return fail("silent-both must have no reason")
    hole_r = by_id["wf-silent-reason-hole"]
    if hole_r["evidence_fields_changed"] != ["named_probe"]:
        return fail(f"reason-hole fields={hole_r['evidence_fields_changed']}")
    if hole_r["has_reason"]:
        return fail("reason-hole unexpectedly has a reason")
    hole_e = by_id["wf-silent-evidence-hole"]
    if hole_e["evidence_fields_changed"]:
        return fail("evidence-hole must have empty evidence delta")
    if not hole_e["has_reason"]:
        return fail("evidence-hole must keep its written reason")

    if by_id["wf-stable-merge"]["kind"] != M.KIND_UNCHANGED:
        return fail("stable-merge was flagged")
    if by_id["wf-doc-smoke"]["fail"] or by_id["wf-doc-preserve"]["fail"]:
        return fail("documented ids were flagged on the silent pair")

    skip_reason = M.compare_paths(v1, v2, mp, require_reason=False)
    skip_ev = M.compare_paths(v1, v2, mp, require_evidence_delta=False)
    print(
        f"mutant-skip-reason missed={skip_reason['silent_drift_ids']} "
        f"mutant-skip-evidence missed={skip_ev['silent_drift_ids']}"
    )
    if "wf-silent-reason-hole" in skip_reason["silent_drift_ids"]:
        return fail("reason-hole mutant still caught reason-hole; mutant is inert")
    if "wf-silent-both" not in skip_reason["silent_drift_ids"]:
        return fail("reason-hole mutant must still catch silent-both")
    if "wf-silent-evidence-hole" in skip_ev["silent_drift_ids"]:
        return fail("evidence-hole mutant still caught evidence-hole; mutant is inert")
    if "wf-silent-both" not in skip_ev["silent_drift_ids"]:
        return fail("evidence-hole mutant must still catch silent-both")

    if not ART.is_file():
        return fail(f"artifact missing {ART}")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {st}")
    if "SUCCESS:WFA-0075" not in text:
        return fail("sentinel absent from artifact")
    recorded = doc.get("silent_pair") or {}
    rec_ids = list(recorded.get("silent_drift_ids") or [])
    if sorted(rec_ids) != sorted(PLANTED):
        return fail(f"artifact silent_drift_ids={rec_ids}")
    if recorded.get("fail") is not True:
        return fail("artifact silent_pair.fail is not true")

    print(
        "NEGATIVE-CONTROL v2_silent: check silent_drift_ids catch all three "
        "plants (both-missing, reason-hole, evidence-hole); "
        f"observed ids={ids} fail={live['fail']}"
    )
    print("SUCCESS:WFA-0075-probe1 three planted silent changes caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
