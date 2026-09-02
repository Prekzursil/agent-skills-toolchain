#!/usr/bin/env python3
"""Probe 1: both-states control for the known M-NN stale-open case.

Must fire on the stale-open premise and stay silent on the current
reprefix premise in the same pack. Silence on both is a dead detector.
Inverted and reconciled packs prove the detector is not stuck.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from detector import evaluate_pack  # noqa: E402
from fixtures import ensure_fixtures  # noqa: E402

ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0188-stale-premise-detection-in-briefing-packs.json"
)
SENTINEL = "SUCCESS:RES-0188"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0188-probe1 {msg}")
    return 1


def main() -> int:
    paths = ensure_fixtures()
    known = evaluate_pack(paths["known-case"])
    inverted = evaluate_pack(paths["inverted"])
    reconciled = evaluate_pack(paths["reconciled"])

    stale = next(p for p in known["premises"] if p["id"] == "P-STALE-MNN-OPEN")
    current = next(p for p in known["premises"] if p["id"] == "P-CURRENT-MECH-REPREFIX")
    print(
        "known-case stale_fire={0} current_fire={1} collision={2} mech={3} bare_m={4}".format(
            stale["fire"],
            current["fire"],
            stale["measurement"]["literal_collision_count"],
            stale["measurement"]["architecture_mech_count"],
            stale["measurement"]["architecture_bare_m_count"],
        )
    )
    if not stale["fire"]:
        return fail("known-stale M-NN premise did not fire")
    if current["fire"]:
        return fail("current reprefix premise fired (false positive)")
    if stale["fire"] == current["fire"]:
        return fail("both-states identical; detector measures nothing")

    inv_stale = next(p for p in inverted["premises"] if p["id"] == "P-STALE-MNN-OPEN")
    inv_cur = next(p for p in inverted["premises"] if p["id"] == "P-CURRENT-MECH-REPREFIX")
    print(
        "inverted open_fire={0} reprefix_fire={1} collision={2}".format(
            inv_stale["fire"],
            inv_cur["fire"],
            inv_stale["measurement"]["literal_collision_count"],
        )
    )
    if inv_stale["fire"]:
        return fail("inverted live collision was labelled stale-open")
    if not inv_cur["fire"]:
        return fail("inverted missing reprefix was silent")
    if any(p["fire"] for p in reconciled["premises"]):
        return fail("reconciled pack fired; detector is stuck-on")
    print("reconciled fired_ids={0}".format(reconciled["fired_ids"]))

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != "RES-0188":
        return fail(f"unit_id={doc.get('unit_id')}")
    ctrl = doc.get("both_states") or {}
    if ctrl.get("stale_fired") is not True:
        return fail("artifact both_states.stale_fired is not true")
    if ctrl.get("current_silent") is not True:
        return fail("artifact both_states.current_silent is not true")
    print("SUCCESS:RES-0188-probe1 both-states fire-on-stale silent-on-current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
