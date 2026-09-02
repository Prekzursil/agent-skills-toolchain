#!/usr/bin/env python3
"""Named probe 2: Dice coefficient, identical-seed control, all-KEEP mutant.

Does not import overlap.py. Different settling field than probe 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from dice import measure  # noqa: E402
from lenses import UNIQUE_YIELD_THRESHOLD  # noqa: E402

ART = REPO / "command-center/research/gem-hunt/RES-0155-lens-taxonomy-non-redundancy.json"
SENTINEL = "SUCCESS:RES-0155"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0155-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    p1_der = (doc.get("probe1_jaccard") or {}).get("derivation")
    p2_der = (doc.get("probe2_dice") or {}).get("derivation")
    if not p1_der or not p2_der or p1_der == p2_der:
        return fail(f"shared-derivation p1={p1_der} p2={p2_der}")
    if "jaccard-set-overlap" not in str(p1_der):
        return fail("probe1-derivation-missing")
    if "dice-coefficient" not in str(p2_der):
        return fail("probe2-derivation-missing")

    live = measure()
    stated = doc.get("probe2_dice") or {}
    if live["findings"] != stated.get("findings"):
        return fail("findings-mismatch")
    if not live["identical_seed_dice_all_one"]:
        return fail("identical-seed-dice")
    if not live["mutant_rejected"]:
        return fail("all-keep-mutant-survived")
    if stated.get("mutant_rejected") is not True:
        return fail("artifact-mutant-not-rejected")

    live_pairs = {(r["a"], r["b"], round(r["dice"], 12)) for r in live["pairwise"]}
    art_pairs = {
        (r["a"], r["b"], round(float(r["dice"]), 12))
        for r in (stated.get("pairwise") or [])
    }
    if live_pairs != art_pairs:
        return fail("dice-matrix-drift")

    live_uy = {r["lens_id"]: r["unique_yield"] for r in live["unique_yields"]}
    if live_uy.get("orchestration-synonym") != 0.0:
        return fail("synonym-unique")
    if live_uy.get("orchestration", 0) < UNIQUE_YIELD_THRESHOLD:
        return fail("orchestration-unique")

    zero_forced = int((live.get("mutant") or {}).get("n_zero_unique_forced_keep") or 0)
    if zero_forced < 1:
        return fail("mutant-had-no-zero-unique")

    payload = {
        "probe": "probe2-dice-mutant",
        "unit_id": "RES-0155",
        "pass": True,
        "identical_seed_dice_all_one": True,
        "mutant_rejected": True,
        "n_zero_unique_forced_keep": zero_forced,
        "derivation": live["derivation"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"identical_seed_dice=1 mutant_rejected=True zero_unique_forced_keep={zero_forced}"
    )
    print("SUCCESS:RES-0155-probe2 dice plus all-KEEP mutant both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
