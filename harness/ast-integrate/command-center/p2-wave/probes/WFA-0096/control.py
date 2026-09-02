"""Live planted-mutant control: catch three shapes, stay silent on three decoys."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import differ as D  # noqa: E402
import plant as P  # noqa: E402
from ir import load_base_corpus  # noqa: E402


def _score_plant(
    plant: dict[str, Any],
    augmented: list[dict[str, Any]],
    *,
    threshold: float,
) -> dict[str, Any]:
    ranked = D.nearest_neighbors(plant, augmented, score_fn=D.jaccard)
    if not ranked:
        raise RuntimeError(f"no neighbors for {plant['id']}")
    nearest_id, nearest_score = ranked[0]
    host_score = None
    host_id = plant.get("host_id")
    for oid, score in ranked:
        if oid == host_id:
            host_score = score
            break
    detected = D.is_duplicate(nearest_score, threshold)
    nearest_ir = next((ir for ir in augmented if ir.get("id") == nearest_id), None)
    host_ir = next((ir for ir in augmented if ir.get("id") == host_id), None)
    if nearest_ir is None:
        raise RuntimeError(f"nearest {nearest_id} missing from corpus")
    return {
        "plant_id": plant["id"],
        "shape": plant.get("plant_shape"),
        "host_id": host_id,
        "nearest_id": nearest_id,
        "nearest_score": round(nearest_score, 6),
        "host_score": None if host_score is None else round(host_score, 6),
        "exclusive_vs_host": (
            None if host_ir is None else D.exclusive_total(plant, host_ir)
        ),
        "exclusive_vs_nearest": D.exclusive_total(plant, nearest_ir),
        "detected": detected,
        "independent_duplicate_vs_host": (
            None if host_ir is None else D.independent_is_duplicate(plant, host_ir)
        ),
        "independent_duplicate_vs_nearest": D.independent_is_duplicate(plant, nearest_ir),
        "threshold": threshold,
    }


def run_control(*, threshold: float | None = None) -> dict[str, Any]:
    thr = D.THRESHOLD if threshold is None else float(threshold)
    base = load_base_corpus()
    planted = P.plant_into_corpus(base, threshold=thr)
    augmented = planted["augmented"]
    if planted["augmented_count"] != planted["base_count"] + 6:
        raise RuntimeError("plants were not inserted into the scored corpus")
    planted_ids = {p["id"] for p in planted["mutants"] + planted["decoys"]}
    corpus_ids = {ir["id"] for ir in augmented}
    if not planted_ids <= corpus_ids:
        raise RuntimeError("plant ids missing from scored corpus")

    self_bad = D.self_diff_failures(augmented)
    absent_vs = D.absent_versus_different_fixture()
    mutants = [_score_plant(p, augmented, threshold=thr) for p in planted["mutants"]]
    decoys = [_score_plant(p, augmented, threshold=thr) for p in planted["decoys"]]

    mutants_caught = all(
        row["detected"]
        and row["nearest_id"] == row["host_id"]
        and row["independent_duplicate_vs_host"] is True
        and row["independent_duplicate_vs_nearest"] is True
        for row in mutants
    )
    decoys_silent = all(
        (not row["detected"])
        and row["independent_duplicate_vs_nearest"] is False
        and row["exclusive_vs_nearest"] > D.INDEPENDENT_EXCLUSIVE_MAX
        for row in decoys
    )
    shapes = [row["shape"] for row in mutants]
    return {
        "ok": mutants_caught
        and decoys_silent
        and not self_bad
        and absent_vs["distinguished"]
        and planted["planted_into_real_corpus"]
        and not planted["toy_fixture"],
        "threshold": thr,
        "threshold_version": D.THRESHOLD_VERSION,
        "differ_id": D.DIFFER_ID,
        "differ_path": "command-center/p2-wave/probes/WFA-0096/differ.py",
        "differ_sha256": D.module_fingerprint(HERE / "differ.py"),
        "base_count": planted["base_count"],
        "augmented_count": planted["augmented_count"],
        "planted_into_real_corpus": planted["planted_into_real_corpus"],
        "toy_fixture": planted["toy_fixture"],
        "hosts": planted["hosts"],
        "mutants": mutants,
        "decoys": decoys,
        "mutants_caught": mutants_caught,
        "decoys_silent": decoys_silent,
        "shapes": shapes,
        "self_diff_failures": self_bad,
        "absent_versus_different": absent_vs,
        "always_fire_would_flag_decoys": all(
            D.is_duplicate(row["nearest_score"], 0.0) for row in decoys
        ),
        "never_fire_would_miss_mutants": all(
            not D.is_duplicate(row["host_score"] or 0.0, 1.01) for row in mutants
        ),
    }
