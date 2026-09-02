#!/usr/bin/env python3
"""Probe 1: seeding-permutation sweep + both-states invariance gate.

Planted-bad = cyclic4 (W>X>Y>W, Z loses to all): 24 seedings, 3 distinct
winners, invariance_rate=1/3 -> gate FIRES, unique winner refused.
Known-good = transitive4 (W beats everyone): W on all 24 -> gate SILENT.

A stability claim without those numbers is refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import bracket as B  # noqa: E402
import contract as C  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0036-pairwise-tournament-topology-bracket-seeding-and-tie-break.md"
)
FIX = HERE / "fixtures.json"


def profile(fx: dict, key: str):
    p = fx[key]
    return (
        list(fx["options"]),
        B.beats_set(p["beats"]),
        B.tie_set(p.get("ties") or []),
    )


def compact(row: dict, gate: dict) -> str:
    return (
        f"n_perm={row['n_permutations']} n_distinct={row['n_distinct_winners']} "
        f"counts={row['counts']} invariance_rate={row['invariance_rate']:.12f} "
        f"fires={gate['fires']} publication={gate['publication']} "
        f"published_winner={gate['published_winner']!r} reason={row['reason']}"
    )


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0036-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNL-0036-probe1 unparseable:{type(exc).__name__}")
        return 1
    uid = doc.get("unit_id") or doc.get("unit_id")
    if uid != "CNL-0036":
        print("FAILED:CNL-0036-probe1 unit_id", uid)
        return 1
    if "SUCCESS:CNL-0036" not in text:
        print("FAILED:CNL-0036-probe1 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNL-0036-probe1 self-declared", doc.get("state"))
        return 1

    fx = json.loads(FIX.read_text(encoding="utf-8"))
    thr = float(fx["threshold_reject_below"])
    tb = fx["tie_break_declared"]

    opt_c, beats_c, ties_c = profile(fx, "cyclic4")
    opt_t, beats_t, ties_t = profile(fx, "transitive4")
    cyclic = B.sweep(opt_c, beats_c, ties_c, tb)
    trans = B.sweep(opt_t, beats_t, ties_t, tb)
    g_c = B.gate_unique_winner(cyclic, thr)
    g_t = B.gate_unique_winner(trans, thr)

    print("PLANTED-BAD cyclic4: " + compact(cyclic, g_c))
    print("KNOWN-GOOD transitive4: " + compact(trans, g_t))

    if cyclic["n_permutations"] != 24 or trans["n_permutations"] != 24:
        print("FAILED:CNL-0036-probe1 expected 4!=24 permutations")
        return 1
    if cyclic["n_distinct_winners"] != 3 or cyclic["counts"] != {
        "W": 8,
        "X": 8,
        "Y": 8,
    }:
        print("FAILED:CNL-0036-probe1 unexpected cyclic counts", cyclic["counts"])
        return 1
    if abs(cyclic["invariance_rate"] - (8 / 24)) > 1e-12:
        print("FAILED:CNL-0036-probe1 cyclic invariance_rate", cyclic["invariance_rate"])
        return 1
    if not g_c["fires"] or g_c["publication"] != "SEEDING-DEPENDENT-REFUSED":
        print("FAILED:CNL-0036-probe1 planted-bad did not FIRE")
        return 1
    if g_c["published_winner"] is not None:
        print("FAILED:CNL-0036-probe1 planted-bad published a unique winner")
        return 1
    if trans["counts"] != {"W": 24} or trans["n_distinct_winners"] != 1:
        print("FAILED:CNL-0036-probe1 transitive is not W x24")
        return 1
    if g_t["fires"] or g_t["publication"] != "INVARIANT-UNIQUE-WINNER":
        print("FAILED:CNL-0036-probe1 known-good was not SILENT")
        return 1
    if g_t["published_winner"] != "W":
        print("FAILED:CNL-0036-probe1 known-good published_winner", g_t["published_winner"])
        return 1

    rec = C.sweep_of(doc)
    rec_c = rec.get("cyclic4") or {}
    rec_t = rec.get("transitive4") or {}
    if rec_c.get("counts") != cyclic["counts"]:
        print("FAILED:CNL-0036-probe1 artifact cyclic counts drift")
        return 1
    if rec_c.get("n_distinct_winners") != 3:
        print("FAILED:CNL-0036-probe1 artifact cyclic n_distinct drift")
        return 1
    if abs(float(rec_c.get("invariance_rate")) - cyclic["invariance_rate"]) > 1e-12:
        print("FAILED:CNL-0036-probe1 artifact cyclic rate drift")
        return 1
    if rec_t.get("counts") != {"W": 24}:
        print("FAILED:CNL-0036-probe1 artifact transitive counts drift")
        return 1

    print(
        "NEGATIVE CONTROL verbatim: on cyclic4 the invariance gate FIRES "
        f"(n_distinct=3 invariance_rate={cyclic['invariance_rate']:.12f} "
        f"< threshold={thr}); it does not publish the winner of one seed "
        "order as the council winner."
    )
    print(
        "BOTH-STATES: FIRED on planted-bad cyclic4; SILENT on known-good "
        f"transitive4; same n_perm={cyclic['n_permutations']}"
    )
    print("SUCCESS:CNL-0036-probe1 seeding-sweep both-states negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
