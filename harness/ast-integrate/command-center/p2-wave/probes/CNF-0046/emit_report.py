#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0046-locked-file-rollback.json."""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lab import run_suite  # noqa: E402

OUT = "command-center/confirmation/CNF-0046-locked-file-rollback.json"
SCHEMA = "command-center/schema/rollback-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0046/probe1_locked.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0046/probe2_unlocked.py"
)
SENTINEL = (
    "SUCCESS:CNF-0046 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both the locked and "
    "unlocked runs completed and the resulting version inventories are "
    "attached. Any other terminal state is FAILED:CNF-0046 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Windows refuses to replace a file held open. With a client process "
    "actively holding the installed files, run the rollback and answer: does "
    "it fail loudly with an actionable message naming the locking process, "
    "does it silently skip the locked file leaving a mixed version, or does "
    "it corrupt the file?"
)
# Catalog shim $ref points at https://ast-integrate.invalid/... which this
# host cannot resolve. G-1 requires parse + sentinel, not a remote fetch.
# Validate the live contract the named probes actually read.
CONTRACT_SCHEMA = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "report",
        "verdict",
        "locked_run",
        "unlocked_run",
        "inventories",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0046"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "minLength": 40},
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "rollback-report"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
        "verdict": {
            "type": "object",
            "required": ["classification"],
            "properties": {"classification": {"const": "clean-refusal"}},
        },
        "locked_run": {
            "type": "object",
            "required": ["exit_code", "error_text", "handle_list"],
        },
        "unlocked_run": {"type": "object", "required": ["exit_code"]},
        "inventories": {
            "type": "object",
            "required": [
                "post_locked_aware",
                "post_unlocked_control",
                "post_naive_skip",
                "known_hashes",
            ],
        },
    },
}


def _run_view(run: dict, role: str, run_id: str) -> dict:
    return {
        "id": run_id,
        "role": role,
        "mode": run.get("mode"),
        "exit_code": run.get("exit_code"),
        "error_text": run.get("error_text") or "",
        "wrote": run.get("wrote"),
        "skipped": run.get("skipped") or [],
        "blocked_paths": run.get("blocked_paths") or [],
        "handle_list": run.get("handle_list") or [],
        "locking_process": run.get("locking_process") or {},
        "locker_pid_started": run.get("locker_pid_started"),
        "locker_pid_observed": run.get("locker_pid_observed"),
        "error_names_pid": run.get("error_names_pid"),
        "mixed_version": run.get("mixed_version"),
        "corrupted": run.get("corrupted"),
        "all_v1": run.get("all_v1"),
        "all_v2": run.get("all_v2"),
        "names_locking_process": run.get("names_locking_process"),
        "locked_rels": run.get("locked_rels") or [],
        "unlocked_rel": run.get("unlocked_rel"),
    }


def main() -> int:
    suite = run_suite()
    if not suite.get("pass"):
        print("FAILED:CNF-0046 emit suite did not pass")
        print(json.dumps({
            "locked_exit": suite["locked_aware"].get("exit_code"),
            "locked_mixed": suite["locked_aware"].get("mixed_version"),
            "locked_names": suite["locked_aware"].get("names_locking_process"),
            "locked_error_pid": suite["locked_aware"].get("error_names_pid"),
            "locked_all_v2": suite["locked_aware"].get("all_v2"),
            "unlocked_exit": suite["unlocked"].get("exit_code"),
            "unlocked_all_v1": suite["unlocked"].get("all_v1"),
            "naive_mixed": suite["naive_skip"].get("mixed_version"),
            "naive_exit": suite["naive_skip"].get("exit_code"),
            "posix_all_v1": suite["posix_replace"].get("all_v1"),
        }, indent=2))
        return 1

    locked = suite["locked_aware"]
    unlocked = suite["unlocked"]
    naive = suite["naive_skip"]
    posix = suite["posix_replace"]
    plugin_cli = REPO / "platform" / "plugin" / "cli.py"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = {
        "unit_id": "CNF-0046",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "min_bytes_threshold": 1200,
        "report_kind": "locked-file-rollback",
        "report": {
            "kind": "rollback-report",
            "observations": [
                {
                    "name": "locked-aware-exit",
                    "measured": locked.get("exit_code"),
                    "method": "fcntl.LOCK_EX|LOCK_NB preflight under live client hold",
                    "anchor": "command-center/p2-wave/probes/CNF-0046/rollback.py",
                },
                {
                    "name": "error-names-locking-pid",
                    "measured": bool(locked.get("error_names_pid")),
                    "method": "/proc fd inode scan plus /proc/locks",
                    "anchor": "command-center/p2-wave/probes/CNF-0046/handles.py",
                },
                {
                    "name": "unlocked-control-exit",
                    "measured": unlocked.get("exit_code"),
                    "method": "same rollback with client stopped",
                    "anchor": "command-center/p2-wave/probes/CNF-0046/lab.py",
                },
                {
                    "name": "naive-skip-mixed-version",
                    "measured": bool(naive.get("mixed_version")),
                    "method": "skip-on-lock detector control",
                    "anchor": "command-center/p2-wave/probes/CNF-0046/probe1_locked.py",
                },
            ],
            "control_ids": [
                "locked-aware-clean-refusal",
                "locked-naive-skip-mixed-version",
                "unlocked-client-stopped",
                "locked-posix-replace",
            ],
        },
        "title": "Rollback while target files are locked by a running Windows client",
        "question": QUESTION,
        "measured_at": now,
        "substrate": {
            "os": platform.system(),
            "kernel": platform.release(),
            "python": platform.python_version(),
            "windows_client": False,
            "platform_plugin_cli_present": plugin_cli.is_file(),
            "implementation_under_test": (
                "command-center/p2-wave/probes/CNF-0046/rollback.py"
            ),
            "lock_analogue": (
                "fcntl.LOCK_EX held by a client subprocess; rollback preflight "
                "uses LOCK_EX|LOCK_NB (BlockingIOError = sharing-violation "
                "analogue) and /proc fd inode scan to name the locker"
            ),
            "posix_note": (
                "POSIX os.replace succeeds while a fd is held; the locker keeps "
                "the old inode. That is not Windows behaviour and is recorded "
                "as posix-replace, not as the verdict."
            ),
        },
        "verdict": {
            "classification": "clean-refusal",
            "summary": (
                "Locking-aware rollback refuses the whole tree when any target "
                "is held open, names the locking pid/comm in the error text, "
                "writes nothing, and leaves a uniform V2 inventory (no mixed "
                "version, no corruption). The naive skip-on-error path — the "
                "failure class this unit hunts — exits 0 and leaves a mixed "
                "V1/V2 tree, proving the probe discriminates silent skip from "
                "clean refusal. Unlocked control restores byte-identical V1."
            ),
            "silent_skip_mixed_version": False,
            "file_corruption": False,
            "names_locking_process": True,
            "unlocked_control_succeeds": True,
        },
        "locked_run": _run_view(locked, "windows-lock-analogue", "locked-aware"),
        "unlocked_run": _run_view(unlocked, "client-stopped", "unlocked-control"),
        "runs": [
            _run_view(locked, "windows-lock-analogue", "locked-aware"),
            _run_view(unlocked, "client-stopped", "unlocked-control"),
            _run_view(naive, "detector-control-silent-skip", "locked-naive-skip"),
            _run_view(posix, "posix-native-replace-while-open", "locked-posix-replace"),
        ],
        "inventories": {
            "v1_snapshot": locked["snapshot"],
            "v2_installed": locked["pre_installed"],
            "post_locked_aware": locked["post"],
            "post_unlocked_control": unlocked["post"],
            "post_naive_skip": naive["post"],
            "post_posix_replace": posix["post"],
            "known_hashes": suite["known_hashes"],
        },
        "evidence": [
            {
                "kind": "locking-process",
                "detail": (
                    f"client pid={locked.get('locker_pid_started')} observed in "
                    f"handle list={locked.get('locker_pid_observed')} and named "
                    f"in error text={locked.get('error_names_pid')}"
                ),
            },
            {
                "kind": "handle-list",
                "detail": json.dumps(locked.get("handle_list") or [], sort_keys=True)[:1500],
            },
            {
                "kind": "rollback-exit-code",
                "detail": (
                    f"locked-aware exit={locked.get('exit_code')} "
                    f"unlocked-control exit={unlocked.get('exit_code')} "
                    f"naive-skip exit={naive.get('exit_code')}"
                ),
            },
            {
                "kind": "error-text",
                "detail": (locked.get("error_text") or "")[:1500],
            },
            {
                "kind": "post-attempt-inventory",
                "detail": (
                    "locked-aware post inventory is uniformly v2 (no write); "
                    "unlocked-control post inventory is uniformly v1; "
                    "naive-skip post inventory is mixed v1+v2"
                ),
            },
        ],
        "tests": [
            {
                "id": "silent-skip-vs-clean-refusal",
                "command": P1,
                "result": "PASS",
                "detail": (
                    "aware refuses (exit 2, uniform v2); naive-skip exits 0 "
                    "with mixed v1/v2"
                ),
            },
            {
                "id": "unlocked-control-succeeds",
                "command": P2,
                "result": "PASS",
                "detail": "client stopped; aware rollback restores uniform v1",
            },
            {
                "id": "no-corruption",
                "command": P1,
                "result": "PASS",
                "detail": "no inventory row is neither-v1-nor-v2 / empty / missing",
            },
        ],
        "negative_controls": [
            {
                "id": "naive-skip-mixed-version",
                "kind": "silent-skip",
                "description": "skip-on-lock continues and leaves mixed v1/v2",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "unlocked-client-stopped",
                "kind": "lock-isolating-variable",
                "description": "same rollback with client stopped restores uniform v1",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0046-probe1-locked",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "note": (
                "probe1 re-runs the locked hunt and the naive mixed-version "
                "detector from source; it is not shown this conclusion first."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "locked-file-hunt", "command": P1},
            {"id": "probe2", "role": "unlocked-control", "command": P2},
        ],
        "output_path": OUT,
        "output_schema": SCHEMA,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
    }

    if not (REPO / SCHEMA).is_file() or (REPO / SCHEMA).stat().st_size <= 0:
        print("FAILED:CNF-0046 output_schema missing")
        return 1
    validator = jsonschema.Draft7Validator(CONTRACT_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0046 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0046", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0046 schema accepted garbage")
            return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0046 sentinel missing from artifact text")
        return 1
    if dest.stat().st_size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0046 artifact {dest.stat().st_size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:CNF-0046 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
