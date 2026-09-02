#!/usr/bin/env python3
"""Named probe 1: differential equivalence, two real units per rail.

Signal 1 is sha256 of the portable payload. Signal 2 is the portable key-set.
Disagreement is BLOCKED. Also checks both-direction unwrap and refuse-drop.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from differential import run_all  # noqa: E402
from view import plan as domain  # noqa: E402

ART = REPO / "command-center/phase3/A6/MIGRATION.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0042-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("migration artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0042":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:ARC-0042" not in json.dumps(doc):
        return fail("sentinel absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live = run_all(REPO, HERE)
    if live["disagree"]:
        print(json.dumps(live["disagree"], indent=2, default=str)[:2000])
        return fail("signal disagreement (BLOCKED, not picked)")
    if live["failed"]:
        print(json.dumps(live["failed"], indent=2, default=str)[:2000])
        return fail("payload or remainder not preserved")
    rows = live["rows"]
    if len(rows) != 6:
        return fail(f"sample_size={len(rows)} want=6")
    if len({r["rail_id"] for r in rows}) != 3:
        return fail("rails_checked != 3")
    for rid in live["rails"]:
        n = sum(1 for r in rows if r["rail_id"] == rid)
        if n != 2:
            return fail(f"{rid} units={n} want=2")
    identical = [r for r in rows if r["byte_identical_payload"]]
    if len(identical) != 6:
        return fail(f"byte_identical_payload={len(identical)} want=6")
    queued = live["queued"]
    if not queued:
        return fail("no remainder queued")
    neg = live["negative_control"]
    if not neg.get("pass") or not neg.get("refused"):
        print(json.dumps(neg, indent=2))
        return fail("negative control did not refuse drop-remainder")
    faf = live["fire_and_forget"]
    if not faf.get("pass") or not faf.get("refused"):
        print(json.dumps(faf, indent=2))
        return fail("fire-and-forget was not refused (would be a REPLACE of a working refusal)")

    payload = domain(doc)
    recorded = {
        (r["rail_id"], r["unit_id"]): r for r in (payload.get("sample") or [])
    }
    for rec in rows:
        got = recorded.get((rec["rail_id"], rec["unit_id"]))
        if not got:
            return fail(f"artifact missing sample {rec['rail_id']}/{rec['unit_id']}")
        if got.get("payload_sha256") != rec["payload_sha256"]:
            return fail(f"payload sha drift {rec['rail_id']}/{rec['unit_id']}")
        if bool(got.get("byte_identical_payload")) != rec["byte_identical_payload"]:
            return fail(f"byte_identical drift {rec['rail_id']}/{rec['unit_id']}")
        if bool(got.get("both_directions")) is not True:
            return fail(f"both_directions missing {rec['rail_id']}/{rec['unit_id']}")

    tests = (payload.get("tests") or {}).get("differential_equivalence") or {}
    if tests.get("files_checked") != 6 or tests.get("byte_identical_payload") != 6:
        return fail("artifact tests.differential_equivalence drift")
    if int(tests.get("adjudicated") or 0) < 1:
        return fail("artifact adjudicated < 1")

    out = {
        "probe": "probe1-differential",
        "unit_id": "ARC-0042",
        "rails_checked": 3,
        "units_per_rail": 2,
        "files_checked": len(rows),
        "byte_identical_payload": len(identical),
        "adjudicated": len(queued),
        "negative_control_refused": True,
        "fire_and_forget_refused": True,
        "both_directions": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    for rec in rows:
        print(
            f"rail={rec['rail_id']} unit={rec['unit_id']} "
            f"identical={rec['byte_identical_payload']} "
            f"remainder={rec['remainder_queued']} "
            f"class={rec['classification']}"
        )
    print("SUCCESS:ARC-0042-probe1 differential equivalence both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
