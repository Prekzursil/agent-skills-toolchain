#!/usr/bin/env python3
"""Probe 2: independent matrix census + bulk-symmetrise must go red.

A reviewer who only re-reads the pair list has verified nothing. This probe
rebuilds the adjacency matrix, applies the forbidden bulk-symmetrise mutant,
and requires repair_is_admissible to reject it while the typed repair passes.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import graph as G  # noqa: E402

ART = (
    REPO
    / "command-center/foundry/WFA-0149-resolve-the-140-asymmetric-compatibility-declaration.json"
)
MAPS = HERE / "fixtures" / "merge-maps-decoy-counts.json"
SENTINEL = "SUCCESS:WFA-0149"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0149-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")

    library, source_label, live = G.load_subject(REPO)
    bps = G.blueprints_of(library)
    matrix = G.census_from_matrix(bps)
    lists = G.census_from_lists(bps)
    print(f"source={source_label} live={live} matrix={matrix}")
    if matrix != lists:
        return fail("matrix != lists")
    if doc.get("census_matrix") != matrix:
        return fail("artifact census_matrix stale")

    verdicts = G.adjudicate_all(bps)
    typed = G.typed_repair(bps, verdicts)
    tok, twhy = G.repair_is_admissible(bps, typed, verdicts)
    print(f"typed_repair ok={tok} {twhy}")
    if not tok:
        return fail(f"typed repair rejected {twhy}")

    bulk = G.bulk_symmetrise(bps)
    bok, bwhy = G.repair_is_admissible(bps, bulk, verdicts)
    bc = G.census_from_matrix(bulk)
    print(f"bulk_symmetrise ok={bok} {bwhy} census={bc}")
    if bok:
        return fail("bulk-symmetrise mutant was accepted")
    if bc["asymmetric"] != 0:
        return fail("bulk mutant did not drive asymmetric to 0")
    if not live and bc["declared"] != 530:
        return fail(f"bulk declared {bc['declared']} != 530")

    mutant = copy.deepcopy(verdicts)
    for v in mutant:
        v["verdict"] = "MISSING-REVERSE"
        v["reason"] = "mutant: force every pair to MISSING-REVERSE"
    mok, mwhy = G.repair_is_admissible(bps, G.typed_repair(bps, mutant), mutant)
    print(f"mutant_all_missing_reverse ok={mok} {mwhy}")
    if mok:
        return fail("all-MISSING-REVERSE mutant was accepted")

    if not MAPS.is_file():
        return fail("merge-maps decoy fixture missing")
    maps = json.loads(MAPS.read_text(encoding="utf-8"))
    finding = maps.get("FINDING_asymmetric_compat") or {}
    print(f"finding_recommended_action={finding.get('recommended_action')}")
    if finding.get("recommended_action") != "SYMMETRISE-ALL":
        return fail("decoy finding not planted")
    if doc.get("bulk_symmetrise", {}).get("rejected") is not True:
        return fail("artifact did not reject bulk symmetrise")
    if doc.get("bulk_symmetrise", {}).get("admissible") is not False:
        return fail("artifact marked bulk admissible")

    bulk_art = doc.get("bulk_symmetrise") or {}
    if bulk_art.get("census_if_applied") != G.census_from_lists(bulk):
        return fail("artifact bulk census stale")

    print("live_detector_ok=True")
    print("SUCCESS:WFA-0149-probe2 bulk-symmetrise mutant rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
