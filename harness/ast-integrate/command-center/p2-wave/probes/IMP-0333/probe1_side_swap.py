#!/usr/bin/env python3
"""Named probe 1: side-swap flip rate on the live Oxford engine.

Recomputes the swapped-sides replication. Does not trust the receipt's
summary: the engine must produce the same rates the receipt published.
Also checks both sides sat, turns were timed, and over-depth rebuttal is
refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from tools.council.protocol.oxford import (  # noqa: E402
    HIGH_FLIP_FLOOR,
    LOW_FLIP_CEILING,
    OxfordProtocol,
    side_swap_experiment,
)

ART = REPO / S.ART


def _load_receipt() -> dict:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0333-probe1 receipt missing")
        sys.exit(1)
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0333-probe1 receipt unparseable {exc}")
        sys.exit(1)
    if not isinstance(doc, dict):
        print("FAILED:IMP-0333-probe1 receipt not an object")
        sys.exit(1)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0333-probe1 self-declared {doc.get('state')}")
        sys.exit(1)
    if "SUCCESS:IMP-0333" not in text:
        print("FAILED:IMP-0333-probe1 sentinel absent")
        sys.exit(1)
    if doc.get("unit_id") != "IMP-0333":
        print(f"FAILED:IMP-0333-probe1 unit_id {doc.get('unit_id')}")
        sys.exit(1)
    return doc


def main() -> int:
    doc = _load_receipt()
    proto = OxfordProtocol(S.CONFIG)
    rec = proto.run(S.decisive(), S.evidence_speakers(), S.ASSIGNMENTS)
    sides = {t.side for t in rec.turns}
    kinds = {t.kind for t in rec.turns}
    if sides != {"proposition", "opposition"}:
        print(f"FAILED:IMP-0333-probe1 sides {sides}")
        return 1
    if not {"opening", "rebuttal", "closing"} <= kinds:
        print(f"FAILED:IMP-0333-probe1 kinds {kinds}")
        return 1
    if rec.turns_executed != rec.turns_recorded or rec.turns_executed < 4:
        print(
            f"FAILED:IMP-0333-probe1 loop invariant "
            f"executed={rec.turns_executed} recorded={rec.turns_recorded}"
        )
        return 1
    extra = proto.submit_rebuttal(rec, S.evidence_speakers(), "alice", depth=3)
    if not extra.refused or extra.refuse_reason != "rebuttal_depth_exceeded":
        print(f"FAILED:IMP-0333-probe1 depth bound did not fire {extra}")
        return 1

    decisive_e = side_swap_experiment(
        S.decisive(), S.evidence_speakers(), S.ASSIGNMENTS, S.CONFIG
    )
    rhetoric = side_swap_experiment(
        S.balanced(), S.side_speakers(), S.ASSIGNMENTS, S.CONFIG
    )
    if decisive_e["flip_rate"] > LOW_FLIP_CEILING:
        print(
            f"FAILED:IMP-0333-probe1 evidence-bound decisive flip_rate="
            f"{decisive_e['flip_rate']} exceeds ceiling {LOW_FLIP_CEILING}"
        )
        return 1
    if rhetoric["flip_rate"] < HIGH_FLIP_FLOOR:
        print(
            f"FAILED:IMP-0333-probe1 side-bound balanced flip_rate="
            f"{rhetoric['flip_rate']} below floor {HIGH_FLIP_FLOOR}"
        )
        return 1

    published = doc.get("measurements") or {}
    want_low = published.get("evidence_bound_decisive_side_swap_flip_rate")
    want_high = published.get("side_bound_balanced_side_swap_flip_rate")
    if want_low is None or abs(float(want_low) - float(decisive_e["flip_rate"])) > 1e-9:
        print(
            f"FAILED:IMP-0333-probe1 receipt flip mismatch low "
            f"published={want_low} live={decisive_e['flip_rate']}"
        )
        return 1
    if want_high is None or abs(float(want_high) - float(rhetoric["flip_rate"])) > 1e-9:
        print(
            f"FAILED:IMP-0333-probe1 receipt flip mismatch high "
            f"published={want_high} live={rhetoric['flip_rate']}"
        )
        return 1

    payload = {
        "depth_bound_refused": True,
        "flip_rate_evidence_bound_decisive": decisive_e["flip_rate"],
        "flip_rate_side_bound_balanced": rhetoric["flip_rate"],
        "kinds": sorted(kinds),
        "n_turns": rec.turns_executed,
        "pass": True,
        "probe": "probe1-side-swap",
        "sides": sorted(sides),
        "unit_id": "IMP-0333",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "sides=proposition,opposition "
        f"turns={rec.turns_executed} "
        f"decisive_flip={decisive_e['flip_rate']} "
        f"rhetoric_flip={rhetoric['flip_rate']} "
        "depth_bound_refused=True"
    )
    print("SUCCESS:IMP-0333-probe1 side-swap flip rate published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
