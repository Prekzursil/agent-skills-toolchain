#!/usr/bin/env python3
"""Named probe 2: partitioned reviewers + widely-cited correction control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catalog as C  # noqa: E402
import grade as G  # noqa: E402

ART = REPO / "command-center/research/RES-0077.json"
SENTINEL = (
    "SUCCESS:RES-0077 in the receipt AND a bias-by-correction table with "
    "per-row effect sizes and an explicit grade"
)


def main() -> int:
    part = G.partition_ok()
    print(
        f"partition ok={part['ok']} A={len(part.get('reviewer_a_rows') or [])} "
        f"B={len(part.get('reviewer_b_rows') or [])} unassigned={part.get('unassigned')}"
    )
    if not part["ok"]:
        print("FAILED:RES-0077-probe2 reviewer partition failed")
        print(json.dumps(part, indent=2, default=str)[:4000])
        return 1
    if C.REVIEWER_A_SOURCES & C.REVIEWER_B_SOURCES:
        print("FAILED:RES-0077-probe2 source sets overlap")
        return 1

    ctrl = G.both_states_all_measured_effective_control()
    print(
        f"widely_cited_control live_ok={ctrl['live_ok']} "
        f"poisoned_ok={ctrl['poisoned_ok']} hits={ctrl['live_hits']}"
    )
    if not ctrl["ok"]:
        print("FAILED:RES-0077-probe2 widely-cited control did not discriminate")
        print(json.dumps(ctrl, indent=2, default=str)[:4000])
        return 1

    if not ART.is_file():
        print("FAILED:RES-0077-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0077-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:RES-0077-probe2 self-declared {doc.get('state')}")
        return 1

    rev = doc.get("reviewer") or {}
    if not rev.get("independent") or not rev.get("partitioned"):
        print("FAILED:RES-0077-probe2 reviewer block missing independent+partitioned")
        return 1
    if rev.get("verdict") != "PASS":
        print("FAILED:RES-0077-probe2 reviewer verdict not PASS")
        return 1
    reviewers = rev.get("reviewers") or []
    if len(reviewers) != 2:
        print("FAILED:RES-0077-probe2 expected two partitioned reviewers")
        return 1
    src_a = set(reviewers[0].get("sources") or [])
    src_b = set(reviewers[1].get("sources") or [])
    if src_a & src_b:
        print("FAILED:RES-0077-probe2 artifact reviewer sources overlap")
        return 1
    if src_a != set(C.REVIEWER_A_SOURCES) or src_b != set(C.REVIEWER_B_SOURCES):
        print("FAILED:RES-0077-probe2 artifact reviewer sources drifted from catalog")
        return 1

    table = doc.get("bias_by_correction_table") or []
    live_ctrl = G.widely_cited_outside_measured(table)
    if not live_ctrl["ok"]:
        print("FAILED:RES-0077-probe2 artifact lost the widely-cited outside-measured rows")
        print(live_ctrl)
        return 1
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    t2 = tests.get("T-widely-cited-outside-measured-effective")
    if not t2 or t2.get("result") != "PASS":
        print("FAILED:RES-0077-probe2 artifact test T-widely-cited not PASS")
        return 1
    print(
        f"disjoint=True widely_cited_outside={[h['correction_id'] for h in live_ctrl['rows']]}"
    )
    print("SUCCESS:RES-0077-probe2 partitioned reviewers and widely-cited control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
