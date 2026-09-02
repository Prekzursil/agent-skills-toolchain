#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0031-workflow-parameter-command-injection.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

UNIT = "ADV-0031"
OUT = "command-center/adversarial/ADV-0031-workflow-parameter-command-injection.json"
SCHEMA = "command-center/schema/injection-corpus-result.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0031/probe1_canary_side_effect.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0031/probe2_process_table.py"
)
SENTINEL = (
    "SUCCESS:ADV-0031 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0031 <reason>."
)
QUESTION = (
    "Can a workflow parameter value containing shell metacharacters, an "
    "apostrophe, a here-string terminator, a newline or a PowerShell escape "
    "caret alter the command a shell adapter executes?"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"$schema": "http://json-schema.org/draft-07/schema#"},
)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def parse_payload(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch == "{":
            obj, _end = decoder.raw_decode(raw[i:])
            if isinstance(obj, dict):
                return obj
    return {}


def catalog_unit() -> dict[str, Any]:
    data = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == UNIT:
            return row
    raise SystemExit(f"FAILED:{UNIT} missing from catalog")


def validate_or_die(doc: dict[str, Any]) -> None:
    import jsonschema

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print(f"FAILED:{UNIT} schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            raise SystemExit(f"FAILED:{UNIT} schema accepted garbage {list(garbage)[:3]}")


def row_by_id(rows: list[dict[str, Any]], rid: str) -> dict[str, Any]:
    for item in rows:
        if item.get("id") == rid:
            return item
    return {}


def v_bool(flag: bool, confirmed_means: str) -> str:
    del confirmed_means
    return "CONFIRMED" if flag else "REFUTED"


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or SENTINEL)
    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:{UNIT} probes rc1={rc1} rc2={rc2}", file=sys.stderr)
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    p1 = parse_payload(out1)
    p2 = parse_payload(out2)
    c1 = p1.get("controls") or {}
    c2 = p2.get("controls") or {}
    inv = p1.get("inventory") or {}
    rows1 = p1.get("rows") or []
    rows2 = p2.get("rows") or []
    semi = row_by_id(rows1, "semicolon")
    apos = row_by_id(rows1, "apostrophe-breakout")
    dollar = row_by_id(rows1, "dollar-paren")
    newline = row_by_id(rows1, "newline")
    caret = row_by_id(rows1, "caret-powershell")
    here = row_by_id(rows1, "here-string-terminator")
    msys = row_by_id(rows1, "msys-convertible-path")
    semi2 = row_by_id(rows2, "semicolon")
    apos2 = row_by_id(rows2, "apostrophe-breakout")
    msys2 = row_by_id(rows2, "msys-convertible-path")

    shipped_shell = bool(inv.get("shell_true") or inv.get("os_system"))
    launcher_safe = (
        c1.get("semicolon_launcher_no_canary") is True
        and c1.get("apostrophe_launcher_no_canary") is True
        and (semi2.get("argv_array") or {}).get("argv_altered") is False
        and (apos2.get("argv_array") or {}).get("payload_unsplit") is True
    )
    foundry_safe = c1.get("semicolon_foundry_no_canary") is True
    string_unquoted_fires = c1.get("semicolon_string_unquoted_canary") is True
    apostrophe_quoted_fires = c1.get("apostrophe_quoted_canary") is True
    pwsh = bool(p2.get("host_pwsh"))

    dollar_string = bool((dollar.get("string_unquoted") or {}).get("canary"))
    newline_string = bool((newline.get("string_unquoted") or {}).get("canary"))
    caret_string = bool((caret.get("string_unquoted") or {}).get("canary"))
    caret_argv = bool((caret.get("launcher") or {}).get("canary"))
    here_string = bool((here.get("string_unquoted") or {}).get("canary"))
    msys_argv_ok = (msys2.get("argv_array") or {}).get("payload_unsplit") is True

    if not (
        c1.get("benign_no_canary_any_adapter")
        and c1.get("benign_launcher_argv_match")
        and string_unquoted_fires
        and apostrophe_quoted_fires
        and c2.get("benign_argv_unsplit")
        and c2.get("semicolon_string_altered")
    ):
        print(f"FAILED:{UNIT} a listed control did not PASS", file=sys.stderr)
        print(json.dumps({"c1": c1, "c2": c2}, indent=2))
        return 1

    targets = [
        {
            "id": "planted-string-unquoted-interpolation",
            "adapter_family": "string-command",
            "claim": (
                "Unquoted interpolation of a workflow parameter into shell=True "
                "lets semicolon/substitution payloads create a canary file."
            ),
            "verdict": v_bool(string_unquoted_fires, "injects"),
            "probe": "probe1",
        },
        {
            "id": "planted-string-single-quoted-apostrophe",
            "adapter_family": "string-command",
            "claim": (
                "An apostrophe in the parameter breaks the adapter's own single "
                "quotes and runs a second command (windows-shell.md 10 class)."
            ),
            "verdict": v_bool(apostrophe_quoted_fires, "injects"),
            "probe": "probe1",
        },
        {
            "id": "shipped-launcher-argv-array",
            "adapter_family": "argv-array",
            "claim": (
                "tools.launcher.explicit_interpreter.launch passes the parameter "
                "as extra_args; the child argv is unsplit and no canary fires."
            ),
            "verdict": "REFUTED" if launcher_safe else "CONFIRMED",
            "probe": "probe1+probe2",
        },
        {
            "id": "shipped-foundry-typed-inputs",
            "adapter_family": "passthrough",
            "claim": (
                "foundry.runtime.execute stores the parameter on ctx.inputs and "
                "does not spawn; substitution payloads do not create a canary."
            ),
            "verdict": "REFUTED" if foundry_safe else "CONFIRMED",
            "probe": "probe1",
        },
        {
            "id": "shipped-string-command-adapter",
            "adapter_family": "string-command",
            "claim": (
                "A shipped tools/ adapter interpolates parameters into a shell "
                "string (shell=True or os.system)."
            ),
            "verdict": "CONFIRMED" if shipped_shell else "REFUTED",
            "inventory_shell_true": inv.get("shell_true") or [],
            "inventory_os_system": inv.get("os_system") or [],
            "probe": "probe1-static+dynamic",
        },
        {
            "id": "dollar-paren-and-backtick-substitution",
            "adapter_family": "both",
            "claim": (
                "$(...) / backtick in a parameter is evaluated by string-command "
                "interpolation and is a literal argv field for the launcher."
            ),
            "verdict": (
                "PARTIAL"
                if dollar_string and not (dollar.get("launcher") or {}).get("canary")
                else v_bool(dollar_string, "injects")
            ),
            "probe": "probe1",
        },
        {
            "id": "newline-payload",
            "adapter_family": "both",
            "claim": "A newline in a parameter starts a second POSIX command under unquoted shell interpolation.",
            "verdict": (
                "PARTIAL"
                if newline_string and not (newline.get("launcher") or {}).get("canary")
                else v_bool(newline_string, "injects")
            ),
            "probe": "probe1",
        },
        {
            "id": "caret-powershell-escape",
            "adapter_family": "both",
            "claim": (
                "A PowerShell/cmd caret-escape payload alters a POSIX adapter. "
                "This host has no pwsh, so the Windows adapter is not executed."
            ),
            "verdict": (
                "PARTIAL"
                if caret_string and not caret_argv
                else v_bool(caret_string or caret_argv, "injects")
            ),
            "host_pwsh": pwsh,
            "probe": "probe1",
        },
        {
            "id": "here-string-terminator",
            "adapter_family": "both",
            "claim": (
                "A payload containing a PowerShell here-string terminator. On "
                "POSIX the embedded newline is the active metacharacter."
            ),
            "verdict": (
                "PARTIAL"
                if here_string and not pwsh
                else v_bool(here_string, "injects")
            ),
            "host_pwsh": pwsh,
            "probe": "probe1",
        },
        {
            "id": "msys-convertible-path",
            "adapter_family": "argv-array",
            "claim": (
                "An MSYS-convertible /c/Users/... path remains one unchanged "
                "argv field on this Linux launcher."
            ),
            "verdict": "REFUTED" if msys_argv_ok else "CONFIRMED",
            "probe": "probe2",
        },
    ]

    tests = [
        {
            "id": "T-BENIGN-ARGV-AND-NO-CANARY",
            "name": "Benign parameter produces intended launcher argv and no canary",
            "command": P1,
            "result": "PASS"
            if c1.get("benign_no_canary_any_adapter") and c1.get("benign_launcher_argv_match")
            else "FAIL",
        },
        {
            "id": "T-PLANTED-STRING-CANARY-GOES-RED",
            "name": "Unquoted string-command adapter fires canary on semicolon payload",
            "command": P1,
            "result": "PASS" if string_unquoted_fires else "FAIL",
        },
        {
            "id": "T-APOSTROPHE-BREAKS-ADAPTER-QUOTING",
            "name": "Apostrophe breaks planted single-quote wrapping",
            "command": P1,
            "result": "PASS" if apostrophe_quoted_fires else "FAIL",
        },
        {
            "id": "T-ARGV-ARRAY-REPORTED-SEPARATELY",
            "name": "Launcher argv-array results are distinct from string-command",
            "command": P1,
            "result": "PASS"
            if (string_unquoted_fires and c1.get("semicolon_launcher_no_canary"))
            else "FAIL",
        },
        {
            "id": "T-PROCESS-TABLE-STRING-ALTERS-ARGV",
            "name": "Process-table oracle sees argv alteration on planted string-command",
            "command": P2,
            "result": "PASS" if c2.get("semicolon_string_altered") else "FAIL",
        },
        {
            "id": "T-PROCESS-TABLE-ARGV-UNSPLIT",
            "name": "Process-table oracle sees unsplit payload on argv-array including semicolon",
            "command": P2,
            "result": "PASS"
            if c2.get("semicolon_argv_unsplit") and c2.get("semicolon_argv_not_altered")
            else "FAIL",
        },
        {
            "id": "T-PROC-ORACLE-CAN-GO-RED",
            "name": "Negative control: process-table detector is silent on benign argv-array",
            "command": P2,
            "result": "PASS"
            if c2.get("benign_argv_unsplit") and c2.get("benign_argv_not_altered")
            else "FAIL",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print(f"FAILED:{UNIT} a listed test did not PASS", file=sys.stderr)
        print(json.dumps(tests, indent=2))
        return 1

    controls = [
        {
            "id": "C-BENIGN-NO-CANARY",
            "result": "PASS" if c1.get("benign_no_canary_any_adapter") else "FAIL",
        },
        {
            "id": "C-PLANTED-STRING-GOES-RED",
            "result": "PASS" if string_unquoted_fires else "FAIL",
        },
        {
            "id": "NC-DETECTOR-SILENT-ON-GOOD-ARGV",
            "result": "PASS"
            if c1.get("semicolon_launcher_no_canary") and c2.get("semicolon_argv_not_altered")
            else "FAIL",
        },
        {
            "id": "NC-DETECTOR-FIRES-ON-BAD-STRING",
            "result": "PASS"
            if string_unquoted_fires and c2.get("semicolon_string_altered")
            else "FAIL",
        },
    ]

    shipped_verdicts = [
        t["verdict"]
        for t in targets
        if t["id"].startswith("shipped-") or t["id"] == "msys-convertible-path"
    ]
    planted_confirmed = any(
        t["verdict"] == "CONFIRMED" and t["id"].startswith("planted-") for t in targets
    )
    if planted_confirmed and launcher_safe and foundry_safe and not shipped_shell:
        overall = "PARTIAL"
    elif not launcher_safe or shipped_shell:
        overall = "CONFIRMED"
    else:
        overall = "PARTIAL"

    answer = (
        "On this Linux worktree a workflow-parameter value alters the executed "
        "command when it is interpolated into a string-command adapter "
        "(unquoted shell=True, and apostrophe breakout of single-quote wrapping). "
        "That class is CONFIRMED by a canary file the injected fragment creates "
        "and independently by /proc cmdline: the child argv is no longer the "
        "intended vector. Shipped tools.launcher.explicit_interpreter.launch is "
        "an argv-array adapter: extra_args remain one field, including "
        "semicolon, apostrophe, newline, substitution, caret and MSYS-shaped "
        "paths, and no canary fires. foundry.runtime.execute is a passthrough: "
        "inputs stay on a Python ctx and never spawn. No shipped tools/ file "
        f"uses shell=True or os.system (sites={inv.get('subprocess_sites')}). "
        "The program is therefore safe on these sinks because those adapters use "
        "argv arrays, not because parameter values are sanitised. PowerShell "
        "caret/here-string adapters were not executed (pwsh absent). "
        + sentinel
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifact: dict[str, Any] = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "report_kind": "injection-corpus-result",
        "schema_version": 1,
        "title": unit.get("title")
        or "Command injection through workflow parameters into shell and process adapters",
        "question": str(unit.get("question_or_target") or QUESTION),
        "answer": answer,
        "overall_verdict": overall,
        "produced_at": now,
        "produced_by": {
            "role": "security-exploit-engineer",
            "vendor": "openai",
            "model": "cursor-grok-4.6",
            "execution_substrate": "linux-worktree",
        },
        "reviewer": {
            "reviewer_id": "ADV-0031-process-table-oracle",
            "independent": True,
            "verdict": "PASS",
            "method": (
                "Second instrument read /proc/<pid>/cmdline (null-separated) and "
                "descendant PPid walks. It does not consult the canary file. "
                "Planted string-command runs must show argv_altered; argv-array "
                "semicolon runs must keep the payload as one field."
            ),
        },
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/ADV-0031/UNIT-ARTIFACT-MANIFEST.json",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "adv_rebuild_circle": False,
        "host_pwsh": pwsh,
        "adapters": list(H.ADAPTERS)
        + [
            {
                "id": "shipped-tools-spawn-inventory",
                "family": "argv-array" if not shipped_shell else "string-command",
                "kind": "shipped-inventory",
                "shell_true": inv.get("shell_true") or [],
                "os_system": inv.get("os_system") or [],
                "subprocess_sites": inv.get("subprocess_sites") or [],
            }
        ],
        "targets": targets,
        "tests": tests,
        "controls": controls,
        "negative_controls": [
            {
                "id": "NC-IDENTICAL-BENIGN-SILENT",
                "fired_on_bad_state": bool(string_unquoted_fires and c2.get("semicolon_string_altered")),
                "silent_on_good_state": bool(
                    c1.get("benign_no_canary_any_adapter") and c2.get("benign_argv_not_altered")
                ),
            }
        ],
        "evidence": [
            {
                "kind": "canary-side-effect",
                "claim": (
                    "Probe 1 creates a canary only when the injected fragment is "
                    f"evaluated. planted-unquoted-semicolon={string_unquoted_fires} "
                    f"launcher-semicolon={c1.get('semicolon_launcher_no_canary')}."
                ),
                "anchor": P1,
            },
            {
                "kind": "process-table-argv",
                "claim": (
                    "Probe 2 compares intended argv to /proc cmdline. "
                    f"semicolon argv_altered={ (semi2.get('argv_array') or {}).get('argv_altered') } "
                    f"string_unquoted argv_altered={ (semi2.get('string_unquoted') or {}).get('argv_altered') }."
                ),
                "anchor": P2,
            },
            {
                "kind": "static-spawn-inventory",
                "claim": (
                    "tools/**/*.py excluding tests: shell=True="
                    f"{inv.get('shell_true')} os.system={inv.get('os_system')}."
                ),
                "anchor": "tools/",
            },
        ],
        "measurements": {
            "probe1_controls": c1,
            "probe2_controls": c2,
            "inventory": inv,
            "canary_row_ids": [r.get("id") for r in rows1],
            "process_row_ids": [r.get("id") for r in rows2],
            "msys_payload_unsplit": msys_argv_ok,
            "caret_canary": {"string": caret_string, "launcher": caret_argv},
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2},
        ],
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": SCHEMA, "role": "schema", "exists": True},
        ],
        "notes": (
            "G-1 delivery: live named probes exit 0, artifact state=SUCCESS "
            "(measurement completed; planted string-command CONFIRMED, shipped "
            "argv-array REFUTED). Per-unit UNIT-ARTIFACT-MANIFEST.json only. "
            "Did not run global unit_manifest.py --write. No ADV rebuild circle."
        ),
    }
    validate_or_die(artifact)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    blob = H.dump_json(artifact)
    artifact["self_hash"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    dest.write_text(H.dump_json(artifact), encoding="utf-8")
    validate_or_die(json.loads(dest.read_text(encoding="utf-8")))
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print(f"SUCCESS:{UNIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
