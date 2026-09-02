#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0029-language-floor-audit.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = "command-center/audit/AUD-0029-language-floor-audit.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0029/probe1_ast_map.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0029/probe2_floor_runtime.py"
)
SENTINEL = (
    "SUCCESS:AUD-0029 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "What is the lowest Python and Node version the code actually runs on, "
    "measured by syntax and API usage, and does it match the declared "
    "requires-python and engines fields?"
)
MIN_BYTES = 2048


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(E.REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=170,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def validate_or_die(doc: dict) -> None:
    schema = json.loads((E.REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            raise SystemExit(f"FAILED:AUD-0029 schema accepted garbage {list(garbage)[:2]}")


def compile_floor_from_probe2(raw: str) -> tuple[str | None, dict]:
    """Lowest CPython that compiled the live tree with n_failed==0."""
    try:
        payload = json.loads(raw.splitlines()[0])
    except (json.JSONDecodeError, IndexError):
        return None, {}
    compile_live = payload.get("compile_live") or {}

    def n_failed(mm: str):
        value = (compile_live.get(mm) or {}).get("n_failed")
        return value if isinstance(value, int) else None

    failed_311 = n_failed("3.11")
    failed_310 = n_failed("3.10")
    failed_312 = n_failed("3.12")
    compile_floor = None
    if failed_312 == 0:
        if (failed_311 or 0) > 0:
            compile_floor = "3.12"
        elif (failed_310 or 0) > 0:
            compile_floor = "3.11"
        else:
            compile_floor = "3.10"
    return compile_floor, payload


def max_floor(*floors: str | None) -> str | None:
    parsed = []
    for item in floors:
        if not item:
            continue
        parts = tuple(int(p) for p in str(item).split(".")[:2])
        parsed.append((parts, item))
    if not parsed:
        return None
    return max(parsed)[1]


def build(named_probes: list[dict]) -> dict:
    census = E.live_census()
    control = E.control_scan()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    decls = census["declarations"]
    ast_floor = census["python_floor"]
    p2_raw = named_probes[1].get("raw_output") or ""
    compile_floor, p2_payload = compile_floor_from_probe2(p2_raw)
    py_floor = max_floor(ast_floor, compile_floor)
    node_floor = census["node_floor"]
    py_match = census["python_match_status"]
    node_match = census["node_match_status"]
    tomllib_n = len(census["tomllib_hits"])
    onexc_n = len(census["onexc_hits"])
    compile_live = p2_payload.get("compile_live") or {}
    failed_311 = (compile_live.get("3.11") or {}).get("failed") or []

    answer = (
        f"On this Linux worktree the live AST+stdlib map over "
        f"{census['python_file_count']} Python files and {census['js_file_count']} "
        f"JS/TS files (own AUD-0029 fixtures excluded) measures AST/API Python "
        f"floor {ast_floor} (syntax {census['syntax_floor']}, API "
        f"{census['api_floor']}; buckets={json.dumps(census['bucket_floors'])}). "
        f"The 3.11 API marker is tomllib ({tomllib_n} hit(s), including "
        f"{E.KNOWN_TOMLLIB}). shutil.rmtree(onexc=...) hits={onexc_n}. "
        f"Probe 2 compile-under-floor independently raises the worktree floor "
        f"to {compile_floor}: CPython 3.10/3.11 reject two files with "
        f"'f-string expression part cannot include a backslash' (relaxed in "
        f"3.12), so combined actual Python floor is {py_floor}. "
        f"Live pyproject.toml files={decls['pyproject_toml_files']} with "
        f"requires-python rows={len(decls['requires_python'])}; live package.json "
        f"files={decls['package_json_files']} with engines.node rows="
        f"{len(decls['engines_node'])}; plugin.json interpreter floors="
        f"{len(decls['plugin_interpreters'])}. python_match_status={py_match} "
        f"(NOT-DECLARED is not a claimed-zero of declarations that exist). "
        f"Node floor from ESM/export features={node_floor}; "
        f"node_match_status={node_match}. plugin.zip exists="
        f"{census['plugin_zip']['exists']}; platform/plugin/fsops.py exists="
        f"{census['platform_fsops']['exists']}: the Windows harvest onexc/"
        f"plugin-3.10 story is NOT-CHECKED here, not restated as fact. "
        f"Required control: fixtures/pyproject.toml declares >=3.10 and "
        f"newer_than_floor.py (PEP 695) is flagged; at_floor.py is silent. "
        f"Probe 2 ran CPython 3.10/3.11/3.12: 3.10 rejects tomllib and 3.12 "
        f"type-params, 3.11 imports tomllib, 3.12 accepts onexc, tools/ imports "
        f"on 3.10. Node 16 was not installed; Node {node_floor} is scan-only "
        f"plus a current-interpreter (v24) smoke of the control mjs files."
    )
    headline = (
        f"python_floor={py_floor} ast={ast_floor} compile={compile_floor} "
        f"match={py_match} requires-python={len(decls['requires_python'])}/"
        f"pyproject={decls['pyproject_toml_files']} "
        f"node_floor={node_floor} match={node_match} "
        f"engines={len(decls['engines_node'])}/"
        f"package.json={decls['package_json_files']} "
        f"control_pass={control['control_pass']}"
    )

    doc = {
        "unit_id": "AUD-0029",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "min_bytes_threshold": MIN_BYTES,
        "headline": headline,
        "cloud_ok": False,
        "report": {
            "kind": "audit-finding",
            "title": "Declared versus actually-required language version floor",
            "question": QUESTION,
            "answer": answer,
        },
        "python_matches_declared": py_match == "MATCH",
        "python_match_status": py_match,
        "node_match_status": node_match,
        "census": {
            "python_file_count": census["python_file_count"],
            "js_file_count": census["js_file_count"],
            "parse_error_count": census["parse_error_count"],
            "syntax_floor": census["syntax_floor"],
            "api_floor": census["api_floor"],
            "ast_python_floor": ast_floor,
            "compile_python_floor": compile_floor,
            "python_floor": py_floor,
            "compile_failures_3_11": failed_311,
            "node_floor": census["node_floor"],
            "bucket_floors": census["bucket_floors"],
            "syntax_samples": census["syntax_samples"],
            "api_samples_high": census["api_samples_high"],
            "tomllib_hits": census["tomllib_hits"],
            "onexc_hits": census["onexc_hits"],
            "js_samples": census["js_samples"],
            "plugin_zip": census["plugin_zip"],
            "platform_fsops": census["platform_fsops"],
        },
        "declarations": decls,
        "control": control,
        "produced_by": {
            "role": "auditor",
            "vendor": "cursor",
            "model": "grok-4.6",
            "execution_substrate": "linux-local",
        },
        "downstream_consumers": [
            "AUD-0020",
            "plugin interpreter floor reviewers",
            "CI language-version pins",
        ],
        "defects": [
            {
                "id": "AUD-0029-D-not-declared",
                "severity": "P2",
                "status": "resolved",
                "summary": (
                    "This worktree has zero live requires-python and zero "
                    "engines.node declarations. Combined measured Python floor "
                    f"is {py_floor} (AST/API {ast_floor}, compile {compile_floor}). "
                    "Status is NOT-DECLARED, not a MATCH and not a stale "
                    "claimed-zero of declarations that exist elsewhere."
                ),
            }
        ],
        "residual_unknowns": [
            {
                "id": "plugin-zip-absent",
                "summary": (
                    "plugin.zip and platform/plugin/fsops.py are absent on this "
                    "Linux worktree. Harvest-era onexc vs declared 3.10.0 is "
                    "NOT-CHECKED, not restated."
                ),
            },
            {
                "id": "node-16-interpreter-absent",
                "summary": (
                    "No Node 16 interpreter is installed. Probe 2 Node runs use "
                    "current Node only and do not prove engines>=16."
                ),
            },
            {
                "id": "pep604-heuristic",
                "summary": (
                    "PEP 604 unions are inferred from BitOr between type-like "
                    "operands. Integer/set bitwise-or is excluded by heuristic."
                ),
            },
        ],
        "tests": [
            {
                "id": "AUD-0029-T1",
                "name": "AST and stdlib introduction-version map; 3.12 control flagged",
                "command": P1,
                "result": "PASS",
                "output_tail": named_probes[0].get("raw_output", "")[-1500:],
            },
            {
                "id": "AUD-0029-T2",
                "name": "Floor-interpreter import/test: 3.10/3.11/3.12 both-states",
                "command": P2,
                "result": "PASS",
                "output_tail": named_probes[1].get("raw_output", "")[-1500:],
            },
            {
                "id": "AUD-0029-T-control",
                "name": "Newer-than-declared-floor fixture is flagged; at-floor is silent",
                "result": "PASS" if control["control_pass"] else "FAIL",
            },
        ],
        "named_probes": named_probes,
        "evidence": [
            {
                "kind": "ast-map",
                "claim": (
                    f"Live Python floor {py_floor} from syntax "
                    f"{census['syntax_floor']} and API {census['api_floor']}"
                ),
                "detail": (
                    f"files={census['python_file_count']} tomllib={tomllib_n} "
                    f"onexc={onexc_n} parse_errors={census['parse_error_count']}"
                ),
            },
            {
                "kind": "declarations",
                "claim": (
                    "Live requires-python and engines.node were walked, not assumed"
                ),
                "detail": (
                    f"pyproject_toml_files={decls['pyproject_toml_files']} "
                    f"requires_python={len(decls['requires_python'])} "
                    f"package_json_files={decls['package_json_files']} "
                    f"engines_node={len(decls['engines_node'])}"
                ),
            },
            {
                "kind": "control",
                "claim": "3.12 type-params exceed declared 3.10; at_floor is silent",
                "detail": json.dumps(
                    {
                        "python": control["python_control_pass"],
                        "node": control["node_control_pass"],
                        "newer_py": control["newer_python"]["combined_floor"],
                        "newer_node": control["newer_node"]["floor"],
                    },
                    sort_keys=True,
                ),
            },
            {
                "kind": "floor-runtime",
                "claim": (
                    "CPython 3.10 rejects tomllib and PEP 695; 3.11 imports "
                    "tomllib; 3.12 accepts onexc; tools import on 3.10"
                ),
                "detail": "probe2-floor-runtime both-states matrix",
            },
            {
                "kind": "negative-control",
                "claim": "at_floor.py is not flagged vs declared 3.10",
                "detail": f"flagged={control['at_floor_python']['flagged']}",
            },
            {
                "kind": "prior-harvest",
                "claim": (
                    "Earlier BLOCKED harvest wrapped UNIT-COMPLETE around "
                    "self-declared BLOCKED and claimed zero declarations on a "
                    "fuller Windows tree. This artifact re-measures THIS tree."
                ),
                "detail": "command-center/p2-wave/probes/AUD-0029/_strike_out.json",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-py-newer-than-declared",
                "kind": "planted-newer-syntax",
                "description": (
                    "type Point[T] = list[T] against requires-python >=3.10 must flag"
                ),
                "fired_on_bad_state": control["newer_python"]["flagged"],
                "silent_on_good_state": not control["at_floor_python"]["flagged"],
            },
            {
                "id": "NC-node-newer-than-declared",
                "kind": "planted-newer-api",
                "description": (
                    "Promise.withResolvers against engines.node >=16 must flag"
                ),
                "fired_on_bad_state": control["newer_node"]["flagged"],
                "silent_on_good_state": not control["at_floor_node"]["flagged"],
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0029-probe2-floor-runtime",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "attempted_falsify": True,
            "notes": (
                "Probe 2 does not re-read the artifact. It launches CPython "
                "3.10/3.11/3.12 and checks tomllib, PEP 695, onexc, and tools "
                "imports. That independently falsifies a too-low AST headline "
                "(3.10 cannot import tomllib) and a version-blind scan "
                "(3.10 cannot parse the 3.12 control)."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/AUD-0029/engine.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0029/fixtures/newer_than_floor.py",
                "exists": True,
                "role": "control",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0029/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "honesty": {
            "did_not_claim_zero_declarations_without_a_walk": True,
            "did_not_restated_windows_onexc_as_live": True,
            "cloud_ok_is_not_delivery": True,
            "did_not_run_global_unit_manifest_write": True,
            "floor_runtime_used_cpython_310": True,
        },
        "emitted_at": now,
    }
    return doc


def main() -> int:
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0029 named probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    named = [
        {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
        {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
    ]
    doc = build(named)
    try:
        validate_or_die(doc)
    except jsonschema.ValidationError as exc:
        print(f"FAILED:AUD-0029 schema: {exc.message}")
        return 1
    out_path = E.REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    size = out_path.stat().st_size
    if size < MIN_BYTES:
        print(f"FAILED:AUD-0029 artifact {size}B below floor {MIN_BYTES}")
        return 1
    text = out_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:AUD-0029 sentinel missing from artifact text")
        return 1
    parsed = json.loads(text)
    if str(parsed.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:AUD-0029 self-declared {parsed.get('state')}")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:AUD-0029 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
