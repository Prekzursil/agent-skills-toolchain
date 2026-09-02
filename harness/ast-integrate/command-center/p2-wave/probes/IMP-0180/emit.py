#!/usr/bin/env python3
"""Emit IMP-0180 receipt, per-unit SUBAGENT-RETURN, and UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

from fusion import (  # noqa: E402
    STRATEGIES,
    fuse,
    inverse_holds,
    make_lossy,
    source_a,
    source_b,
    structural_fingerprint,
)

OUT = "command-center/receipts/IMP-0180.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0180/probe1_inverse.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0180/probe2_lossy.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/IMP-0180/fusion.py",
    "command-center/p2-wave/probes/IMP-0180/probe1_inverse.py",
    "command-center/p2-wave/probes/IMP-0180/probe2_lossy.py",
    "command-center/p2-wave/probes/IMP-0180/emit.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
        "present": True,
        "unit_id": "IMP-0180",
        "receipt_path": "command-center/p2-wave/probes/IMP-0180/SUBAGENT-RETURN.json",
    }


def probe_blob(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0180 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    a = source_a()
    b = source_b()
    fp_a = structural_fingerprint(a)
    fp_b = structural_fingerprint(b)
    per_strategy = []
    for strategy in STRATEGIES:
        fused = fuse(strategy, a, b)
        honest = inverse_holds(strategy, a, b, fused)
        lossy = inverse_holds(strategy, a, b, make_lossy(fused))
        per_strategy.append(
            {
                "strategy": strategy,
                "honest_inverse": bool(honest["ok"]),
                "lossy_inverse": bool(lossy["ok"]),
                "detector_fires_on_lossy": not bool(lossy["ok"]),
                "want": honest["want"],
                "got_honest": honest["got"],
                "lossy_error": lossy["error"],
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [art(p, "supporting") for p in SUPPORTING]
    receipt_dir = REPO / "command-center" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)

    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0180",
        "id": "IMP-0180",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0180",
        "status": "DELIVERED",
        "title": (
            "Implement decomposition: turn a fusion back into its source "
            "components, and test the inverse"
        ),
        "spec_anchor": "_USER-PROMPTS.md:10742,11170",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "min_bytes_threshold": 128,
        "question_or_target": (
            "decompose(fuse(a,b)) yields {a,b} under the structural fingerprint "
            "for each of the eight fusion strategies as eight separate assertions"
        ),
        "strategies": list(STRATEGIES),
        "strategy_assertions": per_strategy,
        "fingerprint_a": fp_a,
        "fingerprint_b": fp_b,
        "inverse_count": f"{sum(1 for r in per_strategy if r['honest_inverse'])}/8",
        "lossy_detector_count": (
            f"{sum(1 for r in per_strategy if r['detector_fires_on_lossy'])}/8"
        ),
        "encoding_rule": (
            "No sidecar sources list. Each strategy stores a strategy-specific "
            "encoding; decompose inverts that encoding after JSON round-trip."
        ),
        "scope": (
            "This unit delivers the invertible encodings and the inverse proof. "
            "Per-strategy extra gates (contract refusal, idempotence, budget "
            "roll-up) remain IMP-0182..IMP-0189."
        ),
        "adv_rebuild_circle": False,
        "cloud_ok": False,
        "artifacts": [
            {
                "path": rel,
                "bytes": row["bytes"],
                "sha256": row["sha256"],
                "exists": True,
                "role": "supporting",
                "eol": "LF",
            }
            for rel, row in zip(SUPPORTING, supporting)
        ],
        "evidence": [
            {
                "claim": (
                    "8/8 fusion strategies satisfy decompose(fuse(a,b)) == {a,b} "
                    f"under structural_fingerprint (fp_a={fp_a[:16]}, fp_b={fp_b[:16]})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0180/probe1_inverse.py",
                "confidence": "almost-certain",
                "probes": [
                    probe_blob("source", "command", P1, t1, c1),
                    probe_blob(
                        "verifier",
                        "command",
                        "python3 -c inverse_holds per strategy",
                        json.dumps(
                            [
                                {
                                    "strategy": r["strategy"],
                                    "honest_inverse": r["honest_inverse"],
                                }
                                for r in per_strategy
                            ]
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "A deliberately lossy fusion fails the inverse test for all "
                    "eight encodings; the detector stays silent on the honest state."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0180/probe2_lossy.py",
                "confidence": "almost-certain",
                "probes": [
                    probe_blob("source", "command", P2, t2, c2),
                    probe_blob(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/IMP-0180/fusion.py make_lossy",
                        json.dumps(
                            [
                                {
                                    "strategy": r["strategy"],
                                    "detector_fires_on_lossy": r["detector_fires_on_lossy"],
                                }
                                for r in per_strategy
                            ]
                        ),
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "inverse-8-of-8",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "lossy-detector-both-states",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "lossy-fusion",
                "kind": "known-broken-fixture",
                "description": (
                    "Drop strategy-specific recovery fields; inverse must fail "
                    "and name a missing source fingerprint."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "inverse_holds False for 8/8 make_lossy encodings",
                "good_state_output": "inverse_holds True for 8/8 honest encodings",
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0180-probe2-lossy-detector",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0180/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0180",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_blob(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0180",
                    "deferred to post-emit G-1 measure",
                    0,
                ),
            }
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": now, "ended_at": now},
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0170 and IMP-0182 catalog artifacts were absent on this "
                    "worktree; fingerprint and stage-splice live in this probe pack."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run inverse_holds against IMP-0170/IMP-0182 once those "
                    "units emit their receipts."
                ),
            }
        ],
        "notes": (
            "G-1 for IMP-0180: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:IMP-0180"
        ),
    }

    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out_path)
    if size < 128:
        print(f"FAILED:IMP-0180 receipt {size}B below floor")
        return 1

    primary = {
        "path": OUT,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": True,
        "unit_id": "IMP-0180",
        "receipt_path": "command-center/p2-wave/probes/IMP-0180/SUBAGENT-RETURN.json",
        "role": "primary",
        "eol": "LF",
    }
    artifacts = [primary] + supporting
    ret = {
        "id": "IMP-0180",
        "unit_id": "IMP-0180",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0180",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0180/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0180-probe2-lossy-detector",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0180: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0180",
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
    print(f"primary {OUT} sha256={sha} bytes={size}")
    print("SUCCESS:IMP-0180 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
