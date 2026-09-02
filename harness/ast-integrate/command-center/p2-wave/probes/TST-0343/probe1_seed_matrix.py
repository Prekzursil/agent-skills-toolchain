#!/usr/bin/env python3
"""Probe 1: live 10-seed outcome matrix + planted seed-dependent control.

Catalog tests_required[0]: suite run across at least 10 seeds; matrix published.
Catalog tests_required[2]: plant a seed-dependent test and confirm it is detected.
Evidence: seeds used and per-test outcome matrix. A single-seed green run
cannot support a seed-independence claim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import seed_registry as SR  # noqa: E402

ART = REPO / "command-center/receipts/TST-0343.json"
OUT = HERE / "probe1-seed-matrix.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0343-probe1 {msg}")
    return 1


def main() -> int:
    report = SR.run_sweep()
    if report["n_seeds"] < 10:
        return fail(f"n_seeds={report['n_seeds']} want >=10")
    if len(report["seeds"]) != len(set(report["seeds"])):
        return fail("duplicate seeds")
    if report["n_tests"] < 4:
        return fail(f"n_tests={report['n_tests']}")

    # Full matrix: every test x every seed has PASS/FAIL.
    for spec in SR.specs():
        row = report["matrix"].get(spec.id) or {}
        if set(row.keys()) != {str(s) for s in report["seeds"]}:
            return fail(f"matrix holes for {spec.id}")
        if any(v not in {"PASS", "FAIL"} and not str(v).startswith("ERROR") for v in row.values()):
            return fail(f"non-outcome in {spec.id}: {row}")

    if not report["planted_narrow_detected"]:
        return fail("planted seed-dependent test was not detected")
    if SR.PLANTED_NARROW_ID not in report["varying_ids"]:
        return fail("planted narrow id not in varying_ids")
    if SR.PLANTED_NARROW_ID not in report["narrow_assertion_ids"]:
        return fail("planted narrow not classified narrow-assertion")

    planted = next(r for r in report["rows"] if r["id"] == SR.PLANTED_NARROW_ID)
    if planted["per_seed"].get(str(SR.PLANTED_NARROW_SEED)) != "PASS":
        return fail("planted narrow did not PASS on its lucky seed")
    if planted["pass_count"] != 1:
        return fail(f"planted narrow pass_count={planted['pass_count']} want 1")
    if planted["undeclared_sensitivity"] is not True:
        return fail("planted narrow was not flagged as undeclared sensitivity")

    # Seed-robust declared-sensitive tests must stay STABLE.
    for tid in (
        "test_arithmetic_stable",
        "test_string_roundtrip",
        "test_unit_interval",
        "test_shuffle_preserves_multiset",
    ):
        row = next(r for r in report["rows"] if r["id"] == tid)
        if row["class"] != SR.STABLE:
            return fail(f"{tid} class={row['class']} want stable")
        if set(row["per_seed"].values()) != {"PASS"}:
            return fail(f"{tid} not all-PASS: {row['per_seed']}")

    payload = {
        "probe": "probe1-seed-matrix",
        "unit_id": "TST-0343",
        "pass": True,
        "n_seeds": report["n_seeds"],
        "seeds": report["seeds"],
        "n_tests": report["n_tests"],
        "matrix": report["matrix"],
        "varying_ids": report["varying_ids"],
        "narrow_assertion_ids": report["narrow_assertion_ids"],
        "planted_narrow_detected": True,
        "planted_narrow_pass_count": planted["pass_count"],
        "lucky_seed": SR.PLANTED_NARROW_SEED,
    }

    if ART.is_file():
        receipt = json.loads(ART.read_text(encoding="utf-8"))
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:TST-0343" not in text:
            return fail("sentinel-absent")
        if receipt.get("unit_id") != "TST-0343":
            return fail("receipt unit_id")
        live = (receipt.get("report") or {}).get("sweep") or {}
        if live.get("n_seeds") != report["n_seeds"]:
            return fail("receipt n_seeds disagrees with live re-run")
        if live.get("seeds") != report["seeds"]:
            return fail("receipt seeds disagree with live re-run")
        if live.get("matrix") != report["matrix"]:
            return fail("receipt matrix disagrees with live re-run")
        payload["receipt_matches_live"] = True
    else:
        payload["receipt_matches_live"] = False

    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(
        f"n_seeds={report['n_seeds']} n_tests={report['n_tests']} "
        f"varying={report['varying_ids']} planted_narrow=True"
    )
    print("SUCCESS:TST-0343-probe1 10-seed matrix; planted seed-dependent test detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
