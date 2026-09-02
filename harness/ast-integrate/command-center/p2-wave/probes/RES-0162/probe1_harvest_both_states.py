#!/usr/bin/env python3
"""Probe 1: harvest both-states. Exit 0 alone must not produce SUCCESS."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harvest as H  # noqa: E402

UNIT = "RES-0162"
ART = REPO / "command-center/research/prior-art/RES-0162-cross-vendor-invocation-surface-leaks.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0162-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("unit_id") or "") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:RES-0162" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    with tempfile.TemporaryDirectory(prefix="res0162-p1-") as tmp:
        both = H.both_states(Path(tmp))
    if not both.get("pass") or not both.get("discriminates"):
        return fail("both-states did not discriminate SUCCESS vs SEVERED")
    if not both.get("exit_only_cannot_be_the_gate"):
        return fail("exit-only harvester did not SUCCESS the empty plant")

    recorded = {c.get("id"): c for c in (doc.get("controls") or [])}
    for case in both["cases"]:
        rec = recorded.get(case["id"])
        if not rec:
            return fail(f"missing control {case['id']}")
        if rec.get("watcher_wake") != case["watcher_wake"]:
            return fail(f"watcher_wake drift {case['id']}")
        if rec.get("poller_wake") != case["poller_wake"]:
            return fail(f"poller_wake drift {case['id']}")
        if rec.get("verdict") != "PASS":
            return fail(f"recorded verdict {case['id']} {rec.get('verdict')}")

    complete = next(c for c in both["cases"] if c["id"] == "harvest-complete")
    empty = next(c for c in both["cases"] if c["id"] == "harvest-empty")
    absent = next(c for c in both["cases"] if c["id"] == "harvest-absent")
    if complete["and_gate_verdict"] != "SUCCESS":
        return fail("complete plant was not SUCCESS")
    if empty["and_gate_verdict"] != "SEVERED":
        return fail("empty plant was not SEVERED")
    if absent["and_gate_verdict"] != "SEVERED":
        return fail("absent plant was not SEVERED")
    if empty["exit_only_verdict"] != "SUCCESS":
        return fail("exit-only empty plant was not SUCCESS (control is inert)")

    out = {
        "probe": "probe1-harvest-both-states",
        "unit_id": UNIT,
        "pass": True,
        "complete": "SUCCESS",
        "empty": "SEVERED",
        "absent": "SEVERED",
        "exit_only_empty": "SUCCESS",
        "cases": [(c["id"], c["and_gate_verdict"]) for c in both["cases"]],
    }
    print(json.dumps(out, indent=1, sort_keys=True))
    print("SUCCESS:RES-0162-probe1 harvest SUCCESS vs SEVERED; exit code alone cannot SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
