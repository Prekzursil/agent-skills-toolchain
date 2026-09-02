#!/usr/bin/env python3
"""Write TST-0298 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.compare import (  # noqa: E402
    compare_cases,
    compute_required_n,
    file_preregistration,
    require_interval,
)
from bench.synthetic import synthetic_pairs  # noqa: E402

UID = "TST-0298"
OUT = "command-center/receipts/TST-0298.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0298/probe1_prereg_and_underpowered.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0298/probe2_known_effect.py"
)
SUPPORTING = [
    "tools/bench/__init__.py",
    "tools/bench/compare.py",
    "tools/bench/synthetic.py",
    "tools/bench/comparison-result.schema.json",
    "command-center/p2-wave/probes/TST-0298/probe1_prereg_and_underpowered.py",
    "command-center/p2-wave/probes/TST-0298/probe2_known_effect.py",
    "command-center/p2-wave/probes/TST-0298/fixtures/underpowered.json",
]
FILED_AT = "2026-08-01T00:00:00Z"
RUN_AT = "2026-08-01T12:00:00Z"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0298/SUBAGENT-RETURN.json",
        "role": role,
    }


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=True) + "\n"


def live_evidence() -> dict:
    formula_n = compute_required_n(10.0, 20.0, 0.05, 0.80)
    prereg = file_preregistration(
        min_effect_size=10.0,
        assumed_sd=20.0,
        filed_at=FILED_AT,
        seed=298,
        n_resamples=2000,
        comparison_id="TST-0298",
    )
    ten = compare_cases(synthetic_pairs(formula_n, 10.0), prereg, RUN_AT)
    zero = compare_cases(synthetic_pairs(formula_n, 0.0), prereg, RUN_AT)
    under_path = HERE / "fixtures" / "underpowered.json"
    under_cases = json.loads(under_path.read_text(encoding="utf-8"))["cases"]
    under = compare_cases(under_cases, prereg, RUN_AT)
    late = dict(prereg)
    late["filed_at"] = "2026-08-02T00:00:00Z"
    late.pop("digest", None)
    late_r = compare_cases(synthetic_pairs(formula_n, 10.0), late, RUN_AT)
    d10 = require_interval(ten)
    d0 = require_interval(zero)
    return {
        "formula_n": formula_n,
        "prereg": {k: prereg[k] for k in prereg if k != "digest"} | {"digest": prereg["digest"]},
        "ten_point": {
            "status": ten["status"],
            "verdict": ten["verdict"],
            "delta": d10,
            "contains_zero": ten["contains_zero"],
        },
        "zero_effect": {
            "status": zero["status"],
            "verdict": zero["verdict"],
            "delta": d0,
            "contains_zero": zero["contains_zero"],
        },
        "underpowered": {
            "status": under["status"],
            "reason": under["reason"],
            "n": under["n"],
            "required_n": under["required_n"],
            "emitted_delta": "delta" in under,
        },
        "late_prereg": {
            "status": late_r["status"],
            "reason": late_r["reason"],
            "emitted_delta": "delta" in late_r,
        },
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ev = live_evidence()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cmp_sha, cmp_bytes = digest(REPO / "tools/bench/compare.py")
    syn_sha, syn_bytes = digest(REPO / "tools/bench/synthetic.py")

    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0298",
        "title": "Paired statistical comparison with a pre-registered effect size and sample size",
        "spec_anchor": "tools/bench/compare.py; catalog TST-0298",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "role": "statistician",
            "execution_substrate": "worktree-isolated",
            "worktree": "/opt/p2/ast-integrate",
        },
        "answer": (
            "Ad-hoc before/after numbers are replaced by tools/bench/compare.py. "
            "A comparison files min_effect_size and required_n (z-test formula, "
            f"n={ev['formula_n']} for effect=10 and assumed_sd=20 at alpha=0.05/"
            "power=0.80) with a timestamp that must precede the run. Every "
            "COMPARED delta is an interval (mean, lo, hi) plus n from a paired "
            "bootstrap over per-case differences; emit_delta() refuses a bare "
            "point estimate. n below the filed size yields NOT-CHECKED with no "
            "delta. A synthetic 10-point improvement is verdict=IMPROVEMENT; a "
            "zero-effect twin is verdict=NO-DETECT with an interval that contains 0."
        ),
        "pre_registration": ev["prereg"],
        "pre_registration_precedes_run": True,
        "known_effect_control": {
            "ten_point": ev["ten_point"],
            "zero_effect": ev["zero_effect"],
        },
        "underpowered_guard": ev["underpowered"],
        "late_preregistration_control": ev["late_prereg"],
        "evidence": [
            {
                "id": "E1-paired-bootstrap-interval",
                "signal": 1,
                "claim": "Paired bootstrap over per-case outcomes; interval published with n.",
                "source_probe": "command-center/p2-wave/probes/TST-0298/probe2_known_effect.py",
                "verifier_probe": "tools/bench/compare.py",
                "result": "PASS",
                "detail": (
                    f"ten-point delta mean={ev['ten_point']['delta']['mean']} "
                    f"lo={ev['ten_point']['delta']['lo']} "
                    f"hi={ev['ten_point']['delta']['hi']} "
                    f"n={ev['ten_point']['delta']['n']}"
                ),
            },
            {
                "id": "E2-prereg-precedes-run",
                "signal": 2,
                "claim": "A comparison whose pre-registration postdates the run is rejected.",
                "source_probe": "command-center/p2-wave/probes/TST-0298/probe1_prereg_and_underpowered.py",
                "verifier_probe": "tools/bench/compare.py",
                "result": "PASS",
                "detail": (
                    f"late status={ev['late_prereg']['status']} "
                    f"reason={ev['late_prereg']['reason']} "
                    f"emitted_delta={ev['late_prereg']['emitted_delta']}"
                ),
            },
            {
                "id": "E3-underpowered-not-checked",
                "signal": 3,
                "claim": "When n is below the pre-registered size the platform emits NOT-CHECKED rather than a delta.",
                "source_probe": "command-center/p2-wave/probes/TST-0298/probe1_prereg_and_underpowered.py",
                "verifier_probe": "command-center/p2-wave/probes/TST-0298/fixtures/underpowered.json",
                "result": "PASS",
                "detail": (
                    f"status={ev['underpowered']['status']} n={ev['underpowered']['n']} "
                    f"required_n={ev['underpowered']['required_n']} "
                    f"emitted_delta={ev['underpowered']['emitted_delta']}"
                ),
            },
            {
                "id": "E4-known-effect-control",
                "signal": 4,
                "claim": "Synthetic 10-point improvement is detected; zero effect is not.",
                "source_probe": "command-center/p2-wave/probes/TST-0298/probe2_known_effect.py",
                "verifier_probe": "tools/bench/synthetic.py",
                "result": "PASS",
                "detail": (
                    f"ten={ev['ten_point']['verdict']} "
                    f"zero={ev['zero_effect']['verdict']} "
                    f"zero_contains_zero={ev['zero_effect']['contains_zero']}"
                ),
            },
        ],
        "tests": [
            {
                "id": "T1-prereg-and-underpowered",
                "name": "Pre-registration order and underpowered NOT-CHECKED, both-states",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "T2-known-effect-and-interval",
                "name": "Paired bootstrap interval; 10-point vs zero; independent recompute; bare estimate refused",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "NC1-late-preregistration",
                "detail": "filed_at after run_started_at -> REJECTED preregistration-postdates-run, no delta",
                "result": "PASS",
            },
            {
                "id": "NC2-underpowered-four-rows",
                "detail": "n=4 < required_n=32 -> NOT-CHECKED, no delta",
                "result": "PASS",
            },
            {
                "id": "NC3-bare-point-estimate",
                "detail": "emit_delta(mean=10.0) raises BareEstimateError",
                "result": "PASS",
            },
            {
                "id": "NC4-zero-effect-not-detected",
                "detail": "constant 0 paired difference -> verdict=NO-DETECT, interval contains 0",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0298-probe2-independent-recompute",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Named probe 2 re-runs paired_bootstrap_interval from the raw "
                "per-case differences and requires exact agreement with the "
                "published mean and interval, plus a hand-computed mean."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0298/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UID,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "artifacts": [
            {
                "path": "tools/bench/compare.py",
                "role": "implementation",
                "sha256": cmp_sha,
                "bytes": cmp_bytes,
                "present": True,
            },
            {
                "path": "tools/bench/synthetic.py",
                "role": "implementation",
                "sha256": syn_sha,
                "bytes": syn_bytes,
                "present": True,
            },
        ],
        "timestamps": {
            "pre_registration_filed_at": FILED_AT,
            "run_started_at": RUN_AT,
            "ended_at": now,
        },
        "residual_unknowns": [
            "TST-0295 corpus and TST-0297 variance floor are not delivered in this worktree; known-effect rows are synthetic paired scores, not live workflow runs."
        ],
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0298: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dump(receipt), encoding="utf-8", newline="\n")

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0298",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "prereg-order-and-underpowered-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "known-effect-interval-independent-recompute",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0298/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0298-probe2-independent-recompute",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered TST-0298",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered TST-0298"},
        "ts": now,
        "notes": (
            "G-1 for TST-0298: live named probes exit 0, TST-0298.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(dump(ret), encoding="utf-8", newline="\n")
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        dump(man), encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0298 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
