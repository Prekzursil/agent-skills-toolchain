#!/usr/bin/env python3
"""Named probe 1: Jaccard on mechanism-id sets, unique yield, seeded self-overlap.

Does not import dice.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from overlap import measure  # noqa: E402

ART = REPO / "command-center/research/gem-hunt/RES-0155-lens-taxonomy-non-redundancy.json"
SENTINEL = "SUCCESS:RES-0155"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0155-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 400:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "RES-0155":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    live = measure()
    stated = doc.get("probe1_jaccard") or {}
    if stated.get("derivation") != "jaccard-set-overlap-on-mechanism-ids":
        return fail(f"derivation={stated.get('derivation')}")
    p2_der = (doc.get("probe2_dice") or {}).get("derivation")
    if not p2_der or p2_der == stated.get("derivation"):
        return fail(f"shared-derivation p1={stated.get('derivation')} p2={p2_der}")

    if live["findings"] != stated.get("findings"):
        return fail("findings-mismatch")
    if live["n_merge"] != stated.get("n_merge") or live["n_keep"] != stated.get("n_keep"):
        return fail("recommendation-counts")
    if abs(float(live["noise_floor_mean"]) - float(stated.get("noise_floor_mean") or -1)) > 1e-12:
        return fail("noise-floor-mean-drift")

    live_recs = {(r["lens_id"], r["action"], r.get("partner")) for r in live["recommendations"]}
    art_recs = {
        (r["lens_id"], r["action"], r.get("partner"))
        for r in (stated.get("recommendations") or [])
    }
    if live_recs != art_recs:
        return fail(f"recs-mismatch live={sorted(live_recs)} art={sorted(art_recs)}")

    syn = next(r for r in live["recommendations"] if r["lens_id"] == "orchestration-synonym")
    if syn["action"] != "MERGE" or syn["partner"] != "orchestration":
        return fail("synonym-not-merged")

    for lid, row in live["self_overlap"].items():
        if row["identical_seed_jaccard"] != 1.0:
            return fail(f"identical-seed {lid}")
        art_so = (stated.get("self_overlap") or {}).get(lid) or {}
        if abs(float(row["jaccard"]) - float(art_so.get("jaccard") or -1)) > 1e-12:
            return fail(f"self-overlap-drift {lid}")

    uy = {r["lens_id"]: r["unique_yield"] for r in live["unique_yields"]}
    if uy["orchestration-synonym"] != 0.0:
        return fail("synonym-unique-not-zero")
    if uy["orchestration"] < 0.10:
        return fail("orchestration-unique-below-threshold")

    payload = {
        "probe": "probe1-jaccard-sets",
        "unit_id": "RES-0155",
        "pass": True,
        "n_keep": live["n_keep"],
        "n_merge": live["n_merge"],
        "n_drop": live["n_drop"],
        "synonym_merge": True,
        "noise_floor_mean": live["noise_floor_mean"],
        "derivation": live["derivation"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "self-overlap noise floor mean="
        f"{live['noise_floor_mean']:.3f} merge={live['n_merge']} "
        f"drop={live['n_drop']} keep={live['n_keep']}"
    )
    print("SUCCESS:RES-0155-probe1 jaccard unique-yield merge/drop two-seed noise floor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
