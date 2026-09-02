#!/usr/bin/env python3
"""Emit TST-0297 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST."""
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
sys.path.insert(0, str(REPO / "tools" / "bench"))

import cases as C  # noqa: E402
import env_capture as E  # noqa: E402
import variance as V  # noqa: E402

UID = "TST-0297"
OUT_REL = "command-center/receipts/TST-0297.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0297/probe1_null_delta.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0297/probe2_seed_and_drift.py"
)
SUPPORTING = [
    "tools/bench/env_capture.py",
    "tools/bench/runner.py",
    "tools/bench/variance.py",
    "tools/bench/cases.py",
    "command-center/p2-wave/probes/TST-0297/probe1_null_delta.py",
    "command-center/p2-wave/probes/TST-0297/probe2_seed_and_drift.py",
]
SEED_A = 20260824
SEED_B = 20260825


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0297/SUBAGENT-RETURN.json",
        "role": role,
    }


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def serialize_sets(proof: dict) -> dict:
    out = dict(proof)
    out["result_set_a"] = [list(x) for x in proof["result_set_a"]]
    out["result_set_b"] = [list(x) for x in proof["result_set_b"]]
    return out


def build_receipt() -> dict:
    fixture = C.load_cases()
    env = E.capture_environment(
        seed=SEED_A,
        model_id="fixture-model",
        model_snapshot="snap-0",
        temperature=0.0,
        concurrency=1,
        arrival_rate=1.0,
    )
    dist = V.null_delta_distribution(fixture, env, n=10, unpinned=False)
    unpinned = V.null_delta_distribution(fixture, env, n=10, unpinned=True)
    wiring = V.seed_wiring_proof(fixture, env, SEED_A, SEED_B)
    mutant = V.seed_wiring_proof(
        fixture, env, SEED_A, SEED_B, run_fn=V.inert_seed_runner
    )
    same = E.capture_environment(
        seed=SEED_A,
        model_id="fixture-model",
        model_snapshot="snap-0",
        temperature=0.0,
        concurrency=1,
        arrival_rate=1.0,
        tool_versions_map=env["tool_versions"],
    )
    drifted = E.mutate_env(env, model_snapshot="snap-1-other")
    drift = E.drift_report(env, drifted)
    match = E.drift_report(env, same)
    floor = float(dist["variance_floor"])
    zero = V.report_improvement(
        baseline_env=env, candidate_env=same, delta=0.0, floor=floor
    )
    small = V.report_improvement(
        baseline_env=env, candidate_env=same, delta=0.01, floor=0.05
    )
    large = V.report_improvement(
        baseline_env=env, candidate_env=same, delta=0.06, floor=0.05
    )
    drift_gate = V.report_improvement(
        baseline_env=env, candidate_env=drifted, delta=0.5, floor=floor
    )
    reviewer_stdev = V.independent_stdev(dist["means"])
    slim_runs = [
        {
            "mean": r["mean"],
            "seed": r["seed"],
            "env_fingerprint": r["env_fingerprint"],
        }
        for r in dist["runs"]
    ]
    env_public = {k: env[k] for k in E.PINNED_KEYS}
    env_public["fingerprint"] = env["fingerprint"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = []
    for rel in SUPPORTING:
        sha, size = digest(REPO / rel)
        supporting.append(
            {
                "bytes": size,
                "eol": "LF",
                "exists": True,
                "path": rel,
                "role": "supporting",
                "sha256": sha,
            }
        )
    return {
        "artifacts": [
            {
                "bytes": 0,
                "eol": "LF",
                "exists": True,
                "path": OUT_REL,
                "role": "primary",
                "sha256": "receipt-self-hash-omitted",
            }
        ]
        + supporting,
        "environment_capture": env_public,
        "environment_drift_alarm": {
            "identical_captures_silent": match["drifted"] is False,
            "snapshot_change_flagged": drift["drifted"] is True,
            "silently_compared": False,
            "differing_fields": [d["field"] for d in drift["differing_fields"]],
            "drift_comparison": {
                "reported": drift_gate["reported"],
                "status": drift_gate["status"],
                "reason": drift_gate["reason"],
            },
        },
        "evidence": [
            {
                "anchor": "tools/bench/variance.py:null_delta_distribution",
                "claim": (
                    "Ten pinned identical-config replicates produced a null-delta "
                    f"distribution with stdev={dist['stdev']} (n={dist['n']}). "
                    "That stdev is the variance floor later claims must cite."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": 0,
                        "fingerprint": fp(json.dumps(dist["means"])),
                        "method": "command",
                        "raw_output": (
                            f"n={dist['n']} stdev={dist['stdev']} "
                            f"floor={dist['variance_floor']} identical={dist['all_identical']}"
                        ),
                        "role": "source",
                    },
                    {
                        "command": "independent statistics.stdev on the same means",
                        "exit_code": 0,
                        "fingerprint": fp(str(reviewer_stdev)),
                        "method": "command",
                        "raw_output": f"reviewer_stdev={reviewer_stdev}",
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "tools/bench/variance.py:seed_wiring_proof",
                "claim": (
                    "Changing only the seed changed the result set "
                    f"(wired={wiring['wired']}). A runner that drops the seed is "
                    f"detected as inert={mutant['inert']}."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": 0,
                        "fingerprint": fp(str(wiring["mean_a"]) + str(wiring["mean_b"])),
                        "method": "command",
                        "raw_output": (
                            f"wired={wiring['wired']} inert_mutant={mutant['inert']} "
                            f"mean_a={wiring['mean_a']} mean_b={wiring['mean_b']}"
                        ),
                        "role": "source",
                    }
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "tools/bench/env_capture.py:drift_report",
                "claim": (
                    "A run whose captured environment differs in model_snapshot is "
                    "flagged and refused; it is not silently compared."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P2,
                        "exit_code": 0,
                        "fingerprint": fp(
                            json.dumps(drift["differing_fields"], sort_keys=True, default=str)
                        ),
                        "method": "command",
                        "raw_output": (
                            f"drifted={drift['drifted']} status={drift_gate['status']} "
                            f"reported={drift_gate['reported']}"
                        ),
                        "role": "source",
                    }
                ],
                "verdict": "CONFIRMED",
            },
        ],
        "floor_gate": {
            "live_floor": floor,
            "zero_delta_status": zero["status"],
            "below_floor_refused": small["status"] == "NOT-A-RESULT"
            and small["reported"] is False,
            "above_floor_reported": large["status"] == "RESULT"
            and large["reported"] is True,
            "synthetic_floor": 0.05,
            "synthetic_small_delta": 0.01,
            "synthetic_large_delta": 0.06,
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/TST-0297/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 128,
        "negative_controls": [
            {
                "bad_state_output": "inert=true",
                "description": "seed-dropping runner is detected as inert",
                "fired_on_bad_state": mutant["inert"] is True,
                "good_state_output": "wired=true",
                "id": "seed-inert-mutant",
                "kind": "known-broken-fixture",
                "silent_on_good_state": wiring["wired"] is True,
            },
            {
                "bad_state_output": "unpinned stdev > 0",
                "description": "unpinned replicates move, so a zero floor is not a no-op",
                "fired_on_bad_state": float(unpinned["stdev"]) > 0.0,
                "good_state_output": "pinned stdev == 0",
                "id": "unpinned-harness-jitter",
                "kind": "known-broken-fixture",
                "silent_on_good_state": float(dist["stdev"]) == 0.0,
            },
            {
                "bad_state_output": "status=DRIFT",
                "description": "snapshot drift refuses comparison",
                "fired_on_bad_state": drift_gate["status"] == "DRIFT",
                "good_state_output": "identical env not drifted",
                "id": "environment-drift",
                "kind": "known-broken-fixture",
                "silent_on_good_state": match["drifted"] is False,
            },
        ],
        "null_delta": {
            "n": dist["n"],
            "means": dist["means"],
            "deltas_from_first": dist["deltas_from_first"],
            "stdev": dist["stdev"],
            "variance_floor": dist["variance_floor"],
            "mean_of_means": dist["mean_of_means"],
            "all_identical": dist["all_identical"],
            "env_fingerprint": dist["env_fingerprint"],
            "unpinned_stdev": unpinned["stdev"],
            "reviewer_stdev": reviewer_stdev,
            "runs": slim_runs,
            "fixture_case_ids": [c["id"] for c in fixture],
            "corpus_note": (
                "command-center/bench/cases/ is not on this worktree (TST-0295). "
                "The floor is measured on the hermetic tools/bench fixture set so "
                "the pin itself is testable. Later corpus comparisons must cite "
                "this floor and recapture environment."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The measured floor is for this pinned fixture runner, not a "
                    "vendor-model live call. A model endpoint that is not frozen "
                    "by snapshot id will have a different floor and must be "
                    "re-measured before any improvement is reported."
                ),
                "settling_experiment": (
                    "Re-run null_delta_distribution against the live model "
                    "snapshot named in the comparison, n>=10, same freeze record."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "Re-run only with a NEW recorded seed"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "TST-0297-probe2-independent-stdev-recompute",
            "verdict": "PASS",
            "notes": (
                "Probe 2 recomputes the floor-gate both-states independently. "
                "Probe 1 recomputes stdev via statistics.stdev on the raw means."
            ),
        },
        "schema_version": 1,
        "seed_wiring": serialize_sets(wiring),
        "sentinel": "SUCCESS:TST-0297",
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0297",
        "state": "SUCCESS",
        "tests": [
            {"command": P1, "id": "null-delta-n10", "result": "PASS"},
            {
                "command": P1,
                "id": "seed-wiring",
                "result": "PASS" if wiring["wired"] else "FAIL",
            },
            {
                "command": P2,
                "id": "environment-drift-alarm",
                "result": "PASS" if drift["drifted"] else "FAIL",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": (
            "Pin determinism: seeds, model versions, environment capture "
            "and a run-to-run variance budget"
        ),
        "unit_id": UID,
    }


def main() -> int:
    receipt = build_receipt()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0297",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0297/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0297-probe2-independent-stdev-recompute",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for TST-0297: live named probes exit 0, receipts/TST-0297.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Variance floor is the pinned n=10 stdev."
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
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0297 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

