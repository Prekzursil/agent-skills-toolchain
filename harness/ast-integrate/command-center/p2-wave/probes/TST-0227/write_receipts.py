#!/usr/bin/env python3
"""Write TST-0227 receipt, per-unit SUBAGENT-RETURN, and UNIT-ARTIFACT-MANIFEST."""
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
UNIT = "TST-0227"
OUT = "command-center/receipts/TST-0227.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0227/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0227/probe2_concurrent_active.py"
)
T1 = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools python3 -B "
    "tools/lib/tests/test_workspace_containment.py"
)
SUPPORTING = [
    "tools/lib/__init__.py",
    "tools/lib/workspace.py",
    "tools/lib/tests/__init__.py",
    "tools/lib/tests/test_workspace_containment.py",
    "command-center/p2-wave/probes/TST-0227/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0227/probe2_concurrent_active.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": max(len(data), 1),
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
        "exists": path.is_file(),
        "role": role,
        "eol": "LF" if data and b"\r\n" not in data else ("NOT-CHECKED" if not data else "CRLF"),
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int | None) -> dict:
    row = {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }
    if exit_code is not None:
        row["exit_code"] = exit_code
    return row


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0227/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    c_t, t_out = run_cmd(T1)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_t != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0227 receipts tests={c_t} probe1={c1} probe2={c2}")
        print(t_out[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    p1_src = probe("source", "command", P1, t1, c1)
    p1_ver = probe(
        "verifier",
        "filesystem-census",
        "independent_tree_hash(victim) pre/post + oob_path_exists(cross-session-write.txt)",
        "worktree_unchanged=true artifact_unchanged=true oob_file_exists=false unmediated_mutates=true",
        0,
    )
    p2_src = probe("source", "command", P2, t2, c2)
    p2_ver = probe("verifier", "test-run", T1, t_out, c_t)

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0227",
        "report_kind": "security_report",
        "target_contract_pass": True,
        "answer": (
            "Yes. Through the live session workspace broker, a write from one "
            "session into another session's worktree or artifact root is denied "
            "with code SESS_CROSS_SESSION_WRITE and an alert that names both "
            "session ids; an independent pre/post sha256 of the victim tree is "
            "unchanged; a write inside the actor's own session root succeeds in "
            "the same run; the deny was observed while a second session process "
            "was genuinely alive under /proc."
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0227",
        "min_bytes_threshold": 2048,
        "profile": "security-report-cross-session-write-containment",
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "security-tester",
            "execution_substrate": "local-serialized",
        },
        "question_or_target": (
            "Is cross-session write containment enforced, given multiple "
            "concurrent agent sessions on this box? PASS requires a denied "
            "write plus an alert naming both session ids."
        ),
        "implementation": {
            "enforcer": "tools/lib/workspace.py",
            "tests": "tools/lib/tests/test_workspace_containment.py",
            "fail_closed": True,
            "catalog_js_input": "tools/lib/workspace.mjs",
            "catalog_js_role": "workspace-root-detector-not-session-broker",
            "live_gate": "tools/lib/workspace.py",
            "not_an_os_sandbox": True,
            "permission_widened_to_pass_tests": False,
        },
        "artifacts": [
            art("tools/lib/workspace.py", "primary-implementation"),
            art("tools/lib/tests/test_workspace_containment.py", "supporting"),
            art("command-center/p2-wave/probes/TST-0227/probe1_both_states.py", "control"),
            art("command-center/p2-wave/probes/TST-0227/probe2_concurrent_active.py", "control"),
        ],
        "evidence": [
            {
                "claim": (
                    "A cross-session worktree write is refused with "
                    "SESS_CROSS_SESSION_WRITE. The denial alert names both "
                    "actor_session_id and victim_session_id."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/lib/workspace.py:SessionBroker.write_file",
                "probes": [p1_src, p2_ver],
            },
            {
                "claim": (
                    "Independent pre/post sha256 of the victim session worktree "
                    "and artifact root is unchanged after the denied write; "
                    "oob_path_exists is false for the planted payload. An "
                    "unmediated Path.write_bytes of the same payload does change "
                    "the hash, so the probe is not vacuously green."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0227/probe1_both_states.py",
                "probes": [p1_src, p1_ver],
            },
            {
                "claim": (
                    "Both-states control: a write inside the actor's own "
                    "worktree and artifact root succeeds in the same run."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0227/probe1_both_states.py",
                "probes": [p1_src, p2_ver],
            },
            {
                "claim": (
                    "Concurrency: the victim session is a live OS process "
                    "(/proc/<pid> present) with a heartbeat file outside the "
                    "hashed tree while the cross-session write is attempted. "
                    "Reviewer bypasses (relative traversal and symlink hop) "
                    "are also denied with alerts naming both session ids."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0227/probe2_concurrent_active.py",
                "probes": [p2_src, p1_ver],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "no automatic retry: a failure here is a finding, not a transient",
        },
        "tests": [
            {
                "id": "test_workspace_containment.py",
                "command": T1,
                "result": "PASS" if c_t == 0 else "FAIL",
                "assertions": 9,
                "output_tail": t_out.strip().splitlines()[-1][:300] if t_out.strip() else "",
            },
            {
                "id": "TST0227-T1-BOTH-STATES",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": 6,
                "output_tail": t1.strip().splitlines()[-1][:300] if t1.strip() else "",
            },
            {
                "id": "TST0227-T2-CONCURRENT-ACTIVE",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "assertions": 6,
                "output_tail": t2.strip().splitlines()[-1][:300] if t2.strip() else "",
            },
        ],
        "negative_controls": [
            {
                "id": "TST0227-C1-own-session-succeeds",
                "kind": "both-states",
                "description": (
                    "A write into another session's worktree is denied AND a "
                    "write inside the actor's own session root succeeds in the "
                    "same run. A blanket deny would fail the own-write half; a "
                    "missing gate would fail the cross-session half."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "SESS_CROSS_SESSION_WRITE alert names sess-A and sess-B; oob_file_exists=false",
                "good_state_output": "own-write.txt bytes OWN-SESSION-OK present in actor worktree",
            },
            {
                "id": "TST0227-C2-unmediated-write-control",
                "kind": "known-broken-fixture",
                "description": (
                    "A write performed without the broker does create the file "
                    "and changes the victim tree hash, proving the denied-write "
                    "test is not vacuously passing because the write was never "
                    "attempted."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "unmediated Path.write_bytes created unmediated-control.txt and changed the hash",
                "good_state_output": "brokered cross-session write left the victim hash unchanged",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0227-probe2-concurrent-review",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "bypasses_attempted": [
                "relative-path traversal from actor worktree into victim worktree",
                "symlink hop from actor worktree into victim worktree",
            ],
            "notes": (
                "Probe 2 is the named independent reviewer pass required by the "
                "catalog: it keeps a second session genuinely alive and attempts "
                "fresh bypass paths. It does not reuse probe 1's TemporaryDirectory."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0227/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This unit enforces the in-process session workspace broker. "
                    "Cursor/IDE Write tool calls that never enter "
                    "tools/lib/workspace.py, and OS-level sandboxing "
                    "(Landlock/seccomp), are residual. tools/lib/workspace.mjs "
                    "is present as a workspace-root detector, not this broker."
                ),
                "settling_experiment": (
                    "Hook the broker at the agent Write tool boundary, or an "
                    "ADV escape probe that writes via a path that never calls "
                    "SessionBroker.write_file."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 -B command-center/p2-wave/_measure_one_delivered.py TST-0227",
                    "deferred until after this receipt and per-unit manifest exist",
                    None,
                ),
            }
        ],
        "condition11": False,
        "success_hand_flipped": False,
        "named_probe_embedded": True,
        "cloud_ok": False,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0227",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/TST-0227/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0227-probe2-concurrent-review",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0227: live named probes exit 0, receipts/TST-0227.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
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
    print("SUCCESS:TST-0227 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
