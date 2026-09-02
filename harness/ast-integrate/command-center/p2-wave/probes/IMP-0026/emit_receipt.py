#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0026.json from live probes and tests."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin import trees as T  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0026.json"
TEST = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_rollback_preserves_foreign_files.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0026/probe1_rehearsal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0026/probe2_census.py"
)
SUPPORTING = [
    "tools/plugin/rollback.py",
    "tools/plugin/trees.py",
    "tools/plugin/tests/test_rollback_preserves_foreign_files.py",
    "command-center/p2-wave/probes/IMP-0026/probe1_rehearsal.py",
    "command-center/p2-wave/probes/IMP-0026/probe2_census.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "present": True,
        "role": role,
    }


def main() -> int:
    c_test, t_test = run(TEST)
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0026 emit probes c_test={c_test} c1={c1} c2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    owned_from = sorted(T.OWNED_V2)
    owned_to = sorted(T.OWNED_V1)
    foreign = sorted(T.FOREIGN_PATHS)
    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    receipt = {
        "unit_id": "IMP-0026",
        "id": "IMP-0026",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0026",
        "title": "`rollback` command that cannot remove existing commands or user data",
        "question_or_target": (
            "Implement rollback to a previous version from the rollback manifest "
            "such that commands, skills, and user data introduced OUTSIDE the "
            "rolled-back version survive. The seeded failure class is 'rollback "
            "removes existing commands or user data'; the rollback must compute a "
            "set difference, not restore a snapshot wholesale."
        ),
        "answer": (
            "Set-difference rollback at tools/plugin/rollback.py restores only "
            "owned_to paths from the target payload and unlinks only "
            "owned_from − owned_to. Live paths outside owned_from are foreign "
            "and are never unlinked or overwritten (clash refuses). A throwaway "
            "HOME rehearsal kept commands/user-created.md byte-identical. An "
            "independent payload-derived hash census matched the post-rollback "
            "tree (v1 ∪ foreign). Wholesale snapshot restore deleted all three "
            "foreign paths, so the preservation test discriminates. "
            "Rollback-then-reinstall returned the original hash census. "
            "SUCCESS:IMP-0026"
        ),
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_anchor": "_USER-PROMPTS.md:11347 (rollback removes existing commands or user data)",
        "seeded_failure_class": "rollback removes existing commands or user data",
        "mechanism": "set-difference over owned path sets; not wholesale snapshot restore",
        "owner_approval_required": True,
        "live_tree_touched": False,
        "throwaway_home_only": True,
        "cloud_ok": False,
        "registered": True,
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0026/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "rollback": {
            "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin/rollback.py",
            "mode": "set-difference",
            "from_version": "2.0.0",
            "to_version": "1.0.0",
            "owned_from": owned_from,
            "owned_to": owned_to,
            "foreign_paths": foreign,
            "refuse_overwrite_foreign": True,
            "wholesale_is_negative_control_only": True,
        },
        "evidence": [
            {
                "id": "E1-rehearsal",
                "claim": (
                    "A rollback rehearsal in a throwaway HOME seeded with a "
                    "user-created command file still has that file afterwards, "
                    "byte-identical."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0026/probe1_rehearsal.py",
                "probes": [
                    {
                        "id": "probe1",
                        "role": "source",
                        "command": P1,
                        "exit_code": c1,
                        "method": "command",
                        "raw_output": t1,
                    }
                ],
            },
            {
                "id": "E2-census",
                "claim": (
                    "Independent pre/post inventory hash census equals the set "
                    "derived from PAYLOAD_V1 ∪ FOREIGN, not from rollback()'s "
                    "own added/removed lists. Changed paths reviewed against "
                    "that expected set."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0026/probe2_census.py",
                "probes": [
                    {
                        "id": "probe2",
                        "role": "verifier",
                        "command": P2,
                        "exit_code": c2,
                        "method": "command",
                        "raw_output": t2,
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "test_rollback_preserves_foreign_files",
                "command": TEST,
                "result": "PASS" if c_test == 0 else "FAIL",
                "exit_code": c_test,
                "raw_output": t_test,
            },
            {
                "id": "probe1-rehearsal",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "probe2-census",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "wholesale-snapshot-restore",
                "kind": "mutant-implementation",
                "description": (
                    "wholesale_snapshot_restore wipes live and copies v1. The "
                    "same foreign_preserved predicate returns False; all three "
                    "foreign paths are absent. Set-difference rollback keeps them."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state": "wholesale-snapshot-restore",
                "good_state": "set-difference rollback",
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0026-probe2-census",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 recomputes expected post-census from payload maps and "
                "does not trust probe 1's existence check or rollback report lists."
            ),
        },
        "artifacts": artifacts,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "role": "throwaway-HOME-rehearsal"},
            {"id": "probe2", "command": P2, "exit_code": c2, "role": "independent-hash-census"},
        ],
        "retry": {
            "count": 0,
            "policy": "no automatic retry; every attempt requires a fresh backup (IMP-0030)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree has no platform/plugin/ and no live owner HOME. "
                    "Rehearsal used a throwaway prefix only."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": "Owner-gated rehearsal against a real profile after IMP-0030 backup.",
            }
        ],
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 for IMP-0026: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }
    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    sha, size = digest(dest)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0026 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
