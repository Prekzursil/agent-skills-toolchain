#!/usr/bin/env python3
"""Probe 1: two independent labellers, per-dimension kappa, family coverage.

Recomputes labels and kappa from the frozen sample. Does not trust the
artifact's summary numbers. Both-states: dropping family I must fire;
the live 9-family set must be silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gold as G  # noqa: E402
from dimensions import DIMENSIONS, FAMILIES, KAPPA_FLOOR, N_GOLD, OUT_REL, UNIT_ID  # noqa: E402
from kappa import round6  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / OUT_REL


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT_ID}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:WFA-0042" not in blob:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    pack = G.build_gold()
    live_kappa = {
        d: pack["kappa"]["per_dimension"][d]["kappa"] for d in DIMENSIONS
    }
    art_kappa = doc.get("per_dimension_kappa") or {}
    for dim in DIMENSIONS:
        live = round6(live_kappa[dim])
        got = round6(float(art_kappa.get(dim)))
        if live != got:
            return fail(
                "artifact kappa drifted",
                {"dim": dim, "live": live, "artifact": got},
            )

    cov = pack["family_coverage"]
    if not cov["complete"] or pack["n"] != N_GOLD:
        return fail("family coverage incomplete", cov)
    if list(FAMILIES) != cov["required"]:
        return fail("family list drifted")

    mutant = G.missing_family_mutant(pack["records"])
    if not mutant["fired_on_bad_state"]:
        return fail("missing-family mutant did not fire", mutant)
    if not mutant["silent_on_good_state"]:
        return fail("missing-family mutant fired on the good set", mutant)

    if doc.get("aggregate_kappa") is not None:
        return fail("aggregate kappa must stay null")
    if len(live_kappa) != 10:
        return fail("not 10 dimensions")
    if float(doc.get("kappa_floor")) != KAPPA_FLOOR:
        return fail("kappa floor drifted")

    sampling = pack["sampling"]
    if not sampling.get("written_before_selection"):
        return fail("sampling rule not marked written-before-selection")

    payload = {
        "both_states": {
            "bad_missing_family_fires": mutant["fired_on_bad_state"],
            "good_all_nine_silent": mutant["silent_on_good_state"],
        },
        "families": list(FAMILIES),
        "kappa_floor": KAPPA_FLOOR,
        "n": pack["n"],
        "pass": True,
        "per_dimension_kappa": live_kappa,
        "unmeasurable": pack["kappa"]["unmeasurable"],
        "probe": "probe1-two-labellers",
        "unit_id": UNIT_ID,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"SUCCESS:{UNIT_ID}-probe1 n={pack['n']} families=9 "
        "per-dimension kappa; missing-family mutant fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
