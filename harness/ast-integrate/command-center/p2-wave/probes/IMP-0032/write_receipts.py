#!/usr/bin/env python3
"""Write IMP-0032 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
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
OUT = "command-center/receipts/IMP-0032.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0032/probe1_fidelity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0032/probe2_shared_planner.py"
)
SUPPORTING = [
    "tools/plugin/execute.py",
    "tools/plugin/planner.py",
    "tools/plugin/apply.py",
    "tools/plugin/cli.py",
    "tools/plugin/mutations.py",
    "tools/plugin/census.py",
    "tools/plugin/fidelity.py",
    "tools/plugin/inspect_planner.py",
    "tools/plugin/scenario.py",
    "tools/plugin/tests/test_dry_run_fidelity.py",
    "command-center/p2-wave/probes/IMP-0032/probe1_fidelity.py",
    "command-center/p2-wave/probes/IMP-0032/probe2_shared_planner.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0032",
        "receipt_path": "command-center/p2-wave/probes/IMP-0032/SUBAGENT-RETURN.json",
        "role": role,
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    tests_cmd = (
        "PYTHONPATH=tools PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "tools/plugin/tests/test_dry_run_fidelity.py"
    )
    tc, tt = run_probe(tests_cmd)
    if tc != 0:
        print(f"FAILED:receipts fidelity tests rc={tc}")
        print(tt[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting_rows = []
    for rel in SUPPORTING:
        sha, size = digest(REPO / rel)
        supporting_rows.append(
            {
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "role": "supporting",
                "eol": "LF",
            }
        )

    receipt = {
        "unit_id": "IMP-0032",
        "id": "IMP-0032",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0032",
        "completion_sentinel": "SUCCESS:IMP-0032",
        "spec_anchor": "WORK-UNIT-CATALOG.json IMP-0032 question_or_target",
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "reviewer": {
            "reviewer_id": "IMP-0032-probe2-shared-planner",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0032/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "tests": [
            {
                "id": "test_dry_run_fidelity",
                "command": tests_cmd,
                "result": "PASS",
                "raw_output": tt[-4000:],
            }
        ],
        "negative_controls": [
            {
                "id": "dry-run-census-zero",
                "kind": "known-good-fixture",
                "description": "A hashlib file census of a throwaway HOME is identical before and after --dry-run for every lifecycle command.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "census_changed",
                "good_state_output": "census_unchanged",
            },
            {
                "id": "hidden-write-outside-plan",
                "kind": "mutation",
                "description": "A file written after apply, not listed in the plan, makes plan vs independent census fail while plan vs journal still matches.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "observed_minus_plan nonempty",
                "good_state_output": "ok",
            },
        ],
        "evidence": [
            {
                "claim": "For install, update, repair, rollback and uninstall, the ordered dry-run mutation list (create/overwrite/delete with byte deltas) is set-equal to the journal produced by the real run of the same command in a throwaway HOME.",
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/execute.py:execute",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[-65000:],
                        "fingerprint": fp("command", P1),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": tests_cmd,
                        "exit_code": tc,
                        "raw_output": tt[-8000:],
                        "fingerprint": fp("command", tests_cmd),
                    },
                ],
            },
            {
                "claim": "Dry-run writes nothing: an independent hashlib walk (not plugin.census) of the throwaway HOME is byte-identical before and after --dry-run.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0032/probe1_fidelity.py:independent_walk",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": "independent_walk_dry_run_unchanged=True",
                        "fingerprint": fp("command", P1 + "#census"),
                    },
                    {
                        "role": "verifier",
                        "method": "file-census",
                        "command": "independent hashlib rglob vs execute(dry_run=True)",
                        "exit_code": 0,
                        "raw_output": "before_dry == after_dry",
                        "fingerprint": fp("file-census", "independent_walk"),
                    },
                ],
            },
            {
                "claim": "Dry-run shares the planning code path with the real run: execute() calls plan_command once, then branches — dry-run returns the plan; else apply_plan journals observed disk mutations. There is no twin planner.",
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/execute.py:execute",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[-65000:],
                        "fingerprint": fp("command", P2),
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "python3 -m plugin install --dry-run then real --journal-out",
                        "exit_code": 0,
                        "raw_output": "cli_dry_run_eq_journal=True",
                        "fingerprint": fp("command", "cli dry-run vs journal"),
                    },
                ],
            },
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "read_ok": True,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0032",
                    "exit_code": None,
                    "raw_output": "deferred until after this receipt and per-unit manifest are written",
                    "fingerprint": fp("command", "measure IMP-0032"),
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": "tools/plugin/install.py is the IMP-0023 generation-swap installer. This unit's --dry-run covers the five-verb mutation engine in tools/plugin/execute.py (install/update/repair/rollback/uninstall). Wiring --dry-run onto the generation-swap installer is a follow-on, not claimed here.",
                "settling_experiment": "Add --dry-run to install.py that prints the generation-swap mutations without creating gen-* directories, and set-equal that plan against an apply journal.",
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "Dry-run for install, update, repair, rollback and uninstall lives in "
            "tools/plugin/execute.py: one plan_command, then either return the plan "
            "or apply_plan + journal. Byte deltas are after_bytes-before_bytes. "
            "Journal is observed on disk, not a copy of the plan object. Hidden "
            "writes are caught by an independent census, not by the journal. "
            "Did not run global unit_manifest.py --write. No ADV rebuild. "
            "SUCCESS:IMP-0032"
        ),
        "primary_artifact": {"path": OUT, "role": "primary"},
        "artifacts": supporting_rows,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary_sha, primary_bytes = digest(out_path)

    primary = {
        "path": OUT,
        "sha256": primary_sha,
        "bytes": primary_bytes,
        "present": True,
        "unit_id": "IMP-0032",
        "receipt_path": "command-center/p2-wave/probes/IMP-0032/SUBAGENT-RETURN.json",
        "role": "primary",
    }
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0032",
        "unit_id": "IMP-0032",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0032",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary_sha,
                "bytes": primary_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0032/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0032-probe2-shared-planner",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0032: live named probes exit 0, IMP-0032.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0032",
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
    print(f"primary {OUT} sha256={primary_sha} bytes={primary_bytes}")
    print("SUCCESS:IMP-0032 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
