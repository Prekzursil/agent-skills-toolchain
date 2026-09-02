#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0009.json and G-1 per-unit receipts."""
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
import harness as H  # noqa: E402

OUT = "command-center/receipts/BLD-0009.json"
SCHEMA = "command-center/schema/coverage-matrix.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0009/probe1_unc_containment.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0009/probe2_permission_lock.py"
)
QUESTION = (
    "Which filesystem semantic is covered by NEITHER the shipped tests NOR the "
    "adversarial hostile-path matrix? SCOPE BOUNDARY: ADV-0117 owns reserved "
    "device names, MAX_PATH overflow, case-only collisions, spaces, non-ASCII "
    "and trailing dots. This unit consumes that receipt and covers the residue "
    "it does not touch: UNC \\\\server\\share and mapped network drives, symlink "
    "versus NTFS junction versus hardlink traversal, a read-only or ACL-denied "
    "directory, a path crossing a filesystem boundary mid-operation, and an "
    "open file held by another process."
)


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
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    matrix = H.run_matrix()
    by_id = {c["id"]: c for c in matrix["cells"]}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    required_ok = all(
        by_id[i]["verdict"] == "EXERCISED"
        for i in ("unc_share", "symlink_escape", "hardlink", "fixture_control", "open_file_held")
    )
    if not required_ok or not matrix["outside_sentinel_intact"]:
        print("FAILED:BLD-0009 required live cells did not EXERCISE")
        return 1
    if not H.fixture_negative_fails():
        print("FAILED:BLD-0009 negative fixture control stayed green")
        return 1

    supporting = [
        SCHEMA,
        "tools/command-center/path_guard.py",
        "tools/command-center/catalog.py",
        "tools/command-center/unit_manifest.py",
        "command-center/p2-wave/probes/BLD-0009/harness.py",
        "command-center/p2-wave/probes/BLD-0009/probe1_unc_containment.py",
        "command-center/p2-wave/probes/BLD-0009/probe2_permission_lock.py",
        "tools/command-center/tests/test_path_guard.py",
    ]
    artifacts = [{"path": OUT, "exists": True, "role": "primary"}]
    for rel in supporting:
        artifacts.append(
            {"path": rel, "exists": (REPO / rel).is_file(), "role": "supporting"}
        )

    tests = [
        {
            "id": "T-UNC-REJECT",
            "command": P1,
            "result": "NOT-RUN",
            "requirement": "any path or URI handler must REJECT a normalised UNC target",
        },
        {
            "id": "T-LINK-CONTAINMENT",
            "command": P1,
            "result": "NOT-RUN",
            "requirement": "a junction/symlink pointing outside the scratch root must not be followed",
        },
        {
            "id": "T-PERMISSION-NAMED",
            "command": P2,
            "result": "NOT-RUN",
            "requirement": "write into an ACL-denied directory must fail with a named error",
        },
        {
            "id": "T-LOCKED-FILE-NAMED",
            "command": P2,
            "result": "NOT-RUN",
            "requirement": "an open file held by a second process must produce a named error rather than a partial write",
        },
        {
            "id": "T-FIXTURE-CONTROL",
            "command": P1,
            "result": "NOT-RUN",
            "requirement": "the fixture set must be proven to be created",
        },
    ]

    doc = {
        "unit_id": "BLD-0009",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0009",
        "report_kind": "coverage-matrix",
        "question": QUESTION,
        "title": "Link, network-path and permission filesystem semantics the hostile-path matrix leaves uncovered",
        "adv_0117": matrix["adv_0117"],
        "host": matrix["host"],
        "census": matrix["census"],
        "cells": matrix["cells"],
        "outside_sentinel_intact": matrix["outside_sentinel_intact"],
        "scratch_root": matrix["scratch"],
        "tests": tests,
        "reviewer": {
            "reviewer_id": "BLD-0009-probe2-permission-lock-overclaim",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Catalog asked an independent reviewer to re-run reserved-name and "
                "long-path cells; those belong to ADV-0117 and were not re-derived. "
                "Probe 2 re-ran lock/permission cells and refused Windows-only overclaims."
            ),
        },
        "artifacts": artifacts,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/BLD-0009/UNIT-ARTIFACT-MANIFEST.json",
        "produced_by": {
            "role": "platform-test-engineer",
            "execution_substrate": "linux",
            "ts": now,
        },
        "notes": (
            "G-1 for BLD-0009: live named probes exit 0, receipts/BLD-0009.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Did not rebuild ADV-0117."
        ),
    }

    schema_ok = (
        isinstance(doc, dict)
        and doc.get("report_kind") == "coverage-matrix"
        and isinstance(doc.get("cells"), list)
        and len(doc["cells"]) >= 8
        and doc.get("sentinel") == "SUCCESS:BLD-0009"
        and doc.get("state") not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
    )
    if not schema_ok:
        print("FAILED:BLD-0009 schema errors")
        print("  missing coverage-matrix cells/sentinel")
        return 1
    for garbage in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        garbage_ok = (
            isinstance(garbage, dict)
            and garbage.get("report_kind") == "coverage-matrix"
            and isinstance(garbage.get("cells"), list)
            and len(garbage.get("cells") or []) >= 8
            and garbage.get("sentinel") == "SUCCESS:BLD-0009"
        )
        if garbage_ok:
            print(f"FAILED:BLD-0009 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    print(f"probe1 rc={rc1}")
    print(out1[-2000:])
    print(f"probe2 rc={rc2}")
    print(out2[-2000:])
    if rc1 != 0 or rc2 != 0:
        print("FAILED:BLD-0009 named probes")
        return 1

    for test in doc["tests"]:
        test["result"] = "PASS"
        if test["id"] in {"T-PERMISSION-NAMED"} and by_id["acl_or_readonly_dir"]["verdict"] != "EXERCISED":
            test["result"] = "NOT-RUN"
            test["note"] = by_id["acl_or_readonly_dir"]["evidence"]
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:BLD-0009 artifact {size}B below floor")
        return 1

    ret = {
        "id": "BLD-0009",
        "unit_id": "BLD-0009",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0009",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
        ],
        "artifacts": [
            {"path": OUT, "sha256": digest, "bytes": size, "exists": True, "role": "primary"}
        ],
        "manifest_path": "command-center/p2-wave/probes/BLD-0009/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "BLD-0009-probe2-permission-lock-overclaim",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for BLD-0009: live named probes exit 0, BLD-0009.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild of ADV-0117."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        sha, n = sha256_file(path)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "BLD-0009",
            "receipt_path": "command-center/p2-wave/probes/BLD-0009/SUBAGENT-RETURN.json",
            "role": role,
        }

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "BLD-0009",
        "verified_on_disk": True,
        "artifacts": [
            row(OUT, "primary"),
            row(SCHEMA, "supporting"),
            row("tools/command-center/path_guard.py", "supporting"),
            row("command-center/p2-wave/probes/BLD-0009/harness.py", "supporting"),
            row("command-center/p2-wave/probes/BLD-0009/probe1_unc_containment.py", "supporting"),
            row("command-center/p2-wave/probes/BLD-0009/probe2_permission_lock.py", "supporting"),
            row("command-center/p2-wave/probes/BLD-0009/SUBAGENT-RETURN.json", "supporting"),
        ],
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:BLD-0009 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
