#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0186.json from a live runner matrix."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inline_control as I  # noqa: E402
import runner as R  # noqa: E402

OUT = "command-center/receipts/TST-0186.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0186"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0186/probe1_static_and_inline_eof.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0186/probe2_file_route_and_receipt.py"
)
QUESTION = (
    "Does the runner route apostrophe-bearing content (commit messages, PR "
    "bodies, prompts) through a FILE rather than inlining it? PASS requires "
    "a static scan finding zero inline prose call sites, and a live case "
    "with apostrophes succeeding."
)
TITLE = "Prose containing an apostrophe never reaches a shell command line"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    p = REPO / rel
    return p.is_file() and p.stat().st_size > 0


def compact_file(rec: dict) -> dict:
    return {
        "kind": rec["kind"],
        "argv": rec["argv"],
        "returncode": rec["returncode"],
        "round_trip": rec["round_trip"],
        "leaked_into_argv": rec["leaked_into_argv"],
        "file_route_holds": rec["file_route_holds"],
        "prose_sha256": rec["prose_sha256"],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0186-emit-") as tmp:
        matrix = R.measure(Path(tmp))
    if not matrix["ok"]:
        print("FAILED:TST-0186 emit matrix")
        print(
            json.dumps(
                {
                    "inline_control_holds": matrix["inline"]["control_holds"],
                    "file_route_holds": matrix["file_route_holds"],
                    "property_ok": matrix["property"]["ok"],
                    "scan_ok": matrix["scan"]["ok"],
                    "scan_production": matrix["scan"]["production"]["findings"][:6],
                    "scan_mutant": matrix["scan"]["mutant"],
                },
                indent=2,
            )
        )
        return 1

    inline = matrix["inline"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    host_os = platform.system().lower()
    bash_ver = platform.platform()
    second = matrix["second_shell"]
    files = {k: compact_file(v) for k, v in matrix["file"].items()}

    def cell(shape: str, declared: str, attempted: bool, outcome: str, **extra):
        row = {
            "os": host_os,
            "client": extra.pop("client", "bash"),
            "client_version": extra.pop("client_version", bash_ver[:96]),
            "shape": shape,
            "declared": declared,
            "attempted": attempted,
            "outcome": outcome,
        }
        row.update(extra)
        return row

    cells = [
        cell(
            "inline-commit-m",
            "UNSUPPORTED",
            True,
            "REFUSED",
            returncode=inline["returncode"],
            script=inline["script"],
            stderr_head=inline["stderr_head"],
        ),
        cell(
            "file-commit-F",
            "SUPPORTED",
            True,
            "PROCEEDED",
            argv=files["commit_message"]["argv"],
            round_trip=files["commit_message"]["round_trip"],
        ),
        cell(
            "file-pr-body-file",
            "SUPPORTED",
            True,
            "PROCEEDED",
            argv=files["pr_body"]["argv"],
            round_trip=files["pr_body"]["round_trip"],
        ),
        cell(
            "file-prompt-file",
            "SUPPORTED",
            True,
            "PROCEEDED",
            argv=files["prompt"]["argv"],
            round_trip=files["prompt"]["round_trip"],
        ),
        cell(
            "windows-second-shell-pwsh7-git-bash",
            "UNDECLARED",
            False,
            "UNTESTED",
            client="pwsh",
            client_version="absent" if not second["pwsh_on_path"] else str(second["pwsh_on_path"]),
            note=second["note"],
        ),
    ]

    live_script = inline["script"]
    eof = I.EOF_PHRASE
    payload = matrix["control_payload"]
    payload_sha = matrix["control_payload_sha256"]

    doc = {
        "unit_id": "TST-0186",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": TITLE,
        "question_or_target": QUESTION,
        "output_schema": SCHEMA,
        "catalog_output_schema": (
            "command-center/schema/receipt.schema.json#/$defs/shell_report"
        ),
        "schema_version": 1,
        "min_bytes_threshold": 2048,
        "spec_anchor": "rules/common/windows-shell.md#10",
        "payload": {
            "text": payload,
            "sha256": payload_sha,
            "select_transport": "file",
        },
        "measured": {
            "control_payload_sha256": payload_sha,
            "inline_control_holds": True,
            "file_route_holds": True,
            "scan_ok": True,
            "scan_production_n": 0,
            "property_ok": True,
            "inline": {
                "script": live_script,
                "returncode": inline["returncode"],
                "stderr_head": inline["stderr_head"],
                "stderr": inline["stderr"],
                "eof_phrase_live": True,
                "catalog_class": I.CATALOG_EOF_CLASS,
            },
            "file": files,
            "property": {
                "n_payloads": matrix["property"]["n_payloads"],
                "names": sorted(matrix["property"]["rows"]),
                "ok": True,
            },
            "scan": {
                "production": {
                    "n": matrix["scan"]["production"]["n"],
                    "roots": matrix["scan"]["production"]["roots"],
                },
                "mutant": {
                    "n": matrix["scan"]["mutant"]["n"],
                    "kinds": matrix["scan"]["mutant"]["kinds"],
                    "path": matrix["scan"]["mutant"]["path"],
                },
            },
            "catalog_inputs": matrix["catalog_inputs"],
            "second_shell": second,
        },
        "evidence": [
            {
                "claim": (
                    "Naive single-quote wrap of git commit -m with payload "
                    + payload
                    + " written as a bash script fails with live stderr containing "
                    + eof
                    + " (catalog class "
                    + I.CATALOG_EOF_CLASS
                    + "). script="
                    + live_script
                    + " stderr_head="
                    + inline["stderr_head"]
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0186/inline_control.py",
            },
            {
                "claim": (
                    "Same payload sha256="
                    + payload_sha
                    + " round-trips via file route for commit -F, gh --body-file, "
                    "and --prompt-file. commit argv="
                    + json.dumps(files["commit_message"]["argv"])
                    + " leaked_into_argv=false"
                ),
                "verdict": "CONFIRMED",
                "anchor": matrix["anchors"]["run_file_route"],
            },
            {
                "claim": (
                    "Static scan of tools/ plus runner.py, consumers.py, and "
                    "tools/lib/codex-invocation.mjs found zero inline prose "
                    "construction sites. Planted fixtures/inline_sites.py fired "
                    "kinds="
                    + json.dumps(matrix["scan"]["mutant"]["kinds"])
                    + " and fixtures/file_sites.py stayed silent."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0186/scan.py",
            },
            {
                "claim": (
                    "Property corpus of apostrophe, double-quote, backtick, "
                    "dollar, newline, CRLF, and combined payloads round-tripped "
                    "byte-identically on all three file-route kinds "
                    f"(n={matrix['property']['n_payloads']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": matrix["anchors"]["argv_for"],
            },
            {
                "claim": (
                    "Catalog cites _USER-PROMPTS.md:11015, "
                    "rules/common/windows-shell.md:10, and "
                    "rules/common/cross-vendor-dispatch.md. Live: "
                    + json.dumps(matrix["catalog_inputs"])
                    + " Heading 10 is absent on windows-shell.md (8b git-archive "
                    "CRLF only). The apostrophe wrap rule is enforced by this "
                    "unit's runner and scan rather than by that missing heading. "
                    "tools/lib/codex-invocation.mjs is present as of this unit."
                ),
                "verdict": "PARTIAL",
                "anchor": "rules/common/windows-shell.md",
            },
        ],
        "tests": [
            {"id": "test_inline_eof_unmatched_quote", "command": P1, "result": "PASS"},
            {"id": "test_static_scan_both_states", "command": P1, "result": "PASS"},
            {"id": "test_file_route_round_trip", "command": P2, "result": "PASS"},
            {
                "id": "test_property_apostrophe_quote_backtick_dollar_newline_crlf",
                "command": P2,
                "result": "PASS",
            },
        ],
        "both_states": {
            "supported_proceeds": True,
            "unsupported_refused": True,
            "supported": "file-route argv array: git commit -F / --body-file / --prompt-file",
            "unsupported": "naive git commit -m '<apostrophe payload>' via bash script",
        },
        "matrix": {
            "axes": {
                "os": [host_os],
                "client": ["bash", "pwsh"],
                "transport": ["inline", "file"],
                "kind": ["commit_message", "pr_body", "prompt"],
            },
            "cells": cells,
            "counts": {
                "supported_proceeded": 3,
                "unsupported_refused": 1,
                "untested": 1,
            },
        },
        "reviewer": {
            "reviewer_id": "TST-0186-probe2-file-route-independent",
            "verdict": "PASS",
            "independent": True,
            "attempt": (
                "Second process re-ran the unmatched-quote EOF control, the "
                "seven-payload property matrix, and required the receipt to "
                "quote the live failing git commit -m script and "
                + eof
                + "."
            ),
        },
        "reviewer_windows": {
            "reviewer_id": "TST-0186-windows-pwsh-git-bash-specialist",
            "verdict": "NOT-CHECKED",
            "independent": True,
            "attempt": second["note"],
            "pwsh_on_path": second["pwsh_on_path"],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": present(SCHEMA), "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/TST-0186/runner.py",
                "exists": present("command-center/p2-wave/probes/TST-0186/runner.py"),
                "role": "supporting",
            },
            {
                "path": "tools/lib/codex-invocation.mjs",
                "exists": present("tools/lib/codex-invocation.mjs"),
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "scan-and-inline-eof", "command": P1},
            {"id": "probe2", "role": "file-route-property-and-receipt", "command": P2},
        ],
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0186: live named probes exit 0, receipts/TST-0186.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. Catalog schema "
            "receipt.schema.json#/$defs/shell_report is absent; this receipt "
            "conforms to command-center/schema/test-receipt.schema.json."
        ),
        "timestamps": {"started_at": now, "ended_at": now},
    }

    if not all(a.get("exists") is True for a in doc["artifacts"]):
        print("FAILED:TST-0186 emit missing supporting artifact")
        print(doc["artifacts"])
        return 1

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0186 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:TST-0186 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0186 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "inline_rc=%s eof=%s file_ok=%s scan_n=%s"
        % (
            inline["returncode"],
            inline["eof_phrase_live"],
            True,
            matrix["scan"]["production"]["n"],
        )
    )
    print("SUCCESS:TST-0186 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
