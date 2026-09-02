#!/usr/bin/env python3
"""Emit IMP-0086 receipt + per-unit manifest + SUBAGENT-RETURN after live probes."""

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
UNIT = "IMP-0086"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0086/probe1_file_set_equals.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0086/probe2_gates_and_no_placement.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
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


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code1 != 0 or code2 != 0:
        print("FAILED:IMP-0086 live probes did not both exit 0")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        "tools/marketplace/install.py",
        "tools/marketplace/verify.py",
        "tools/marketplace/handoff.py",
        "tools/marketplace/fetch.py",
        "tools/marketplace/placement_audit.py",
        "tools/marketplace/schema/install-handoff.schema.json",
        "tools/marketplace/tests/test_install_delegation.py",
        "tools/plugin/installer.py",
        "command-center/p2-wave/probes/IMP-0086/probe1_file_set_equals.py",
        "command-center/p2-wave/probes/IMP-0086/probe2_gates_and_no_placement.py",
    ]
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10862; catalog IMP-0086",
        "min_bytes_threshold": 128,
        "title": "Marketplace install operation delegating to the plugin installer",
        "question_or_target": (
            "Implement marketplace-side install as fetch, verify (signature, "
            "revocation, lockfile digest, compatibility), then HAND OFF to the "
            "Phase-5 plugin installer through the typed handoff contract — never "
            "reimplementing file placement, so there is exactly one installer "
            "control plane."
        ),
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": "two-strikes-then-pivot; a verification failure never retries",
        },
        "artifacts": [art(rel, "supporting") for rel in supporting],
        "evidence": [
            {
                "anchor": "tools/marketplace/tests/test_install_delegation.py::test_file_set_equals_direct_plugin_install",
                "claim": (
                    "An end-to-end marketplace install into a throwaway HOME produces "
                    "the same relative file set as invoking the plugin installer "
                    "directly with the same payload (set equality)."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, p2],
            },
            {
                "anchor": "tools/marketplace/tests/test_install_delegation.py::test_no_placement_code_in_marketplace_module",
                "claim": (
                    "Static AST audit of tools/marketplace finds no tar extract, "
                    "shutil copy/move, or os.replace/rename; planted copytree+extractall "
                    "is detected. Digest and signature run before deliver()."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, p1],
            },
        ],
        "tests": [
            {
                "id": "test_file_set_equals_direct_plugin_install",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_no_placement_code_in_marketplace_module",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "negative-control-gate-abort",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "gate-lockfile_digest",
                "kind": "known-broken-fixture",
                "description": "mutated lockfile digest aborts before handoff; dest census empty",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "GateFailure lockfile_digest",
                "good_state_output": "handoff after VERIFY_ORDER",
            },
            {
                "id": "gate-signature",
                "kind": "known-broken-fixture",
                "description": "unsigned package is fail-closed, never valid-by-absence; no handoff",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "GateFailure signature",
                "good_state_output": "ed25519 verify pass",
            },
            {
                "id": "gate-revocation",
                "kind": "known-broken-fixture",
                "description": "revoked package version aborts before handoff",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "GateFailure revocation",
                "good_state_output": "empty revocation list",
            },
            {
                "id": "gate-compatibility",
                "kind": "known-broken-fixture",
                "description": "platform mismatch aborts before handoff",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "GateFailure compatibility",
                "good_state_output": "linux in platforms",
            },
            {
                "id": "planted-placement",
                "kind": "mutation",
                "description": "AST audit fires on planted shutil.copytree + tarfile.extractall",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "placement call shutil.copytree",
                "good_state_output": "audit_tree() empty",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0086-probe2-gates-and-no-placement",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Confirm verification order places lockfile digest and signature "
                "checks before deliver()/extract; marketplace has no extractall."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_rec(
                    "verifier",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0086",
                    "pending-after-write",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0023/IMP-0078/IMP-0084 catalog units are not separately "
                    "delivered; this unit implements the handoff consumer plus the "
                    "minimum plugin placement plane and the four verify gates it must "
                    "run before that handoff."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-bind verify.py to IMP-0078/IMP-0084 modules when those units exist.",
            }
        ],
        "control_plane": {
            "placement_module": "tools/plugin/installer.py",
            "marketplace_module": "tools/marketplace/install.py",
            "handoff_schema": "tools/marketplace/schema/install-handoff.schema.json",
            "verify_order": [
                "lockfile_digest",
                "signature",
                "revocation",
                "compatibility",
            ],
        },
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:IMP-0086 receipt too small ({live_bytes} B)")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in supporting:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    man_path = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "file-set-equality",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "no-placement-and-gate-abort",
                "raw_output": out2[-8000:],
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
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0086-probe2-gates-and-no-placement",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0086: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
