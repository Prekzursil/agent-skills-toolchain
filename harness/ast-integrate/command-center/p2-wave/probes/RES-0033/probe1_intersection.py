#!/usr/bin/env python3
"""Probe 1: live set-intersection over sibling JSON must match the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import OUT_REL, SCRIPT_REL, SENTINEL, UNIT, compute, domain_of  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    live = compute()
    inter = live["intersection"]
    card = live["cardinality"]
    uni_card = live["union_cardinality"]
    ratio = live["intersection_over_union"]
    print(
        "intersection="
        + json.dumps(inter)
        + f" cardinality={card} union_cardinality={uni_card} "
        + f"ratio={live['ratio_fraction']} {ratio:.6f} "
        + f"n_supported={live['n_supported_vendors']} script={SCRIPT_REL}"
    )
    payload = domain_of(doc)
    if list(payload.get("intersection") or []) != inter:
        return fail(f"artifact intersection {payload.get('intersection')} != live {inter}")
    if int(payload.get("cardinality") or -1) != card:
        return fail(f"cardinality artifact={payload.get('cardinality')} live={card}")
    if int(payload.get("union_cardinality") or -1) != uni_card:
        return fail("union_cardinality mismatch")
    art_ratio = float(payload.get("intersection_over_union"))
    if abs(art_ratio - ratio) > 1e-12:
        return fail(f"ratio artifact={art_ratio} live={ratio}")
    if list(payload.get("union") or []) != live["union"]:
        return fail("union mismatch")
    if payload.get("script_path") != SCRIPT_REL:
        return fail("script_path mismatch")
    if card < 1:
        return fail("empty intersection — detector produced no portable core")
    if live["n_supported_vendors"] < 8:
        return fail(f"too few supported vendors {live['n_supported_vendors']}")
    # Mechanical: recompute from the vendor rows in the artifact itself.
    art_sets = []
    for v in payload.get("vendors") or []:
        if v.get("in_intersection_denominator") is True:
            art_sets.append(set(v.get("primitive_ids") or []))
    if not art_sets:
        return fail("artifact has no denominator vendors")
    recomputed = set.intersection(*art_sets)
    if sorted(recomputed) != inter:
        return fail("artifact vendor rows do not recompute to published intersection")
    print(f"SUCCESS:{UNIT}-probe1 live intersection cardinality ratio script")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
