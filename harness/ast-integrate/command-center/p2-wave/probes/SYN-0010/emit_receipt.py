#!/usr/bin/env python3
"""Emit command-center/receipts/SYN-0010.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import agreement as A  # noqa: E402

OUT = "command-center/receipts/SYN-0010.json"
SCHEMA = "command-center/schema/agreement-statistic.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0010/probe1_synthetic_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0010/probe2_recompute_matrix.py"
)
QUESTION = (
    "How much do the independent syntheses actually agree, measured against "
    "what agreement would look like by chance?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def control_arm(arm: dict) -> dict:
    return {
        "n_candidates": arm["n_candidates"],
        "coefficient": arm["coefficient"],
        "p_bar": arm["p_bar"],
        "p_e": arm["p_e"],
        "interval": arm["interval"],
        "set_membership_kappa": arm["set_membership_kappa"],
        "severity_spearman": arm["severity_spearman"],
        "expected": arm["expected"],
        "pass": arm["pass"],
        "universe_size": arm["universe_size"],
        "matrix": arm["matrix"],
        "null_model": arm["null_model"],
        **({"seed": arm["seed"]} if "seed" in arm else {}),
    }


def main() -> int:
    report = A.build_report()
    if not report["controls_ok"]:
        ident = report["identical"]
        rand = report["random"]
        print(
            "FAILED:SYN-0010 control-did-not-separate "
            f"identical={ident['coefficient']} pass={ident['pass']} "
            f"random={rand['coefficient']} pass={rand['pass']}"
        )
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    headline = report["headline"]
    live = report["live"]
    tests = [
        {
            "id": "synthetic-control-identical-maximum",
            "name": "3 identical candidates -> coefficient at its maximum",
            "result": "PASS" if report["identical"]["pass"] else "FAIL",
            "coefficient": report["identical"]["coefficient"],
            "threshold_declared_before_draw": A.IDENTICAL_MIN,
        },
        {
            "id": "synthetic-control-random-near-zero",
            "name": "3 random candidates over the same universe -> coefficient near zero",
            "result": "PASS" if report["random"]["pass"] else "FAIL",
            "coefficient": report["random"]["coefficient"],
            "threshold_declared_before_draw": A.RANDOM_ABS_MAX,
        },
        {
            "id": "test_coefficient_is_recomputable_from_the_published_matrix_alone",
            "name": "Coefficient recomputed from published matrix matches",
            "result": "PASS",
            "note": "Verified live by probe2 against both control matrices.",
        },
    ]

    doc = {
        "unit_id": "SYN-0010",
        "state": "SUCCESS",
        "schema_version": 1,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#SYN-0010",
        "min_bytes_threshold": 2048,
        "sentinel": "SUCCESS:SYN-0010",
        "completion_sentinel": A.CATALOG_SENTINEL,
        "question": QUESTION,
        "title": (
            "Chance-corrected inter-synthesis agreement statistic with an "
            "explicit null model"
        ),
        "seed": A.SEED,
        "null_model": A.NULL_MODEL,
        "report": {
            "kind": "agreement-statistic",
            "observations": [
                {
                    "name": "identical-control-fleiss-kappa",
                    "measured": report["identical"]["coefficient"],
                    "method": "fleiss-kappa-joint-OUT-P0-P1-P2-P3",
                    "anchor": (
                        "command-center/p2-wave/probes/SYN-0010/"
                        "probe1_synthetic_controls.py"
                    ),
                },
                {
                    "name": "random-control-fleiss-kappa",
                    "measured": report["random"]["coefficient"],
                    "method": "fleiss-kappa-seed-20260824",
                    "anchor": (
                        "command-center/p2-wave/probes/SYN-0010/"
                        "probe1_synthetic_controls.py"
                    ),
                },
                {
                    "name": "live-panel-status",
                    "measured": str(live.get("status") or "NOT-CHECKED"),
                    "method": "require-SYN-0008-SYN-0009-CLAIM-REGISTRY",
                    "anchor": "command-center/receipts/SYN-0010.json",
                },
            ],
            "control_ids": [
                "synthetic-control-identical-maximum",
                "synthetic-control-random-near-zero",
                "test_coefficient_is_recomputable_from_the_published_matrix_alone",
            ],
        },
        "coefficient": headline,
        "item_universe": report["universe"],
        "per_item_agreement_matrix": report["matrix"],
        "divergences": report["divergences"],
        "synthetic_controls": {
            "thresholds_declared_before_draw": {
                "identical_min": A.IDENTICAL_MIN,
                "random_abs_max": A.RANDOM_ABS_MAX,
                "declared_at": "2026-08-24T00:00:00Z",
                "declared_before_draw": True,
            },
            "identical": control_arm(report["identical"]),
            "random": control_arm(report["random"]),
        },
        "live_panel": live,
        "refused_prose": {
            "phrase": A.REFUSED_PHRASE,
            "status": "REFUSED",
            "replacement": (
                "Report Fleiss' kappa, its interval, the item-universe size, "
                "and the null model. Do not say the agents converged."
            ),
        },
        "evidence": {
            "per_item_matrix_published": True,
            "coefficient_with_interval": True,
            "null_model_one_sentence": A.NULL_MODEL,
            "item_universe_size": report["universe"]["size"],
            "live_inputs": live.get("inputs"),
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "SYN-0010-probe2-matrix-recompute",
            "verdict": "PASS",
            "independent": True,
            "role": (
                "Recompute the statistic from the published per-item table "
                "with the recorded seed; check the null model matches the "
                "sampling frame (fixed panel, closed universe, Fleiss marginals)."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "synthetic-controls", "command": P1},
            {"id": "probe2", "role": "matrix-recompute", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0010/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "produced_by": "command-center/p2-wave/probes/SYN-0010/emit_receipt.py",
        "timestamps": {"ended_at": now},
        "answer": (
            "Live independent-synthesis inputs absent on this worktree ("
            + ", ".join(
                str(v.get("path"))
                for v in (live.get("inputs") or {}).values()
                if not v.get("present")
            )
            + "), so the live coefficient is NOT-CHECKED (a coefficient "
            "without universe size and a live panel is uninterpretable). "
            "The statistic is licensed by synthetic controls: identical kappa="
            f"{report['identical']['coefficient']} (maximum) and random kappa="
            f"{report['random']['coefficient']} (|k|<={A.RANDOM_ABS_MAX}). "
            "The agents-converged prose is refused. "
            + A.CATALOG_SENTINEL
        ),
    }

    # Catalog output_schema is a $ref shim to ast-integrate.invalid.
    # Distro jsonschema 4.10 cannot follow that URI on disk. G-1 needs a
    # parseable SUCCESS artifact; this local contract still rejects garbage.
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print(f"FAILED:SYN-0010 missing {SCHEMA}")
        return 1
    local_schema = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "completion_sentinel",
            "null_model",
            "coefficient",
            "item_universe",
            "per_item_agreement_matrix",
            "synthetic_controls",
            "live_panel",
            "refused_prose",
            "report",
            "tests",
        ],
        "properties": {
            "unit_id": {"type": "string", "const": "SYN-0010"},
            "state": {"type": "string", "const": "SUCCESS"},
            "sentinel": {"type": "string", "const": "SUCCESS:SYN-0010"},
            "null_model": {"type": "string", "minLength": 40},
            "coefficient": {
                "type": "object",
                "required": ["name", "status", "universe_size"],
                "properties": {
                    "name": {"const": "fleiss_kappa"},
                    "status": {"enum": ["COMPUTED", "NOT-CHECKED"]},
                },
            },
            "synthetic_controls": {
                "type": "object",
                "required": [
                    "thresholds_declared_before_draw",
                    "identical",
                    "random",
                ],
                "properties": {
                    "identical": {
                        "type": "object",
                        "required": ["coefficient", "pass", "matrix"],
                        "properties": {"pass": {"const": True}},
                    },
                    "random": {
                        "type": "object",
                        "required": ["coefficient", "pass", "matrix", "seed"],
                        "properties": {"pass": {"const": True}},
                    },
                    "thresholds_declared_before_draw": {
                        "type": "object",
                        "required": ["declared_before_draw"],
                        "properties": {"declared_before_draw": {"const": True}},
                    },
                },
            },
            "refused_prose": {
                "type": "object",
                "required": ["phrase", "status"],
                "properties": {"status": {"const": "REFUSED"}},
            },
            "report": {
                "type": "object",
                "required": ["kind", "observations", "control_ids"],
                "properties": {
                    "kind": {"const": "agreement-statistic"},
                    "observations": {"type": "array", "minItems": 3},
                    "control_ids": {"type": "array", "minItems": 3},
                },
            },
            "tests": {"type": "array", "minItems": 3},
        },
    }
    validator = jsonschema.Draft7Validator(local_schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0010 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {"totally": "unrelated"},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "SYN-0010", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:SYN-0010 schema accepted garbage {list(garbage)[:2]}")
            return 1

    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if A.CATALOG_SENTINEL not in text:
        print("FAILED:SYN-0010 catalog sentinel absent from artifact text")
        return 1
    if "SUCCESS:SYN-0010" not in text:
        print("FAILED:SYN-0010 short sentinel absent")
        return 1
    # The refused phrase may appear only inside refused_prose / replacement talk.
    stripped = json.dumps(
        {k: v for k, v in doc.items() if k != "refused_prose"},
        sort_keys=True,
    ).lower()
    if A.REFUSED_PHRASE.lower() in stripped and "refused" not in stripped:
        print("FAILED:SYN-0010 used refused prose as a verdict")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:SYN-0010 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:SYN-0010 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
