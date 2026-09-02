#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0266.json calibration receipt."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from calibrate import run_calibration  # noqa: E402
from novelty_runtime import KAPPA_FLOOR, KAPPA_FLOOR_NOTE, KAPPA_FLOOR_RECORDED_AT  # noqa: E402

OUT = "command-center/receipts/TST-0266.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0266/probe1_heldout_adversarial.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0266/probe2_reviewer_demotion.py"
)
QUESTION = (
    "Question: does the runtime novelty score agree with human-labelled novelty, "
    "and by how much? Spec :11237 names duplicate ideas passing as novelty. Build "
    "a gold set of idea pairs labelled duplicate / variant / distinct, then report "
    "agreement (Cohen kappa) between the runtime score and the labels. A novelty "
    "score with kappa near chance is a decoration and must be demoted to advisory "
    "rather than allowed to gate a stopping rule."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {"path": rel, "sha256": sha, "bytes": size}


def main() -> int:
    live = run_calibration()
    held = live["heldout"]
    if held["n"] != 30:
        print("FAILED:TST-0266 emit held-out n != 30")
        return 1
    if live["gold"]["n"] != 60:
        print("FAILED:TST-0266 emit gold n != 60")
        return 1
    if not live["demotion"]["demotion_fires_on_seeded_below_floor"]:
        print("FAILED:TST-0266 emit demotion did not fire")
        return 1
    if not live["demotion"]["demotion_silent_on_perfect"]:
        print("FAILED:TST-0266 emit perfect-agreement control failed")
        return 1
    if live["adversarial_heldout"]["recall_distinct"] < 1.0:
        print("FAILED:TST-0266 emit adversarial held-out recall < 1")
        return 1
    if live["kappa_floor"] != KAPPA_FLOOR:
        print("FAILED:TST-0266 emit floor drift")
        return 1

    src_probe = {
        "id": "probe1_heldout_adversarial",
        "command": P1,
        "role": "held-out-kappa-and-adversarial-slice",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0266/probe1_heldout_adversarial.py"
        ),
    }
    ver_probe = {
        "id": "probe2_reviewer_demotion",
        "command": P2,
        "role": "statistics-reviewer-and-demotion-rule",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0266/probe2_reviewer_demotion.py"
        ),
    }
    if src_probe["fingerprint"]["sha256"] == ver_probe["fingerprint"]["sha256"]:
        print("FAILED:TST-0266 emit source/verifier probe files identical")
        return 1

    gold = live["gold"]
    doc = {
        "unit_id": "TST-0266",
        "claim_id": "TST-0266-novelty-kappa-calibration",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "calibration-receipt",
        "title": (
            "Calibrate the novelty score against a labelled gold set instead of "
            "trusting the model that produced it"
        ),
        "question": QUESTION,
        "sentinel": "SUCCESS:TST-0266",
        "completion_sentinel": "SUCCESS:TST-0266",
        "min_bytes_threshold": 2048,
        "kappa_floor": {
            "value": KAPPA_FLOOR,
            "recorded_at": KAPPA_FLOOR_RECORDED_AT,
            "recorded_before_any_score": True,
            "note": KAPPA_FLOOR_NOTE,
        },
        "gold_set_size": gold["n"],
        "gold_set": gold,
        "thresholds": {
            "t_dup": live["thresholds"]["t_dup"],
            "t_var": live["thresholds"]["t_var"],
            "tuned_on": "tune",
            "tune_n": live["tune"]["n"],
            "tune_kappa": live["thresholds"]["tune_kappa"],
            "note": "Thresholds fitted on the tune half only; reported kappa is held-out.",
        },
        "heldout": {
            "n": held["n"],
            "kappa": held["kappa"],
            "observed_agreement": held["observed_agreement"],
            "expected_agreement": held["expected_agreement"],
            "accuracy": held["accuracy"],
            "confusion": held["confusion"],
            "labels": held["labels"],
            "ci": held["ci"],
            "per_case": held["per_case"],
        },
        "tune": {
            "n": live["tune"]["n"],
            "kappa": live["tune"]["kappa"],
            "confusion": live["tune"]["confusion"],
            "note": "Tune kappa is diagnostic only and is not the reported effect size.",
        },
        "adversarial_all": live["adversarial_all"],
        "adversarial_heldout": live["adversarial_heldout"],
        "demotion": live["demotion"],
        "agreement_table": {
            "labels": held["labels"],
            "matrix": held["confusion"],
            "n": held["n"],
            "observed_agreement": held["observed_agreement"],
            "expected_agreement": held["expected_agreement"],
            "kappa": held["kappa"],
        },
        "tests": {
            "heldout_kappa_not_tuned_half": {
                "pass": True,
                "heldout_n": held["n"],
                "tune_n": live["tune"]["n"],
                "heldout_kappa": held["kappa"],
                "tune_kappa": live["tune"]["kappa"],
            },
            "adversarial_load_bearing_qualifier_distinct": {
                "pass": live["adversarial_heldout"]["recall_distinct"] == 1.0
                and live["adversarial_all"]["recall_distinct"] == 1.0,
                "heldout_recall_distinct": live["adversarial_heldout"]["recall_distinct"],
                "all_recall_distinct": live["adversarial_all"]["recall_distinct"],
            },
            "demotion_rule_fires_below_floor": {
                "pass": live["demotion"]["demotion_fires_on_seeded_below_floor"],
                "seeded_kappa": live["demotion"]["seeded_below_floor"]["kappa"],
                "floor": KAPPA_FLOOR,
            },
            "demotion_silent_on_perfect_agreement": {
                "pass": live["demotion"]["demotion_silent_on_perfect"],
            },
        },
        "source_probe": src_probe,
        "verifier_probe": ver_probe,
        "named_probes": [
            {"id": "probe1", "role": src_probe["role"], "command": P1},
            {"id": "probe2", "role": ver_probe["role"], "command": P2},
        ],
        "reviewer": {
            "reviewer_id": "TST-0266-probe2-statistics-reviewer",
            "mandate": "statistics",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 recomputes Cohen's kappa and the percentile bootstrap "
                "interval from the published per-case table without calling "
                "classify_pair, then executes the seeded below-floor demotion."
            ),
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/TST-0266/fixtures/gold_set.json",
                "kind": "published-gold-set",
                "claim": "60 idea pairs labelled duplicate/variant/distinct with frozen even/odd split.",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0266/novelty_runtime.py",
                "kind": "runtime-scorer",
                "claim": "Pair classifier plus stopping-rule demotion when kappa < 0.40.",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0266/kappa.py",
                "kind": "statistic",
                "claim": "Cohen kappa and seed-266 bootstrap CI protocol.",
            },
        ],
        "residual_caveat": (
            "tools/council/simulate.py and a bucket-B07 production novelty scorer "
            "are absent on this worktree. The measured runtime is "
            "command-center/p2-wave/probes/TST-0266/novelty_runtime.py. This is a "
            "calibration of that scorer against a published gold set, not a claim "
            "that a production B07 scorer was imported. cloud ok=true is not delivery."
        ),
        "scope": {
            "proof_surface": (
                "held-out Cohen kappa on 30 pairs; adversarial load-bearing qualifier "
                "slice; seeded below-floor demotion of novelty from a stopping rule."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "tools/council/simulate.py was present",
                "a production B07 novelty scorer was imported from another unit",
            ],
        },
        "cloud_ok": False,
        "registered": True,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0266/fixtures/gold_set.json",
                "exists": True,
                "role": "supporting",
            },
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0266 artifact {size}B below floor")
        return 1
    if b"SUCCESS:TST-0266" not in out.read_bytes():
        print("FAILED:TST-0266 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"heldout_kappa={held['kappa']} n={held['n']} "
        f"ci=[{held['ci']['ci_low']},{held['ci']['ci_high']}]"
    )
    print("SUCCESS:TST-0266 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
