#!/usr/bin/env python3
"""WFA-0101 probe 2: degeneracy both-states, independent of recomposition."""
from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from families import all_families
from fusion_op import OUT_REL, fuse_family
from workflow_foundry.common_core import (
    DEGENERATE_CORE_CEILING,
    DEGENERATE_FAMILY_FLOOR,
    degeneracy_check,
    extract_common_core,
    extract_family_core,
    reproduction_report,
)

ART = REPO / OUT_REL
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0101-probe2 {msg}")
    return 1


def by_id(fid: str):
    return next(s for s in all_families() if s.family_id == fid)


def main() -> int:
    if not ART.is_file():
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in BLOCKED:
        return fail(f"self-declared:{st}")
    if "SUCCESS:WFA-0101" not in text:
        return fail("sentinel-absent")

    src = inspect.getsource(degeneracy_check)
    if "family_size" not in src or "raw_lcs_size" not in src:
        return fail("degeneracy_check-does-not-read-sizes")
    tree = ast.parse(src)
    calls = [
        n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
    ]
    if "reproduction_report" in calls or "recompose" in calls:
        return fail("degeneracy_check-calls-recomposition")

    d4 = by_id("D4")
    naive = extract_common_core(list(d4.members))
    naive_rep = reproduction_report(naive, list(d4.members))
    deg4 = degeneracy_check(
        raw_lcs_size=naive.core_size,
        family_size=len(d4.members),
        source_sizes=[len(w.stages) for w in d4.members],
    )
    honest4, _ = extract_family_core(list(d4.members))
    both_bad = {
        "naive_emits_core": naive.status == "ok" and naive.core_size == 1,
        "naive_recompose_succeeds": naive_rep.get("equal") is True,
        "size_check_fires": deg4["degenerate"] is True,
        "honest_suppresses": honest4.status == "degenerate-intersection" and honest4.core is None,
    }
    if not all(both_bad.values()):
        return fail(f"D4-both-states:{both_bad} deg={deg4} naive={naive.status}/{naive.core_size}")

    d1 = by_id("D1")
    naive1 = extract_common_core(list(d1.members))
    deg1 = degeneracy_check(
        raw_lcs_size=naive1.core_size,
        family_size=len(d1.members),
        source_sizes=[len(w.stages) for w in d1.members],
    )
    honest1, _ = extract_family_core(list(d1.members))
    both_good = {
        "core_emitted": honest1.status == "ok" and honest1.core_size == 4,
        "size_check_silent": deg1["degenerate"] is False and deg1["empty"] is False,
        "recompose_n": reproduction_report(honest1, list(d1.members)).get("equal") is True,
    }
    if not all(both_good.values()):
        return fail(f"D1-good-state:{both_good} core={naive1.core_size} deg={deg1}")

    d10 = by_id("D10")
    naive10 = extract_common_core(list(d10.members))
    deg10 = degeneracy_check(
        raw_lcs_size=naive10.core_size,
        family_size=len(d10.members),
        source_sizes=[len(w.stages) for w in d10.members],
    )
    if len(d10.members) != 7 or naive10.core_size != 4 or deg10["degenerate"]:
        return fail(
            f"D10-large-family-large-core size={naive10.core_size} fam={len(d10.members)} deg={deg10}"
        )

    d11 = by_id("D11")
    naive11 = extract_common_core(list(d11.members))
    deg11 = degeneracy_check(
        raw_lcs_size=naive11.core_size,
        family_size=len(d11.members),
        source_sizes=[len(w.stages) for w in d11.members],
    )
    honest11, _ = extract_family_core(list(d11.members))
    if naive11.core_size != 1 or len(d11.members) != 2 or deg11["degenerate"] or honest11.core is None:
        return fail(
            f"D11-one-stage-pair size={naive11.core_size} fam={len(d11.members)} deg={deg11}"
        )

    d3 = by_id("D3")
    naive3 = extract_common_core(list(d3.members))
    if naive3.status != "empty-intersection" or naive3.core is not None:
        return fail(f"D3-must-be-empty:{naive3.status}")

    art_by = {f["family_id"]: f for f in doc["families"]}
    for fid in ("D4", "D19"):
        rec = art_by[fid]
        if rec["status"] != "degenerate-intersection" or rec["core"] is not None:
            return fail(f"artifact-{fid}-not-suppressed:{rec['status']}")
        live = fuse_family(by_id(fid))
        if live["status"] != "degenerate-intersection":
            return fail(f"live-{fid}-not-degenerate:{live['status']}")

    if DEGENERATE_FAMILY_FLOOR != 7 or DEGENERATE_CORE_CEILING != 1:
        return fail(f"floor-ceiling {DEGENERATE_FAMILY_FLOOR}/{DEGENERATE_CORE_CEILING}")

    print(
        json.dumps(
            {
                "ok": True,
                "both_states": {"good": both_good, "bad": both_bad},
                "D10_core_size": naive10.core_size,
                "D11_core_size": naive11.core_size,
                "D11_emitted": honest11.core is not None,
                "independent_of_recomposition": both_bad["naive_recompose_succeeds"]
                and both_bad["size_check_fires"],
            },
            sort_keys=True,
        )
    )
    print(
        f"good_silent={both_good['size_check_silent']} "
        f"bad_fires={both_bad['size_check_fires']} "
        f"naive_recompose={both_bad['naive_recompose_succeeds']} "
        f"honest_suppress={both_bad['honest_suppresses']}"
    )
    print("SUCCESS:WFA-0101-probe2 degeneracy both-states; size check independent of recomposition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
