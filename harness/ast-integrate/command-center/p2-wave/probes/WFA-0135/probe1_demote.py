#!/usr/bin/env python3
"""Named probe 1: both-states demotion when a flagship e2e test file is deleted.

Signal A: live runner execution of one flagship blueprint produces a parseable
artifact. Signal (this probe): deleting that blueprint's test file flips the
gate from PROVEN/flagship to DEMOTE/not-flagship. A gate that stays green is
not wired.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import demote_experiment  # noqa: E402
from gate import gate  # noqa: E402
from runner import execute_from_estate  # noqa: E402

UNIT = "WFA-0135"
ART = REPO / "command-center/foundry/WFA-0135-quality-tier-evidence-gate-40-flagship-end-to-end-vs.json"
ESTATE = HERE / "estate"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0135" not in json.dumps(doc):
        return fail("sentinel absent")

    live = gate(ESTATE, repo=REPO)
    counts = live["counts"]
    if counts["proven_flagship"] < 40:
        return fail("live proven flagship below floor", counts)
    if counts["blueprints"] != 96:
        return fail("live library size", counts)
    art_counts = doc.get("counts") or {}
    if art_counts.get("proven_flagship") != counts["proven_flagship"]:
        return fail("artifact proven_flagship drifted from live gate", {
            "artifact": art_counts,
            "live": counts,
        })

    live_exec = execute_from_estate(ESTATE, "BP-0001", kind="e2e")
    if not live_exec.get("ok") or live_exec["exit_code"] != 0:
        return fail("live e2e execution", live_exec)
    art_path = Path(live_exec["artifact_path"])
    if not art_path.is_file() or art_path.stat().st_size < 32:
        return fail("live e2e produced no artifact")
    payload = json.loads(art_path.read_text(encoding="utf-8"))
    if payload.get("blueprint_id") != "BP-0001" or payload.get("ok") is not True:
        return fail("live e2e postcondition", payload)

    demo = demote_experiment(ESTATE)
    if not demo.get("ok"):
        return fail("demote experiment stayed green", demo)

    recorded = None
    for t in doc.get("tests") or []:
        if t.get("id") == "both-states-delete-flagship-test":
            recorded = t
            break
    if not recorded or recorded.get("result") != "PASS":
        return fail("artifact missing both-states PASS", recorded)

    out = {
        "pass": True,
        "probe": "probe1-demote",
        "unit_id": UNIT,
        "live_proven_flagship": counts["proven_flagship"],
        "live_e2e_run_id": live_exec["run_id"],
        "demote": demo,
        "computed_not_asserted": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"demote_ok={demo['ok']} {demo['blueprint_id']} "
        f"{demo['baseline_proven_flagship']}->{demo['after_proven_flagship']}"
    )
    print("SUCCESS:WFA-0135-probe1 both-states demote")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
