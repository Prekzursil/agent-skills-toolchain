#!/usr/bin/env python3
"""Probe 2: planted renamed-id duplicate + independent reviewer recount.

Negative control (verbatim): the check REJECTS a planted preset that copies
another preset's protocol set, role set, voting method and stopping
expression while changing only the id and name. It is silent on a genuine
4-tuple (C02 vs C01).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catalog as C  # noqa: E402
import distinctness as D  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0102-preset-protocol-binding-matrix-and-the-mechanical-distinct.md"
)
NEGATIVE_VERBATIM = (
    "The check REJECTS a planted preset that copies another preset's "
    "protocol set, role set, voting method and stopping expression while "
    "changing only the id and name. It is silent on a genuine 4-tuple "
    "(C02 vs C01)."
)


def _fail(msg: str) -> int:
    print(f"FAILED:CNL-0102-probe2 {msg}")
    return 1


def independent_recount(presets: list[dict]) -> dict:
    """Walk in reverse id order and re-bucket; must not read the author's count."""
    rev = sorted(presets, key=lambda p: p["id"], reverse=True)
    buckets: dict[tuple, list[str]] = {}
    for p in rev:
        sig = (
            tuple(sorted(p["bound_protocols"])),
            tuple(sorted(p["roles"])),
            str(p["voting_method"]),
            str(p["stopping_expression"]),
        )
        buckets.setdefault(sig, []).append(p["id"])
    clones = sorted(
        tuple(sorted(ids))
        for ids in buckets.values()
        if len(ids) > 1
    )
    return {
        "distinct_signature_count": len(buckets),
        "pair_count": D.pair_count(len(presets)),
        "clone_groups": clones,
        "preset_count": len(presets),
    }


def main() -> int:
    corpus = C.load_corpus()
    presets = corpus["presets"]
    live = D.analyse(presets)
    recount = independent_recount(presets)
    if recount["distinct_signature_count"] != live["distinct_signature_count"]:
        return _fail(
            "recount disagree distinct "
            f"{recount['distinct_signature_count']} vs {live['distinct_signature_count']}"
        )
    if recount["pair_count"] != live["pair_count"]:
        return _fail("recount disagree pair_count")

    # Plant C02 (no live clone) so the detector must add exactly one pair.
    planted = D.plant_renamed_duplicate(presets, "C02", "C-PLANT-DUP")
    planted_report = D.analyse(planted)
    plant_pairs = [
        r
        for r in planted_report["below_threshold_pairs"]
        if "C-PLANT-DUP" in (r["left"], r["right"])
    ]
    if not plant_pairs:
        return _fail("planted renamed-id duplicate not caught")
    if planted_report["below_threshold_pair_count"] != live["below_threshold_pair_count"] + 1:
        return _fail(
            "planted pair count "
            f"{planted_report['below_threshold_pair_count']} "
            f"live {live['below_threshold_pair_count']}"
        )
    if planted_report["distinct_signature_count"] != live["distinct_signature_count"]:
        return _fail("plant should not create a new signature")

    d_c01_c02 = D.distance(
        next(p for p in presets if p["id"] == "C01"),
        next(p for p in presets if p["id"] == "C02"),
    )
    if d_c01_c02 <= D.THRESHOLD:
        return _fail(f"C01 vs C02 collapsed d={d_c01_c02}")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if "SUCCESS:CNL-0102" not in ART.read_text(encoding="utf-8"):
            return _fail("sentinel-absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"self-declared {st}")
        measured = doc.get("measured") or {}
        if measured.get("distinct_signature_count") != recount["distinct_signature_count"]:
            return _fail(
                "artifact distinct "
                f"{measured.get('distinct_signature_count')} "
                f"recount {recount['distinct_signature_count']}"
            )
        if measured.get("pair_count") != recount["pair_count"]:
            return _fail("artifact pair_count disagree")
        if doc.get("reviewer", {}).get("recounted_crossover_n") != doc.get(
            "size_sweep", {}
        ).get("crossover_n"):
            return _fail("reviewer recounted_crossover_n disagree")
        print("artifact_recount_agrees=true")
    else:
        print("artifact_absent_at_probe2_run")

    print(
        json.dumps(
            {
                "probe": "probe2-planted-duplicate-and-recount",
                "planted_caught": True,
                "plant_pairs": plant_pairs,
                "c01_c02_distance": d_c01_c02,
                "recount": recount,
                "negative_control_verbatim": NEGATIVE_VERBATIM,
            },
            sort_keys=True,
        )
    )
    print(
        "planted_caught=True "
        f"distinct={recount['distinct_signature_count']} "
        f"pair_count={recount['pair_count']} "
        f"c01_c02_distance={d_c01_c02}"
    )
    print("SUCCESS:CNL-0102-probe2 planted duplicate caught; independent recount agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
