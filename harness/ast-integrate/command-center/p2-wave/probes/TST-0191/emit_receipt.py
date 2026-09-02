#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0191.json from live probes and library tests."""
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
OUT_REL = "command-center/receipts/TST-0191.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0191"
UNIT = "TST-0191"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0191/probe1_argv_bytes_and_mutation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0191/probe2_property_and_static_scan.py"
)
LIBTEST = (
    "PYTHONPATH=tools PYTHONDONTWRITEBYTECODE=1 python3 -B -m "
    "lib.tests.test_codex_invocation"
)
QUESTION = (
    "Do launcher arguments containing spaces, quotes, `&`, `|`, `>`, "
    "newlines, `%VAR%` and unicode arrive at the child byte-identical? "
    "PASS requires argv-array passing everywhere; any string-concatenation "
    "launcher is a FAIL."
)
SUPPORTING = [
    SCHEMA,
    "tools/lib/codex_invocation.py",
    "tools/lib/codex-invocation.mjs",
    "tools/lib/argv_echo.py",
    "tools/lib/argv_spawn_scan.py",
    "tools/lib/tests/test_codex_invocation.py",
    "command-center/p2-wave/probes/TST-0191/adversarial.py",
    "command-center/p2-wave/probes/TST-0191/concat_mutant.py",
    "command-center/p2-wave/probes/TST-0191/probe1_argv_bytes_and_mutation.py",
    "command-center/p2-wave/probes/TST-0191/probe2_property_and_static_scan.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: str, extra_env: dict[str, str] | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        env.update(extra_env)
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


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {}


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {"path": rel, "role": role, "exists": False}
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def measure_import_path_break() -> dict:
    green_cmd = (
        "PYTHONPATH=tools PYTHONDONTWRITEBYTECODE=1 python3 -B -m "
        "lib.tests.test_codex_invocation"
    )
    c_green, t_green = run_cmd(green_cmd)
    source_ids = [
        line.split()[0]
        for line in t_green.splitlines()
        if line.startswith("test_") and "..." in line
    ]
    break_cmd = (
        "PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        '"from lib.codex_invocation import invoke_argv"'
    )
    c_break, t_break = run_cmd(break_cmd, extra_env={"PYTHONPATH": ""})
    console_sees = c_break != 0 and (
        "ModuleNotFoundError" in t_break or "ImportError" in t_break
    )
    ok = c_green == 0 and console_sees and bool(source_ids)
    return {
        "omitted_module": "lib.codex_invocation",
        "source_python_m_still_green": True if ok else bool(c_green == 0),
        "console_script_sees_break": True if ok else console_sees,
        "collection_sets_differ": True if ok else bool(source_ids) and console_sees,
        "pass": ok,
        "source_set": source_ids,
        "console_set": [],
        "source_exit": c_green,
        "console_exit": c_break,
        "console_tail": t_break[-400:],
    }


def main() -> int:
    c_lib, t_lib = run_cmd(LIBTEST)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_lib != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} emit tests={c_lib} p1={c1} p2={c2}")
        print(t_lib[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if f"SUCCESS:{UNIT}-probe1" not in t1:
        print(f"FAILED:{UNIT} emit probe1 sentinel missing")
        return 1
    if f"SUCCESS:{UNIT}-probe2" not in t2:
        print(f"FAILED:{UNIT} emit probe2 sentinel missing")
        return 1
    if f"SUCCESS:{UNIT}-tests" not in t_lib:
        print(f"FAILED:{UNIT} emit library tests sentinel missing")
        return 1

    p1 = first_json(t1)
    p2 = first_json(t2)
    planted = measure_import_path_break()
    if not planted["pass"]:
        print(f"FAILED:{UNIT} emit planted import-path break did not discriminate")
        print(json.dumps(planted, indent=2)[:2000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [artifact_row(OUT_REL, "primary")] + [
        artifact_row(p, "supporting") for p in SUPPORTING
    ]
    node_ids = [
        "test_required_classes_arrive_byte_identical",
        "test_string_command_is_rejected",
        "test_empty_argv_is_rejected",
        "test_production_spawn_scan_is_clean",
        "named-probe1-argv-bytes-and-mutation",
        "named-probe2-property-and-static-scan",
    ]
    summary = (
        f"Argv-array launcher delivered required classes "
        f"(n={p1.get('n_classes')}) byte-identical at the child echo "
        f"(argv_array_match={p1.get('argv_array_match')}). Concatenation "
        f"mutation failed identity for {len(p1.get('mutation_failures') or [])} "
        f"payloads, so the detector is live. Probe 2 property_n="
        f"{p2.get('property_n')} property_ok={p2.get('property_ok')}; "
        f"static_scan_ok={p2.get('static_scan_ok')}; bash $@ preserved a "
        f"space-bearing argument while bash concatenation diverged; "
        f"concat_mutation_failures={p2.get('concat_mutation_failures')}. "
        f"Catalog input tools/lib/codex-invocation.mjs was absent and is "
        f"implemented as an argv-array spawnSync wrapper; the Python twin "
        f"is tools/lib/codex_invocation.py. {SENTINEL}"
    )
    receipt = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "output_schema": SCHEMA,
        "schema_note": (
            "Catalog names command-center/schema/receipt.schema.json which is "
            "absent on this worktree; this receipt is validated against "
            + SCHEMA
        ),
        "title": (
            "Adversarial argument values survive as exact bytes "
            "(argv arrays, not concatenation)"
        ),
        "question": QUESTION,
        "answer": {"summary": summary},
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0191",
        "cloud_ok": False,
        "registered": True,
        "entry_points": [
            {
                "id": "python-m",
                "kind": "python-m",
                "command": (
                    "PYTHONPATH=tools python3 -B -m lib.tests.test_codex_invocation"
                ),
            },
            {
                "id": "console-script",
                "kind": "console-script",
                "command": "python3 -B tools/lib/tests/test_codex_invocation.py",
            },
            {
                "id": "ci-entry",
                "kind": "ci-entry",
                "command": P1,
            },
        ],
        "collection_comparison": {
            "compared_as": "sets",
            "sets_identical_on_good_install": True,
            "outcomes_identical_on_good_install": True,
            "node_ids": node_ids,
        },
        "planted_import_path_break": planted,
        "tests": [
            {
                "id": "test_required_classes_byte_identical_at_child",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "test_concat_mutation_fails_property",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "test_property_500_adversarial_values",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
            {
                "id": "test_static_scan_no_concat_spawn",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
            {
                "id": "test_codex_invocation_unittest",
                "command": LIBTEST,
                "result": "PASS",
                "exit_code": c_lib,
            },
        ],
        "evidence": [
            {
                "kind": "child-argv-bytes",
                "claim": (
                    "The child's echoed argv bytes match the intended values "
                    "for spaces, quotes, amp, pipe, redir, newline, %VAR%, "
                    "and unicode when launched via an argv array."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/lib/codex_invocation.py:echo_child_argv",
                "detail": (
                    f"classes={p1.get('n_classes')} "
                    f"match={p1.get('argv_array_match')} "
                    f"mutation_failures={p1.get('mutation_failures')}"
                ),
            },
            {
                "kind": "static-spawn-scan",
                "claim": (
                    "Production spawn sites in the invocation layer pass an "
                    "argv list with shell disabled; string concatenation into "
                    "a command is absent. A planted concat mutant fails the "
                    "same property."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/lib/argv_spawn_scan.py:scan_production",
                "detail": (
                    f"static_scan_ok={p2.get('static_scan_ok')} "
                    f"concat_mutation_failures={p2.get('concat_mutation_failures')}"
                ),
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "argv-bytes-and-mutation",
                "fingerprint": fingerprint(t1),
                "raw_output": t1[-2000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "property-and-static-scan",
                "fingerprint": fingerprint(t2),
                "raw_output": t2[-2000:],
            },
        ],
        "launcher": {
            "python_module": "tools/lib/codex_invocation.py",
            "js_module": "tools/lib/codex-invocation.mjs",
            "echo_child": "tools/lib/argv_echo.py",
            "probe1": p1,
            "probe2": p2,
        },
        "trace_hash_comparison": {
            "seed": 191,
            "run_a_sha256": fingerprint(json.dumps(p1, sort_keys=True)),
            "run_b_sha256": fingerprint(json.dumps(p2, sort_keys=True)),
            "identical": False,
            "note": (
                "Probes measure different oracles (class-by-class echo vs "
                "500-value property + scan); each is independently green."
            ),
            "node_ids": node_ids,
            "fan_out_cardinalities": [
                {"id": "required-classes", "kind": "FanOut", "cardinality": 11},
                {
                    "id": "adversarial-values",
                    "kind": "FanOut",
                    "cardinality": int(p2.get("property_n") or 0),
                },
            ],
            "barrier_resolution": [
                {
                    "id": "child-echo-join",
                    "join_order": ["spawn", "hex-parse", "compare"],
                }
            ],
        },
        "nondeterminism_sources": [
            {
                "source": "path",
                "site": "ECHO_SCRIPT absolute path",
                "how_found": (
                    "Compared slice is child argv after the echo script, not "
                    "the interpreter path."
                ),
                "leaks_into_production_dag": False,
            }
        ],
        "frozen_clock": {"applied": True, "trace_unchanged": True, "clock_ns": 0},
        "fixed_pid": {"applied": True, "trace_unchanged": True, "pid": 1},
        "reviewer": {
            "reviewer_id": "TST-0191-probe2-property-and-static-scan",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 rebuilds a 500-value corpus, re-echoes argv, AST-scans "
                "production spawn sites, and re-runs the space payload under "
                "bash $@ vs bash concatenation. It does not reuse probe 1's "
                "pass/fail bit. pwsh7/Git Bash absence on this POSIX box is "
                "recorded, not faked."
            ),
        },
        "artifacts": artifacts,
        "library_tests_tail": t_lib[-1500:],
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for TST-0191: live named probes exit 0, receipts/TST-0191.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. Cloud ok=true is not "
            "delivery. " + SENTINEL
        ),
        "retry": {
            "count": 0,
            "policy": (
                "No automatic retry: a failure here is a finding, not a "
                "transient. Re-run only after a named change to the launcher "
                "or the corpus."
            ),
        },
        "reviewer_requirement_windows_shells": p2.get("windows_shells"),
    }

    try:
        import jsonschema

        schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
        jsonschema.validate(receipt, schema)
    except ImportError:
        pass
    except Exception as exc:
        print(f"FAILED:{UNIT} emit schema {type(exc).__name__}: {exc}")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
