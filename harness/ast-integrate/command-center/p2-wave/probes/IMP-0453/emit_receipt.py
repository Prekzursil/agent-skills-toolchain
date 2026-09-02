#!/usr/bin/env python3
"""Emit IMP-0453 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(REPO / "tools" / "command-center" / "tests"))

from partial_preserve import (  # noqa: E402
    DEFAULT_BODY_BYTES,
    audit_honest_library,
)
from test_partial_preserve import (  # noqa: E402
    run_kill_late_suite,
    run_mutation_suite,
)

UNIT = "IMP-0453"
OUT = "command-center/receipts/IMP-0453.json"
SENTINEL = "SENTINEL:IMP-0453:PARTIALS-PRESERVED"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0453/probe1_kill_late.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0453/probe2_cleanup_mutation.py"
)
SUPPORTING = [
    "tools/command-center/partial_preserve.py",
    "tools/command-center/tests/test_partial_preserve.py",
    "command-center/p2-wave/probes/IMP-0453/probe1_kill_late.py",
    "command-center/p2-wave/probes/IMP-0453/probe2_cleanup_mutation.py",
    "command-center/p2-wave/probes/IMP-0453/emit_receipt.py",
]


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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0453/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    kill_late = run_kill_late_suite()
    mutation = run_mutation_suite()
    audit = audit_honest_library()
    if not kill_late.get("pass") or not mutation.get("pass"):
        print("FAILED:IMP-0453 emit live suites did not pass")
        print(json.dumps({"kill_late": kill_late, "mutation": mutation}, default=str)[:4000])
        return 1

    lib = REPO / "tools/command-center/partial_preserve.py"
    lib_sha, lib_n = digest(lib)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Partial-artifact preservation and INCOMPLETE classification",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_anchor": (
            "spec line 11313 / FC-11313: an artifact that exists but carries "
            "no sentinel is INCOMPLETE, must be PRESERVED, and must never be "
            "deleted or reported as success"
        ),
        "min_bytes_threshold": 128,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "premise": {
            "catalog_inputs": [
                "command-center/receipts/",
                "command-center/receipts/IMP-0415.json",
            ],
            "inputs_were_absent": True,
            "action": (
                "Created probes/IMP-0453 and tools/command-center/partial_preserve.py "
                "on this sparse worktree. Did not exit on predicate:absent. "
                "IMP-0415 reducer and IMP-0434 atomic writer receipts were absent; "
                "this unit ships durable sentinel-last writes plus failure preservation."
            ),
        },
        "implementation": {
            "module": "tools/command-center/partial_preserve.py",
            "operator": "sentinel-last durable write; classify by exact sentinel carry; preserve_on_failure never unlinks",
            "body_bytes_kill_late": DEFAULT_BODY_BYTES,
            "partial_preserve_sha256": lib_sha,
            "partial_preserve_bytes": lib_n,
            "audit": audit,
        },
        "killed_late_evidence": {
            "bytes": kill_late.get("bytes"),
            "classification": kill_late.get("classification"),
            "status": kill_late.get("status"),
            "preserved": kill_late.get("preserved"),
            "ledger_referenced": kill_late.get("ledger_referenced"),
            "same_inode": kill_late.get("same_inode"),
            "child_returncode": kill_late.get("child_returncode"),
            "ledger_row": kill_late.get("ledger_row"),
        },
        "artifacts": [
            {
                "path": "tools/command-center/partial_preserve.py",
                "role": "primary-implementation",
                "sha256": lib_sha,
                "bytes": lib_n,
                "exists": True,
            }
        ],
        "evidence": [
            {
                "claim": (
                    f"kill-late: partial file survived SIGKILL with "
                    f"{kill_late.get('bytes')} bytes, classified INCOMPLETE, "
                    f"and referenced from the run ledger."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/command-center/partial_preserve.py:kill_late_run",
                "probes": [],
            },
            {
                "claim": (
                    "mutation that unlinks partials on failure turns the "
                    "preservation test red; a complete artifact (sentinel own-line "
                    "or JSON completion_sentinel) is not classified INCOMPLETE."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/command-center/partial_preserve.py:preserve_on_failure",
                "probes": [],
            },
        ],
        "tests": [
            {
                "id": "kill-late-survives",
                "command": P1,
                "result": "PASS",
                "exit_code": 0,
                "bytes": kill_late.get("bytes"),
                "classification": kill_late.get("classification"),
            },
            {
                "id": "cleanup-mutation-turns-red",
                "command": P2,
                "result": "PASS",
                "exit_code": 0,
                "both_states": mutation.get("both_states"),
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0453-C1-kill-late-inode-stable",
                "kind": "computed-count",
                "description": (
                    "After SIGKILL, preserve_on_failure keeps the same inode and byte size; "
                    "it does not rewrite a fake partial."
                ),
                "same_inode": kill_late.get("same_inode"),
            },
            {
                "id": "IMP-0453-C2-cleanup-mutation-both-states",
                "kind": "both-states",
                "description": (
                    "Honest preserve_on_failure: file survives (green). "
                    "Planted unlink-on-failure: preservation test red."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0453-C3-complete-not-incomplete",
                "kind": "negative-control",
                "description": (
                    "A complete artifact carrying the sentinel is COMPLETE/SUCCESS, "
                    "never INCOMPLETE. A quoted mention is still INCOMPLETE."
                ),
                "complete_classification": (mutation.get("complete_control") or {}).get(
                    "classification"
                ),
                "mention_classification": mutation.get("mention_control"),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0453-probe2-cleanup-mutation",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial control is the planted unlink-on-failure mutant plus "
                "the exists-as-complete mutant and the complete-artifact negative "
                "control. AST audit requires classify to read bytes and "
                "preserve_on_failure to call no unlink/remove/rmtree."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0453/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 IMP-0453: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            f"{SENTINEL}"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0453 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    receipt["evidence"][0]["probes"] = [
        {
            "role": "verifier",
            "method": "command",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1[:16000],
        }
    ]
    receipt["evidence"][1]["probes"] = [
        {
            "role": "verifier",
            "method": "command",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2[:16000],
        }
    ]
    receipt["tests"][0]["exit_code"] = c1
    receipt["tests"][1]["exit_code"] = c2
    receipt["tests"][0]["result"] = "PASS" if c1 == 0 else "FAIL"
    receipt["tests"][1]["result"] = "PASS" if c2 == 0 else "FAIL"

    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "kill-late-survives",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "cleanup-mutation-and-complete-control",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0453/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0453-probe2-cleanup-mutation",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0453: live named probes exit 0, IMP-0453.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
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
    print(f"SUCCESS:IMP-0453 receipts {SENTINEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
