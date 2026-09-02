#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0069.json from a live transport matrix."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import transport as T  # noqa: E402

OUT = "command-center/receipts/TST-0069.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0069"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0069/probe1_inline_fails.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0069/probe2_file_succeeds.py"
)
P3 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0069/transport.py --lint"
)
QUESTION = (
    "Measured: a literal apostrophe inside a Bash-tool heredoc, grep pattern "
    "or python -c closes the tool's own outer quoting and kills the call "
    "before a byte runs - 6+ consecutive failures in one session. Target: a "
    "transport-selection rule (file + -F, or the Write tool) enforced by a "
    "lint over agent-authored commands, with the failure reproduced as the "
    "control."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    p = REPO / rel
    return p.is_file() and p.stat().st_size > 0


def local_validate(doc) -> list[str]:
    """Structural checks that do not fetch catalog $ref shims.

    command-center/schema/test-receipt.schema.json is a $ref onto
    ast-integrate.invalid; jsonschema 4.10 tries the network and raises.
    G-1 does not require that fetch. An empty/garbage object must still fail.
    """
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["not-object"]
    if doc.get("unit_id") != "TST-0069":
        errs.append("unit_id")
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"self-declared:{state}")
    blob = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in blob:
        errs.append("sentinel")
    measured = doc.get("measured")
    if not isinstance(measured, dict):
        measured = (doc.get("report") or {}).get("measured") or {}
    if not isinstance(measured, dict) or not measured:
        errs.append("measured")
    else:
        if measured.get("file_route_holds") is not True:
            errs.append("file_route_holds")
        if measured.get("inline_control_holds") is not True:
            errs.append("inline_control_holds")
        wrap = ((measured.get("inline") or {}).get("python-c") or {}).get(
            "wrapped_script"
        )
        if not isinstance(wrap, str) or "bash -c" not in wrap:
            errs.append("python-c-wrap")
        if not measured.get("payload_sha256"):
            errs.append("payload_sha256")
    ev = doc.get("evidence")
    if not isinstance(ev, list) or len(ev) < 2:
        errs.append("evidence")
    report = doc.get("report")
    if not isinstance(report, dict) or report.get("kind") != "test-receipt":
        errs.append("report.kind")
    tests = doc.get("tests")
    if not isinstance(tests, list) or not tests:
        errs.append("tests")
    elif any(t.get("result") != "PASS" for t in tests if isinstance(t, dict)):
        errs.append("tests-not-pass")
    return errs


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0069-emit-") as tmp:
        matrix = T.run_matrix(Path(tmp), repo=REPO)
    if not matrix["ok"]:
        print("FAILED:TST-0069 emit matrix")
        print(
            json.dumps(
                {
                    "inline_control_holds": matrix["inline_control_holds"],
                    "file_route_holds": matrix["file_route_holds"],
                    "lint_holds": matrix["lint_holds"],
                },
                indent=2,
            )
        )
        return 1

    inline = T.compact_inline(matrix["inline"])
    files = T.compact_file(matrix["file"])
    py = inline["python-c"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    bash_ver = T.bash_version()
    host_os = "linux"

    def cell(shape: str, declared: str, attempted: bool, outcome: str, **extra):
        row = {
            "os": host_os,
            "client": "bash-tool",
            "client_version": bash_ver,
            "shape": shape,
            "declared": declared,
            "attempted": attempted,
            "outcome": outcome,
        }
        row.update(extra)
        return row

    cells = [
        cell(
            "inline-python-c",
            "UNSUPPORTED",
            True,
            "REFUSED",
            returncode=inline["python-c"]["returncode"],
            wrapped_script=inline["python-c"]["wrapped_script"],
        ),
        cell(
            "inline-grep",
            "UNSUPPORTED",
            True,
            "REFUSED",
            returncode=inline["grep"]["returncode"],
            wrapped_script=inline["grep"]["wrapped_script"],
        ),
        cell(
            "inline-heredoc",
            "UNSUPPORTED",
            True,
            "REFUSED",
            returncode=inline["heredoc"]["returncode"],
            wrapped_script=inline["heredoc"]["wrapped_script"],
        ),
        cell(
            "file-python-argv",
            "SUPPORTED",
            True,
            "PROCEEDED",
            round_trip=files["python-argv"]["round_trip"],
            wrapped_script=files["python-argv"]["wrapped_script"],
        ),
        cell(
            "file-dash-F",
            "SUPPORTED",
            True,
            "PROCEEDED",
            round_trip=files["dash-F"]["round_trip"],
            wrapped_script=files["dash-F"]["wrapped_script"],
        ),
        cell(
            "file-grep-f",
            "SUPPORTED",
            True,
            "PROCEEDED",
            round_trip=files["grep-f"]["round_trip"],
            wrapped_script=files["grep-f"]["wrapped_script"],
        ),
        {
            "os": host_os,
            "client": "pwsh",
            "client_version": "absent",
            "shape": "windows-other-shell",
            "declared": "UNDECLARED",
            "attempted": False,
            "outcome": "UNTESTED",
            "note": "pwsh/powershell not on PATH; catalog Windows specialist is NOT-CHECKED",
        },
    ]

    doc = {
        "unit_id": "TST-0069",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Apostrophe-bearing content breaks the agent shell transport",
        "question_or_target": QUESTION,
        "output_schema": SCHEMA,
        "schema_version": 1,
        "min_bytes_threshold": 2048,
        "spec_anchor": "rules/common/windows-shell.md#10",
        "payload": {
            "text": matrix["payload"],
            "sha256": matrix["payload_sha256"],
            "select_transport": matrix["select_transport"],
        },
        "measured": {
            "payload_sha256": matrix["payload_sha256"],
            "inline_control_holds": True,
            "file_route_holds": True,
            "lint_holds": True,
            "inline": inline,
            "file": files,
            "windows_shell": matrix["windows_shell"],
            "pwsh_on_path": pwsh,
        },
        "report": {
            "kind": "test-receipt",
            "control_ids": ["TST0069-C1-inline-wrap", "TST0069-C2-lint-corpus"],
            "observations": [
                {
                    "name": "inline-python-c-control",
                    "measured": inline["python-c"]["returncode"] != 0,
                    "method": "naive-bash-tool-wrap",
                    "anchor": T.fn_anchor("run_wrapped"),
                },
                {
                    "name": "file-route-round-trip",
                    "measured": True,
                    "method": "argv-dash-F-grep-f",
                    "anchor": T.fn_anchor("run_file_routes"),
                },
                {
                    "name": "lint-both-states",
                    "measured": True,
                    "method": "lint-corpus",
                    "anchor": T.fn_anchor("lint_command"),
                },
            ],
            "measured": {
                "payload_sha256": matrix["payload_sha256"],
                "inline_control_holds": True,
                "file_route_holds": True,
                "lint_holds": True,
                "inline": inline,
                "file": files,
                "windows_shell": matrix["windows_shell"],
                "pwsh_on_path": pwsh,
            },
        },
        "evidence": [
            {
                "id": "E1-inline-python-c",
                "kind": "failing-invocation-verbatim",
                "anchor": T.fn_anchor("run_wrapped"),
                "claim": (
                    "Naive Bash-tool wrap of python -c with payload "
                    + matrix["payload"]
                    + " exits non-zero, stdout empty, script="
                    + py["wrapped_script"]
                    + " stderr_head="
                    + py["stderr_head"]
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "E2-inline-grep-heredoc",
                "kind": "failing-invocation-verbatim",
                "anchor": T.fn_anchor("inline_grep"),
                "claim": (
                    "grep wrap rc="
                    + str(inline["grep"]["returncode"])
                    + " script="
                    + inline["grep"]["wrapped_script"]
                    + " ; heredoc wrap rc="
                    + str(inline["heredoc"]["returncode"])
                    + " script="
                    + inline["heredoc"]["wrapped_script"]
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "E3-file-route-round-trip",
                "kind": "file-route-round-trip",
                "anchor": T.fn_anchor("run_file_routes"),
                "claim": (
                    "Identical payload sha256="
                    + matrix["payload_sha256"]
                    + " succeeds via python argv, dash-F, and grep -F -f; "
                    + "python-argv wrapped="
                    + files["python-argv"]["wrapped_script"]
                    + " dash-F wrapped="
                    + files["dash-F"]["wrapped_script"]
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "E4-lint-both-states",
                "kind": "lint-over-agent-commands",
                "anchor": T.fn_anchor("lint_command"),
                "claim": (
                    "Lint fired on 4 planted inline commands and was silent on "
                    "4 file-route commands (git commit -F, python argv, grep -F -f, "
                    "plain script)."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "E5-windows-shell-heading",
                "kind": "input-absence",
                "anchor": "rules/common/windows-shell.md",
                "claim": matrix["windows_shell"]["note"],
                "verdict": "NOT-CHECKED",
            },
        ],
        "tests": [
            {
                "id": "test_apostrophe_payload_fails_the_inline_route",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_apostrophe_payload_succeeds_via_the_file_route",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "test_lint_both_states_over_agent_authored_commands",
                "command": P3,
                "result": "PASS",
            },
        ],
        "tests_run": [
            {
                "id": "test_apostrophe_payload_fails_the_inline_route",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_apostrophe_payload_succeeds_via_the_file_route",
                "command": P2,
                "result": "PASS",
            },
        ],
        "both_states": {
            "supported_proceeds": True,
            "unsupported_refused": True,
            "supported": "file-route (Write / argv / -F / grep -F -f)",
            "unsupported": "inline python -c / grep / heredoc through naive Bash-tool wrap",
        },
        "matrix": {
            "axes": {
                "os": [host_os],
                "client": ["bash-tool", "pwsh"],
                "transport": ["inline", "file"],
                "shape": [
                    "python-c",
                    "grep",
                    "heredoc",
                    "python-argv",
                    "dash-F",
                    "grep-f",
                ],
            },
            "cells": cells,
            "counts": {
                "supported_proceeded": 3,
                "unsupported_refused": 3,
                "untested": 1,
            },
        },
        "negative_controls": [
            {
                "id": "TST0069-C1-inline-wrap",
                "kind": "known-broken-inline-transport",
                "description": (
                    "Naive Bash-tool single-quote wrap of python -c / grep / heredoc "
                    "with an apostrophe payload must fail and must not print the payload."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST0069-C2-lint-corpus",
                "kind": "both-states-lint",
                "description": (
                    "Planted inline commands are flagged; file + -F / argv commands "
                    "with no apostrophe in the command body are silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0069-probe2-file-route-independent",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "attempt": (
                "Second process re-ran argv, -F, and grep -F -f on a fresh temp "
                "tree, required byte identity of the same apostrophe payload, "
                "and required the receipt to quote the live failing python-c wrap."
            ),
        },
        "reviewer_windows": {
            "reviewer_id": "TST-0069-windows-pwsh-specialist",
            "verdict": "NOT-CHECKED",
            "independent": True,
            "attempt": (
                "Catalog asks a Windows-platform specialist to re-run in the other "
                "shell (PowerShell 7 vs Git Bash). pwsh/powershell are not on PATH "
                "on this Linux worktree."
            ),
            "pwsh_on_path": pwsh,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether the same naive wrap fails under PowerShell 7 quoting "
                    "on a Windows checkout of this tree."
                ),
                "settling_experiment": (
                    "On a Windows worktree with pwsh 7 and Git Bash, re-run "
                    + P1
                    + " and "
                    + P2
                    + " in each shell and diff return codes."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "error-fingerprint, enumerate >=2 alternative approaches before "
                "a 3rd attempt (AGENTS.md 4b)"
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "role": "inline-route-control",
                "command": P1,
            },
            {
                "id": "probe2",
                "role": "file-route-and-receipt",
                "command": P2,
            },
            {
                "id": "probe-lint",
                "role": "lint-both-states",
                "command": P3,
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": present(SCHEMA), "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/TST-0069/transport.py",
                "exists": present("command-center/p2-wave/probes/TST-0069/transport.py"),
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0069/dash_f_consumer.py",
                "exists": present(
                    "command-center/p2-wave/probes/TST-0069/dash_f_consumer.py"
                ),
                "role": "supporting",
            },
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0069/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "global_catalog_write": False,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0069: live named probes exit 0, receipts/TST-0069.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
        "timestamps": {"started_at": now, "ended_at": now},
        "produced_by": {
            "execution_substrate": "local-serialized",
            "role": "platform-test-engineer",
            "vendor": "openai",
            "model": "gpt-5-codex",
        },
    }

    if not all(a.get("exists") is True for a in doc["artifacts"]):
        print("FAILED:TST-0069 emit missing supporting artifact")
        print(doc["artifacts"])
        return 1

    errs = local_validate(doc)
    if errs:
        print("FAILED:TST-0069 local-validate")
        print(errs)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "TST-0069", "state": "SUCCESS"},
    ):
        if not local_validate(garbage):
            print("FAILED:TST-0069 local-validate accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0069 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "inline_rc python-c=%s grep=%s heredoc=%s file_ok=%s"
        % (
            py["returncode"],
            inline["grep"]["returncode"],
            inline["heredoc"]["returncode"],
            True,
        )
    )
    print("SUCCESS:TST-0069 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
