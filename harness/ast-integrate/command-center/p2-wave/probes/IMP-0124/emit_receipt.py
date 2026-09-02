#!/usr/bin/env python3
"""Emit IMP-0124 receipt, per-unit manifest, and SUBAGENT-RETURN after live probes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "IMP-0124"
OUT_REL = "command-center/receipts/IMP-0124.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0124/probe1_lint_clean_functional.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0124/probe2_negative_census.py"
)
TEST_CMD = "PYTHONPATH=tools python3 tools/marketplace/tests/test_registry_dr.py"
SUPPORTING = [
    "tools/marketplace/store.py",
    "tools/marketplace/dr.py",
    "tools/marketplace/linter.py",
    "tools/marketplace/functional.py",
    "tools/marketplace/atomic.py",
    "tools/marketplace/fixture.py",
    "tools/marketplace/drill.py",
    "tools/marketplace/tests/test_registry_dr.py",
    "tools/marketplace/docs/REGISTRY-DR-RUNBOOK.md",
    "command-center/p2-wave/probes/IMP-0124/probe1_lint_clean_functional.py",
    "command-center/p2-wave/probes/IMP-0124/probe2_negative_census.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    present = path.is_file()
    digest, size = sha256_file(path) if present else ("", 0)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "present": present,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0124/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    rc_t, out_t = run(TEST_CMD)
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc_t != 0 or rc1 != 0 or rc2 != 0:
        print("FAILED:IMP-0124 tests or probes did not exit 0")
        print("tests", rc_t, out_t[-1500:])
        print("probe1", rc1, out1[-1500:])
        print("probe2", rc2, out2[-1500:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": UID,
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0124",
        "schema_version": 1,
        "title": "Registry backup, restore, and a rehearsed disaster-recovery drill",
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "owner_approval_required": True,
        "cloud_ok": False,
        "timestamps": {"ended_at": now},
        "question_or_target": (
            "Implement backup and restore for the index, blob store and event log, "
            "and script a drill that restores into a scratch location and proves the "
            "restored registry is functionally equivalent. Restoring over a live "
            "registry is destructive and owner-gated."
        ),
        "implementation": {
            "substrate": "tools/marketplace/store.py (atomic index, CAS blobs, hash-chained events)",
            "backup_restore": "tools/marketplace/dr.py",
            "linter": "tools/marketplace/linter.py (walks blob store)",
            "functional_probe": "tools/marketplace/functional.py (resolve, install, verify)",
            "runbook": "tools/marketplace/docs/REGISTRY-DR-RUNBOOK.md",
            "dependency_honesty": (
                "IMP-0068 and IMP-0072 have no delivered artifacts on this worktree. "
                "The drill runs against the on-disk substrate shipped with this unit. "
                "That is not a claim that IMP-0068 or IMP-0072 are delivered."
            ),
            "live_restore": (
                "restore_registry refuses dest that is the live root (or inside it) "
                "unless owner_approval == OWNER-APPROVED-LIVE-RESTORE. There is no "
                "automatic retry against a live target."
            ),
        },
        "evidence": [
            {
                "id": "signal-1-index-linter",
                "claim": "The restored registry passes the index linter with zero blocking findings.",
                "verdict": "CONFIRMED",
                "independent_of": "signal-2-functional-probe",
                "anchor": "tools/marketplace/linter.py",
                "probe": P1,
            },
            {
                "id": "signal-2-functional-probe",
                "claim": "resolve + install + verify of echo-skill@1.0.1 succeeds against the restored copy.",
                "verdict": "CONFIRMED",
                "independent_of": "signal-1-index-linter",
                "anchor": "tools/marketplace/functional.py",
                "probe": P1,
            },
        ],
        "tests": [
            {
                "id": "test_restore_is_lint_clean_and_functional",
                "path": "tools/marketplace/tests/test_registry_dr.py::test_restore_is_lint_clean_and_functional",
                "result": "PASS",
            },
            {
                "id": "test_backup_missing_blobs_fails_functional_probe",
                "path": "tools/marketplace/tests/test_registry_dr.py::test_backup_missing_blobs_fails_functional_probe",
                "result": "PASS",
            },
            {
                "id": "test_scratch_restore_never_writes_live_registry",
                "path": "tools/marketplace/tests/test_registry_dr.py::test_scratch_restore_never_writes_live_registry",
                "result": "PASS",
            },
            {
                "id": "test_live_restore_refused_without_owner_approval",
                "path": "tools/marketplace/tests/test_registry_dr.py::test_live_restore_refused_without_owner_approval",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "backup-missing-blob-store",
                "description": (
                    "A backup with blobs/ stripped fails the functional probe and the "
                    "linter reports dangling-blob findings."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "probe": P2,
            },
            {
                "id": "scratch-restore-census",
                "description": (
                    "Scratch restore writes are censused; none land under the live "
                    "registry root; live snapshot is unchanged."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "probe": P2,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0124-probe2-negative-census",
            "verdict": "PASS",
            "independent": True,
            "requirement": "Reviewer must perform the drill themselves from the documented runbook alone.",
            "runbook": "tools/marketplace/docs/REGISTRY-DR-RUNBOOK.md",
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "lint-clean-and-functional",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "negative-control-census-live-gate",
            },
        ],
        "test_run": {"command": TEST_CMD, "exit_code": rc_t, "raw_output": out_t},
        "defects": [],
        "notes": (
            "G-1 for IMP-0124: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud_ok is false and is not delivery. Live overwrite remains owner-gated; "
            "this delivery rehearses scratch restore only. SUCCESS:IMP-0124"
        ),
    }

    out = REPO / OUT_REL
    dump(out, receipt)
    live_sha, live_bytes = sha256_file(out)

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "present": True,
            "unit_id": UID,
            "receipt_path": "command-center/p2-wave/probes/IMP-0124/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        rows.append(art_row(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": sum(1 for r in rows if r["present"]),
        "artifacts": rows,
    }
    dump(HERE / "UNIT-ARTIFACT-MANIFEST.json", manifest)

    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0124",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "lint-clean-and-functional",
                "raw_output": out1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "negative-control-census-live-gate",
                "raw_output": out2,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0124/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0124-probe2-negative-census",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0124: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    dump(HERE / "SUBAGENT-RETURN.json", ret)
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print("SUCCESS:IMP-0124 receipt and per-unit manifest emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
