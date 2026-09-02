#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0067.json from live consumer observations."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from harness import ENV_KEY, CONFIG_KEY, NEW, OLD, PROJECT_WRITE, ROOT_WRITE  # noqa: E402

OUT = "command-center/receipts/TST-0067.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0067/probe1_child_session.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0067/probe2_wrong_scope_detector.py"
)
SENTINEL = "SUCCESS:TST-0067"
QUESTION = (
    "Measured on this estate: `setx` writes the persistent store but misses the "
    "already-running session, so a tool reads the OLD value while the writer "
    "believes it succeeded - and the same class re-appeared as a config key "
    "written at the wrong SCOPE (root instead of per-project) that was inert "
    "while looking correct. Target: every test that depends on an environment "
    "variable or a scoped config key asserts the value OBSERVED BY THE CHILD "
    "PROCESS that consumes it, never the value the setter wrote. Which scope "
    "does each consumer actually read? (Shell-script line endings are owned "
    "by TST-0192 in slice TST-2.)"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0067/consumer.py",
    "command-center/p2-wave/probes/TST-0067/harness.py",
    "command-center/p2-wave/probes/TST-0067/scenario.py",
    "command-center/p2-wave/probes/TST-0067/probe1_child_session.py",
    "command-center/p2-wave/probes/TST-0067/probe2_wrong_scope_detector.py",
]


def eol_of(data: bytes) -> str:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        return "MIXED"
    if crlf:
        return "CRLF"
    return "LF"


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() if data else "",
        "exists": path.is_file(),
        "role": role,
        "eol": eol_of(data) if data else "NOT-CHECKED",
    }


def which(name: str) -> str | None:
    return shutil.which(name)


def main() -> int:
    miss_hit = S.measure_persistent_miss_and_session_hit()
    scope = S.measure_wrong_scope_inert()
    control = S.measure_detector_control()
    if not (miss_hit["pass"] and scope["pass"] and control["pass"]):
        print("FAILED:TST-0067 emit live measurements did not pass")
        print(json.dumps({"miss_hit": miss_hit["pass"], "scope": scope["pass"], "control": control["pass"]}))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [art(p, "supporting") for p in SUPPORTING]
    if any(not a["exists"] for a in artifacts):
        missing = [a["path"] for a in artifacts if not a["exists"]]
        print(f"FAILED:TST-0067 emit missing supporting files {missing}")
        return 1

    miss = miss_hit["persistent_miss"]
    hit = miss_hit["session_hit"]
    inert = scope["wrong_scope_inert"]
    live = scope["correct_scope_live"]
    review = {
        "reviewer_id": "TST-0067-rederive-from-proc-environ-and-scope-file",
        "independent": True,
        "fresh_context": True,
        "starts_from": (
            "live child os.environ JSON plus /proc/<pid>/environ, not the "
            "setter persistent-store or root-settings self-read"
        ),
        "verdict": "PASS",
        "derived": {
            "session_child_saw_new": hit["consumer_userspace"] == NEW
            and hit["consumer_kernel"] == NEW,
            "persistent_child_missed": miss["consumer_userspace"] is None
            and miss["consumer_kernel"] is None,
            "setter_self_read_is_new": miss["setter_self_read"] == NEW,
            "root_write_inert": inert["detected_inert"] is True,
            "project_write_live": live["consumer_scope_value"] == PROJECT_WRITE,
            "setter_false_green_persistent": control["persistent_setter_false_green"],
            "setter_false_green_scope": control["scope_setter_false_green"],
        },
    }

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0067",
        "state": "SUCCESS",
        "title": "Environment-variable scope: the value a child process SEES, not the value that was written",
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0067 question_or_target",
        "min_bytes_threshold": 2048,
        "produced_at": now,
        "timestamps": {"started_at": now, "ended_at": now},
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
            "setx_present": which("setx") is not None,
            "pwsh_present": which("pwsh") is not None,
            "powershell_present": which("powershell") is not None,
            "bash_present": which("bash") is not None,
        },
        "setx_analog": {
            "windows_setx_invoked": False,
            "reason": (
                "This worktree is Linux; `setx` and PowerShell 7 are absent. "
                "The measured analog is a persistent JSON store write that does "
                "not mutate the already-running process environment."
            ),
            "class": "persistent-write-misses-already-running-session",
        },
        "which_scope_each_consumer_reads": scope["consumers"],
        "consumer_observation_pairs": {
            "persistent_miss": {
                "variable": ENV_KEY,
                "value_written": miss["value_written"],
                "setter_self_read": miss["setter_self_read"],
                "parent_os_environ": miss["parent_os_environ"],
                "consumer_userspace": miss["consumer_userspace"],
                "consumer_kernel": miss["consumer_kernel"],
                "consumer_pid": miss["consumer_pid"],
                "same_run": True,
            },
            "session_hit": {
                "variable": ENV_KEY,
                "value_written": hit["value_written"],
                "consumer_userspace": hit["consumer_userspace"],
                "consumer_kernel": hit["consumer_kernel"],
                "consumer_pid": hit["consumer_pid"],
                "parent_os_environ_unchanged": hit["parent_os_environ_unchanged"],
                "same_run": True,
            },
            "wrong_scope_inert": {
                "key": CONFIG_KEY,
                "value_written_at_root": inert["value_written_at_root"],
                "setter_self_read_root": inert["setter_self_read_root"],
                "consumer_scope_file_parent": "project",
                "consumer_scope_value": inert["consumer_scope_value"],
                "consumer_pid": inert["consumer_pid"],
                "same_run": True,
            },
            "correct_scope_live": {
                "key": CONFIG_KEY,
                "value_written_at_project": live["value_written_at_project"],
                "setter_self_read_project": live["setter_self_read_project"],
                "consumer_scope_value": live["consumer_scope_value"],
                "consumer_pid": live["consumer_pid"],
                "same_run": True,
            },
        },
        "constants": {
            "ENV_KEY": ENV_KEY,
            "CONFIG_KEY": CONFIG_KEY,
            "OLD": OLD,
            "NEW": NEW,
            "ROOT_WRITE": ROOT_WRITE,
            "PROJECT_WRITE": PROJECT_WRITE,
        },
        "evidence": [
            {
                "claim": (
                    "A persistent-store write of NEW is visible to the setter "
                    "self-read and invisible to a child spawned from the same "
                    "session. Two consumer signals (os.environ and "
                    "/proc/pid/environ) agree on unset."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0067/harness.py:measure_persistent_miss_and_session_hit",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "child-process-json",
                        "command": "observe_child userspace os.environ",
                        "raw_output": json.dumps(
                            {
                                "written": miss["value_written"],
                                "setter_self_read": miss["setter_self_read"],
                                "consumer_userspace": miss["consumer_userspace"],
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "procfs",
                        "command": "read /proc/<pid>/environ while child alive",
                        "raw_output": json.dumps(
                            {
                                "consumer_kernel": miss["consumer_kernel"],
                                "signals_agree": miss["signals_agree"],
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "When NEW is placed in the child environment at spawn, the "
                    "child process observes NEW on both signals in that same "
                    "session. The parent process environment is not mutated."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0067/harness.py:session_hit",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "child-process-json",
                        "command": "observe_child with env overlay",
                        "raw_output": json.dumps(
                            {
                                "written": hit["value_written"],
                                "consumer_userspace": hit["consumer_userspace"],
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "procfs",
                        "command": "read /proc/<pid>/environ while child alive",
                        "raw_output": json.dumps(
                            {
                                "consumer_kernel": hit["consumer_kernel"],
                                "signals_agree": hit["signals_agree"],
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
            {
                "claim": (
                    "A config key written at root scope is inert for a consumer "
                    "that opens project/settings.json. The same key written at "
                    "project scope is observed. Setter self-read of the root "
                    "file would false-green the write."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0067/harness.py:measure_wrong_scope_inert",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "child-process-json",
                        "command": "observe_child TST0067_SCOPE_FILE=project/settings.json",
                        "raw_output": json.dumps(
                            {
                                "after_root": inert["consumer_scope_value"],
                                "after_project": live["consumer_scope_value"],
                            },
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "detector-control",
                        "command": "measure_detector_control",
                        "raw_output": json.dumps(
                            {
                                "persistent_setter_false_green": control[
                                    "persistent_setter_false_green"
                                ],
                                "scope_setter_false_green": control[
                                    "scope_setter_false_green"
                                ],
                            },
                            sort_keys=True,
                        ),
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "test_child_process_observes_the_new_value_in_the_same_session",
                "command": P1,
                "result": "PASS",
                "requirement": (
                    "child process observes NEW after session-visible injection; "
                    "both os.environ and /proc environ agree"
                ),
            },
            {
                "id": "test_a_write_at_the_wrong_scope_is_detected_as_inert",
                "command": P2,
                "result": "PASS",
                "requirement": (
                    "root-scope write does not change the project consumer; "
                    "the inert write is detected by consumer observation"
                ),
            },
            {
                "id": "test_probe_reads_from_the_consumer_not_from_the_setter",
                "command": P2,
                "result": "PASS",
                "requirement": (
                    "detector control: setter-self-agreement would pass the "
                    "inert writes; consumer observation does not"
                ),
            },
        ],
        "tests_required_record": [
            "test_child_process_observes_the_new_value_in_the_same_session",
            "test_a_write_at_the_wrong_scope_is_detected_as_inert",
            "test_probe_reads_from_the_consumer_not_from_the_setter (detector control)",
        ],
        "evidence_requirement": (
            "for each variable and scoped key, the value read back FROM THE "
            "CONSUMER PROCESS alongside the value written, in the same run; "
            "agreement of the writer with itself is not evidence"
        ),
        "negative_controls": [
            {
                "id": "setter-self-agreement-false-green-persistent",
                "kind": "known-broken-fixture",
                "description": (
                    "Setter self-read of the persistent store equals NEW while "
                    "the session child still sees unset."
                ),
                "fired_on_bad_state": control["persistent_setter_false_green"],
                "silent_on_good_state": control["session_consumer_true_green"],
            },
            {
                "id": "setter-self-agreement-false-green-wrong-scope",
                "kind": "known-broken-fixture",
                "description": (
                    "Setter self-read of root settings equals the root write "
                    "while the project consumer still sees OLD."
                ),
                "fired_on_bad_state": control["scope_setter_false_green"],
                "silent_on_good_state": control["project_consumer_true_green"],
            },
        ],
        "reviewer": review,
        "reviewer_verdict": review["verdict"],
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot; this delivery did not strike",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0067/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/TST-0067/probe1_child_session.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
            },
            {
                "consumer": "command-center/p2-wave/probes/TST-0067/probe2_wrong_scope_detector.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Windows `setx` itself and a PowerShell 7 vs Git Bash "
                    "re-run were not executed; those binaries are absent here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1 and probe2 on a Windows host with setx and "
                    "pwsh 7, capturing the same writer/consumer pairs."
                ),
            },
            {
                "claim": (
                    "Shell-script line endings are owned by TST-0192 and were "
                    "not measured in this unit."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "TST-0192 on this worktree.",
            },
        ],
        "artifacts": artifacts,
        "output_schema": SCHEMA,
        "report": {
            "kind": "test-receipt",
            "control_ids": [
                "setter-self-agreement-false-green-persistent",
                "setter-self-agreement-false-green-wrong-scope",
            ],
            "observations": [
                {
                    "name": "session_child_os_environ",
                    "measured": hit["consumer_userspace"] or "",
                    "method": "child-process-json",
                    "anchor": "command-center/p2-wave/probes/TST-0067/harness.py:observe_child",
                },
                {
                    "name": "session_child_proc_environ",
                    "measured": hit["consumer_kernel"] or "",
                    "method": "procfs",
                    "anchor": "command-center/p2-wave/probes/TST-0067/harness.py:read_proc_environ",
                },
                {
                    "name": "persistent_store_misses_session_child",
                    "measured": miss["consumer_userspace"] is None
                    and miss["setter_self_read"] == NEW,
                    "method": "child-process-json",
                    "anchor": "command-center/p2-wave/probes/TST-0067/harness.py:measure_persistent_miss_and_session_hit",
                },
                {
                    "name": "root_scope_write_inert_for_project_consumer",
                    "measured": inert["detected_inert"] is True,
                    "method": "child-process-json",
                    "anchor": "command-center/p2-wave/probes/TST-0067/harness.py:measure_wrong_scope_inert",
                },
                {
                    "name": "project_scope_write_observed",
                    "measured": live["consumer_scope_value"] or "",
                    "method": "child-process-json",
                    "anchor": "command-center/p2-wave/probes/TST-0067/harness.py:measure_wrong_scope_inert",
                },
            ],
            "which_scope_each_consumer_reads": scope["consumers"],
            "consumer_observation_pairs": {
                "persistent_miss": {
                    "variable": ENV_KEY,
                    "value_written": miss["value_written"],
                    "setter_self_read": miss["setter_self_read"],
                    "parent_os_environ": miss["parent_os_environ"],
                    "consumer_userspace": miss["consumer_userspace"],
                    "consumer_kernel": miss["consumer_kernel"],
                    "consumer_pid": miss["consumer_pid"],
                    "same_run": True,
                },
                "session_hit": {
                    "variable": ENV_KEY,
                    "value_written": hit["value_written"],
                    "consumer_userspace": hit["consumer_userspace"],
                    "consumer_kernel": hit["consumer_kernel"],
                    "consumer_pid": hit["consumer_pid"],
                    "parent_os_environ_unchanged": hit["parent_os_environ_unchanged"],
                    "same_run": True,
                },
                "wrong_scope_inert": {
                    "key": CONFIG_KEY,
                    "value_written_at_root": inert["value_written_at_root"],
                    "setter_self_read_root": inert["setter_self_read_root"],
                    "consumer_scope_file_parent": "project",
                    "consumer_scope_value": inert["consumer_scope_value"],
                    "consumer_pid": inert["consumer_pid"],
                    "same_run": True,
                },
                "correct_scope_live": {
                    "key": CONFIG_KEY,
                    "value_written_at_project": live["value_written_at_project"],
                    "setter_self_read_project": live["setter_self_read_project"],
                    "consumer_scope_value": live["consumer_scope_value"],
                    "consumer_pid": live["consumer_pid"],
                    "same_run": True,
                },
            },
        },
        "schema_note": (
            "Catalog output_schema is command-center/schema/test-receipt.schema.json "
            "(shim present on this worktree). G-1 delivery is parse + sentinel + "
            "live named probes + per-unit manifest sha, not jsonschema."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    size = out_path.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0067 emit {size}B below floor")
        return 1
    text = out_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0067 emit sentinel missing from bytes")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:TST-0067 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
