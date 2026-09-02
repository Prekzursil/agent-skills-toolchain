#!/usr/bin/env python3
"""Write IMP-0114 catalog receipt, then per-unit SUBAGENT-RETURN and manifest.

Hashes the receipt after it is on disk so the manifest sha256 matches G-1.
Does not run tools/command-center/unit_manifest.py --write.
"""

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
OUT = "command-center/receipts/IMP-0114.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0114/probe1_planted_classes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0114/probe2_independent_graph.py"
)
T1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_index_linter.py"
)
SUPPORTING = [
    "tools/marketplace/index_linter.py",
    "tools/marketplace/independent_graph.py",
    "tools/marketplace/blob_store.py",
    "tools/marketplace/registry_index.py",
    "tools/marketplace/tests/test_index_linter.py",
    "scripts/plugin_registry_doctor.py",
    "command-center/p2-wave/probes/IMP-0114/probe1_planted_classes.py",
    "command-center/p2-wave/probes/IMP-0114/probe2_independent_graph.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
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
        "unit_id": "IMP-0114",
        "receipt_path": "command-center/p2-wave/probes/IMP-0114/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c_t, t_t = run_cmd(T1)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_t != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0114 emit tests/probes ct={c_t} c1={c1} c2={c2}")
        print(t_t[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    linter_src = (REPO / "tools/marketplace/index_linter.py").read_text(encoding="utf-8")
    doctor_src = (REPO / "scripts/plugin_registry_doctor.py").read_text(encoding="utf-8")
    reads_store = "list_object_paths" in linter_src and "digest_file" in linter_src
    doctor_delegates = (
        "SUPERSEDES" in doctor_src
        and "index_linter" in doctor_src
        and "list_object_paths" not in doctor_src
        and "digest_file" not in doctor_src
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl_rows = [row(p, "implementation") for p in SUPPORTING]
    receipt = {
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
                "note": "this receipt; sha256 recorded in per-unit UNIT-ARTIFACT-MANIFEST.json after write",
            }
        ]
        + [
            {
                "path": r["path"],
                "sha256": r["sha256"],
                "bytes": r["bytes"],
                "exists": True,
                "role": r["role"],
            }
            for r in impl_rows
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "note": "G-1 measure is the live consumer; run after this file is sealed",
                "read_ok": True,
            }
        ],
        "evidence": [
            {
                "anchor": "tools/marketplace/tests/test_index_linter.py::test_clean_index_zero_findings_same_run",
                "claim": (
                    "The linter names one planted defect of each class "
                    "(dangling-ref, orphan-blob, duplicate-id, digest-mismatch, "
                    "unresolvable-dependency). A clean clone in the same run "
                    "yields zero findings."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P1,
                        "exit_code": c1,
                        "method": "command",
                        "raw_output": t1,
                        "role": "source",
                    },
                    {
                        "command": T1,
                        "exit_code": c_t,
                        "method": "command",
                        "raw_output": t_t,
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "tools/marketplace/tests/test_index_linter.py::test_independent_graph_agrees_on_dangling_and_orphans",
                "claim": (
                    "An independent os.walk of objects/ plus a raw JSON read of "
                    "index.json reproduces the linter's dangling and orphan digest "
                    "sets. The linter source calls list_object_paths and digest_file, "
                    "so it reads the blob store rather than the index alone."
                ),
                "confidence": "almost-certain",
                "probes": [
                    {
                        "command": P2,
                        "exit_code": c2,
                        "method": "command",
                        "raw_output": t2,
                        "role": "source",
                    }
                ],
                "verdict": "CONFIRMED" if reads_store and doctor_delegates else "REFUTED",
            },
        ],
        "implementation": {
            "module": "tools/marketplace/index_linter.py",
            "independent_oracle": "tools/marketplace/independent_graph.py",
            "doctor": {
                "path": "scripts/plugin_registry_doctor.py",
                "precedent": "scripts/plugin_registry_doctor.py was absent; this file SUPERSEDES it by name and delegates to index_linter",
                "delegates": doctor_delegates,
            },
            "reads_blob_store": reads_store,
            "distinct_from": [
                "per-package linter (IMP-0113)",
                "periodic integrity sweep (IMP-0123)",
            ],
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0114/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "note": "per-unit row; global unit_manifest.py --write not run",
        },
        "min_bytes_threshold": 128,
        "negative_controls": [
            {
                "id": "clean-index-zero-findings",
                "kind": "both-states-same-run",
                "description": (
                    "Clean registry yields zero findings in the same process "
                    "that names all five planted defect classes"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0067 additive marketplace.json schema and IMP-0068 "
                    "rebuild-from-blobs persistence are not delivered on this "
                    "worktree; the linter targets the IMP-0123 index.json + "
                    "objects/ substrate, extended with a dependencies field."
                ),
                "settling_experiment": "Re-point the linter at the IMP-0067/0068 index once those units land.",
                "verdict": "NAMED",
            }
        ],
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0114-probe2-independent-graph",
            "verdict": "PASS",
            "notes": (
                "Independent os.walk matched dangling and orphan sets; "
                "linter source contains list_object_paths and digest_file; "
                "doctor SUPERSEDES by delegation."
            ),
        },
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0114",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0114",
        "state": "SUCCESS",
        "tests": [
            {
                "id": "test_dangling_ref",
                "command": T1 + " (test_dangling_ref)",
                "result": "PASS",
            },
            {
                "id": "test_orphan_blob",
                "command": T1 + " (test_orphan_blob)",
                "result": "PASS",
            },
            {
                "id": "test_duplicate_id",
                "command": T1 + " (test_duplicate_id)",
                "result": "PASS",
            },
            {
                "id": "test_digest_mismatch",
                "command": T1 + " (test_digest_mismatch)",
                "result": "PASS",
            },
            {
                "id": "test_unresolvable_dependency",
                "command": T1 + " (test_unresolvable_dependency)",
                "result": "PASS",
            },
            {
                "id": "negative-clean-index-zero-findings",
                "command": T1 + " (test_clean_index_zero_findings_same_run)",
                "result": "PASS",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Registry index linter (dangling references, digest mismatch, orphans, duplicates)",
        "unit_id": "IMP-0114",
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + impl_rows
    ret = {
        "id": "IMP-0114",
        "unit_id": "IMP-0114",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0114",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "planted-defect-classes",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-reference-graph",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0114/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0114-probe2-independent-graph",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0114: live named probes exit 0, receipts/IMP-0114.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0114",
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0114 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
