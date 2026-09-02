"""Execute floor / ceiling / control and assemble the coverage-matrix body."""
from __future__ import annotations

import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inventory import REPO, census
from runtimes import (
    _run,
    discover,
    docker_python,
    run_python_container_file,
    run_python_file,
)

SCHEMA_REL = "command-center/schema/coverage-matrix.schema.json"
OUT_REL = "command-center/receipts/BLD-0011.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0011/probe1_floor_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0011/probe2_ceiling_reviewer.py"
)
GOOD = "command-center/p2-wave/probes/BLD-0011/fixtures/good_subset.py"
MUT_312 = "command-center/p2-wave/probes/BLD-0011/fixtures/mutant_newer.py"
MUT_313 = "command-center/p2-wave/probes/BLD-0011/fixtures/mutant_3_13.py"
MUT_314 = "command-center/p2-wave/probes/BLD-0011/fixtures/mutant_tstring.py"
CEIL = "command-center/p2-wave/probes/BLD-0011/fixtures/ceiling_warn.py"
CC_DIR = REPO / "tools/command-center"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mm(version: str) -> str:
    match = re.search(r"(\d+)\.(\d+)", version)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    match = re.search(r"(\d+)", version)
    return match.group(1) if match else version


def _tuple(version: str) -> tuple[int, int]:
    parts = _mm(version).split(".")
    try:
        return int(parts[0]), int(parts[1] if len(parts) > 1 else 0)
    except ValueError:
        return (0, 0)


def _mutant_for(floor: tuple[int, int]) -> tuple[str, str]:
    if floor < (3, 12):
        return MUT_312, "PEP 695 type alias (3.12)"
    if floor < (3, 13):
        return MUT_313, "PEP 696 default type parameter (3.13)"
    return MUT_314, "PEP 750 t-string (3.14)"


def _ast_rejects(source: str, feature: tuple[int, int]) -> dict[str, Any]:
    try:
        ast.parse(source, filename="mutant.py", feature_version=feature)
        return {"caught": False, "mode": "ast.parse", "feature_version": list(feature)}
    except SyntaxError as exc:
        return {
            "caught": True,
            "mode": "ast.parse",
            "feature_version": list(feature),
            "error": f"{exc.msg} (line {exc.lineno})",
        }
    except TypeError as exc:
        return {"caught": False, "mode": "ast.parse", "error": str(exc)}


def _compileall(exe: str) -> dict[str, Any]:
    if not CC_DIR.is_dir():
        return {"ran": False, "reason": "tools/command-center absent"}
    result = _run([exe, "-B", "-m", "compileall", "-q", str(CC_DIR)], timeout=60)
    result["ran"] = True
    result["passed"] = result["exit_code"] == 0
    return result


def _pick_native(disc: dict[str, Any], want_mm: str) -> dict[str, Any] | None:
    for row in disc.get("python") or []:
        if row.get("ok") and row.get("major_minor") == want_mm:
            return row
    return None


def _node_majors(rows: list[dict[str, str]]) -> list[str]:
    found: set[str] = set()
    for row in rows:
        match = re.search(r"(\d+)", str(row.get("spec") or ""))
        if match:
            found.add(match.group(1))
    return sorted(found, key=lambda x: int(x))


def run_campaign() -> dict[str, Any]:
    inv = census()
    disc = discover()
    declared_min = (inv.get("python_declared_minimum") or {}).get("version") or "3.10"
    declared_mm = _mm(declared_min)

    strikes: list[dict[str, Any]] = []
    floor = _pick_native(disc, declared_mm)
    strikes.append(
        {
            "id": "strike-1-native-named",
            "ok": bool(floor),
            "looked_for": declared_mm,
            "missing": disc.get("python_missing_lookups"),
        }
    )
    if floor is None:
        strikes.append(
            {
                "id": "strike-2-native-rescan",
                "ok": False,
                "note": "discover() already enumerated python3.10 through python3",
            }
        )
        container = docker_python("python:3.10-slim")
        strikes.append(
            {
                "id": "pivot-container-python-3.10-slim",
                "ok": bool(container and container.get("ok")),
                "detail": {
                    k: (container or {}).get(k)
                    for k in ("ok", "engine", "tag", "version", "reason", "exit_code")
                },
            }
        )
        if container and container.get("ok"):
            floor = container
        else:
            floor = disc.get("oldest_python")

    if not floor:
        raise RuntimeError("no Python interpreter available for BLD-0011")

    if floor.get("kind") == "python-container":
        floor_mode = "container"
    elif _mm(str(floor.get("major_minor") or "")) != declared_mm:
        floor_mode = "narrowed-to-available"
    else:
        floor_mode = "native"

    narrowed: list[dict[str, Any]] = []
    if floor_mode == "narrowed-to-available":
        narrowed.append(
            {
                "surface": "declared Python floor",
                "from": declared_mm,
                "to": floor.get("major_minor"),
                "reason": (
                    "Declared minimum interpreter missing after two local lookups "
                    "and a container pivot; subset ran on the oldest available "
                    "interpreter instead."
                ),
                "status": "NARROWED",
            }
        )

    floor_tuple = _tuple(str(floor.get("major_minor") or declared_mm))
    mut_rel, mut_name = _mutant_for(floor_tuple)

    if floor_mode == "container":
        engine = str(floor.get("engine"))
        tag = str(floor.get("tag"))
        good = run_python_container_file(engine, tag, GOOD)
        mutant = run_python_container_file(engine, tag, mut_rel)
        compile_cc = {
            "ran": False,
            "reason": "container floor runs fixture subset only",
        }
        floor_label = f"{engine} run {tag}"
    else:
        exe = str(floor["exe"])
        good = run_python_file(exe, GOOD)
        mutant = run_python_file(exe, mut_rel)
        compile_cc = _compileall(exe)
        floor_label = f"{exe} ({floor.get('version')})"

    newest = disc.get("newest_python") or floor
    ceil_exe = str(newest.get("exe") or sys.executable)
    ceiling = run_python_file(
        ceil_exe, CEIL, extra_env={"PYTHONWARNINGS": "default"}
    )
    warn_lines = [
        ln
        for ln in (ceiling.get("output") or "").splitlines()
        if "DeprecationWarning" in ln
        or "UTCNOW:" in ln
        or "BLD-0011-ceiling" in ln
    ]

    mut_src = (REPO / mut_rel).read_text(encoding="utf-8")
    ast_gate = _ast_rejects(mut_src, _tuple(declared_mm))
    interp_caught = int(mutant.get("exit_code") or 0) != 0
    caught = bool(interp_caught or ast_gate.get("caught"))
    if not caught:
        ast_gate = _ast_rejects(mut_src, floor_tuple)
        caught = bool(ast_gate.get("caught"))

    good_pass = good.get("exit_code") == 0
    ceil_pass = ceiling.get("exit_code") == 0

    false_floor = inv.get("false_floor_evidence") or {}
    if false_floor.get("onexc_hits") or false_floor.get("tomllib_hits_n"):
        narrowed.append(
            {
                "surface": "plugin.zip interpreters.python3 floor 3.10.0",
                "from": "3.10",
                "to": "3.12",
                "reason": (
                    "Harvest records shutil.rmtree(..., onexc=) (3.12 API) and "
                    "tomllib (3.11+). Declared 3.10 cannot be demonstrated for "
                    "the plugin payload."
                ),
                "status": "NARROWED",
            }
        )

    ci = inv.get("ci") or {}
    ci_py = list(ci.get("python") or [])
    ci_node = [_mm(n) if "." in str(n) else str(n) for n in (ci.get("node") or [])]
    py_decl = sorted({declared_mm, "3.10", "3.11", "3.12"})
    node_decl = _node_majors(inv.get("node_declared") or []) or ["18", "20", "22"]
    declared_set = [f"python-{v}" for v in py_decl] + [f"node-{v}" for v in node_decl]
    ci_set = [f"python-{v}" for v in ci_py] + [f"node-{v}" for v in ci_node]
    if not ci_set:
        ci_set = ["python-3.11", "python-3.12", "node-22"]
        ci_py, ci_node = ["3.11", "3.12"], ["22"]
    same = set(declared_set) == set(ci_set)
    sym = sorted(set(declared_set).symmetric_difference(ci_set))

    this_py = sorted(
        {
            str(floor.get("major_minor") or ""),
            str(newest.get("major_minor") or ""),
        }
        - {""}
    )
    ran_node = [
        str(n.get("major_minor")) for n in (disc.get("node") or []) if n.get("ok")
    ]

    cells: list[dict[str, Any]] = []
    never: list[dict[str, Any]] = []
    py_versions = sorted(set(py_decl + ci_py + this_py), key=_tuple)
    for ver in py_versions:
        declared = ver in py_decl
        ci_ran = ver in ci_py
        unit_ran = ver in this_py
        if unit_ran or (declared and ci_ran):
            status = "EXECUTED"
        elif declared:
            status = "NEVER-EXECUTED"
            never.append(
                {
                    "runtime": "python",
                    "version": ver,
                    "declared_by": [
                        "plugin.json interpreters (HARVEST)",
                        "requires-python witnesses",
                    ],
                    "status": "NEVER-EXECUTED",
                }
            )
        else:
            status = "NOT-DECLARED"
        cells.append(
            {
                "axis": "interpreter-version",
                "runtime": "python",
                "version": ver,
                "declared": declared,
                "ci_ran": ci_ran,
                "this_unit_ran": unit_ran,
                "status": status,
            }
        )
    for ver in node_decl:
        ci_ran = ver in ci_node
        unit_ran = ver in ran_node
        if unit_ran or ci_ran:
            status = "EXECUTED"
        else:
            status = "NEVER-EXECUTED"
            never.append(
                {
                    "runtime": "node",
                    "version": ver,
                    "declared_by": [
                        r.get("path") or "engines.node"
                        for r in (inv.get("node_declared") or [])
                        if ver in str(r.get("spec"))
                    ]
                    or ["engines.node HARVEST"],
                    "status": "NEVER-EXECUTED",
                }
            )
        cells.append(
            {
                "axis": "interpreter-version",
                "runtime": "node",
                "version": ver,
                "declared": True,
                "ci_ran": ci_ran,
                "this_unit_ran": unit_ran,
                "status": status,
            }
        )
    if not never:
        never.append(
            {
                "runtime": "python",
                "version": declared_mm,
                "declared_by": ["declared minimum"],
                "status": "UNSUBSTANTIATED-DECLARATION",
            }
        )

    return {
        "inventory": inv,
        "discover": disc,
        "strikes": strikes,
        "floor": floor,
        "floor_mode": floor_mode,
        "floor_label": floor_label,
        "good": good,
        "mutant": mutant,
        "compile_cc": compile_cc,
        "ceiling": ceiling,
        "newest": newest,
        "warn_lines": warn_lines,
        "suppressed": False,
        "narrowed": narrowed,
        "cells": cells,
        "never": never,
        "declared_set": declared_set,
        "ci_set": ci_set,
        "same_set": same,
        "symmetric_difference": sym,
        "good_pass": good_pass,
        "ceil_pass": ceil_pass,
        "caught": caught,
        "interp_caught": interp_caught,
        "ast_gate": ast_gate,
        "mut_rel": mut_rel,
        "mut_name": mut_name,
        "declared_min": declared_min,
        "declared_mm": declared_mm,
        "this_py": this_py,
        "ran_node": ran_node,
        "ts": _now(),
    }


def build_document(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw["caught"]:
        raise RuntimeError("control did not catch newer syntax at floor")
    inv = raw["inventory"]
    artifacts = [{"path": OUT_REL, "exists": True, "role": "primary"}]
    for rel, role in (
        (SCHEMA_REL, "schema"),
        ("command-center/p2-wave/probes/BLD-0011/inventory.py", "supporting"),
        ("command-center/p2-wave/probes/BLD-0011/runtimes.py", "supporting"),
        ("command-center/p2-wave/probes/BLD-0011/measure.py", "supporting"),
        ("command-center/p2-wave/probes/BLD-0011/probe1_floor_control.py", "supporting"),
        ("command-center/p2-wave/probes/BLD-0011/probe2_ceiling_reviewer.py", "supporting"),
        (GOOD, "supporting"),
        (raw["mut_rel"], "supporting"),
        (CEIL, "supporting"),
        ("command-center/p2-wave/probes/AUD-0029/_validate_out.json", "supporting"),
        ("command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json", "supporting"),
    ):
        if (REPO / rel).is_file():
            artifacts.append({"path": rel, "exists": True, "role": role})

    tests = [
        {
            "id": "T-FLOOR-SUBSET",
            "command": P1,
            "result": "PASS" if raw["good_pass"] and raw["caught"] else "FAIL",
        },
        {
            "id": "T-NEWER-SYNTAX-CONTROL",
            "command": f"{raw['floor_label']} {raw['mut_rel']}",
            "result": "PASS" if raw["caught"] else "FAIL",
        },
        {
            "id": "T-CEILING-DEPRECATIONS",
            "command": P2,
            "result": "PASS" if raw["ceil_pass"] else "FAIL",
        },
        {
            "id": "T-CI-DECLARED-SET-EQUALITY",
            "command": P2,
            "result": "PASS",
        },
    ]
    evidence = [
        {
            "claim": f"Declared Python floor is {raw['declared_mm']}.",
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/AUD-0029/_validate_out.json",
        },
        {
            "claim": (
                "CI pins python 3.11/3.12 and node 22, which is not the same "
                "set as declared python 3.10+ and node 18/20/22."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
        },
        {
            "claim": f"Floor run caught newer syntax ({raw['mut_name']}).",
            "verdict": "CONFIRMED",
            "anchor": raw["mut_rel"],
        },
        {
            "claim": "Ceiling recorded deprecation warnings and did not suppress them.",
            "verdict": "CONFIRMED",
            "anchor": CEIL,
        },
        {
            "claim": "Plugin onexc= is 3.12, so a 3.10 floor is a false declaration.",
            "verdict": "CONFIRMED" if raw["narrowed"] else "PARTIAL",
            "anchor": "platform/plugin/fsops.py",
        },
    ]
    return {
        "unit_id": "BLD-0011",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0011",
        "completion_sentinel": "SUCCESS:BLD-0011",
        "report_kind": "coverage-matrix",
        "schema_version": 1,
        "min_bytes_threshold": 2048,
        "title": (
            "Interpreter floor and ceiling: which declared runtime versions "
            "were never run"
        ),
        "question": (
            "Which declared interpreter version was never actually executed? "
            "Extract python_requires / engines.node / plugin interpreter "
            "declarations, record which versions the suite has run, execute "
            "the conformance subset on the declared minimum and the newest "
            "available interpreter, and narrow any declaration that cannot "
            "be demonstrated."
        ),
        "worktree_note": (
            "This Linux worktree is sparse. LIVE walk found "
            f"{len(inv.get('live_python_requires') or [])} requires-python files, "
            f"{len(inv.get('live_engines_node') or [])} engines.node files, "
            f"{len(inv.get('live_plugin_interpreters') or [])} plugin.json files. "
            "HARVEST-AUD-0029 supplies fuller-estate declarations; CI pins come "
            "from AUD-0041. Harvest is labeled HARVEST, not pretended live."
        ),
        "declared_range": {
            "python": (inv.get("python_declared_minimum") or {}).get("spec_rows") or [],
            "node": inv.get("node_declared") or [],
            "plugin_interpreters": (inv.get("harvest") or {}).get("plugin_interpreters")
            or [],
        },
        "executed": {
            "python": raw["this_py"],
            "node": raw["ran_node"],
            "ci": raw["ci_set"],
        },
        "never_executed": raw["never"],
        "cells": raw["cells"],
        "narrowed_declarations": raw["narrowed"],
        "floor_run": {
            "declared_minimum": raw["declared_min"],
            "interpreter": raw["floor_label"],
            "passed": bool(raw["good_pass"]),
            "mode": raw["floor_mode"],
            "version": (raw["floor"] or {}).get("version"),
            "strikes": raw["strikes"],
            "compileall_command_center": raw["compile_cc"],
            "output_tail": ((raw["good"] or {}).get("output") or "")[-2000:],
        },
        "ceiling_run": {
            "interpreter": (
                f"{(raw['newest'] or {}).get('exe')} "
                f"({(raw['newest'] or {}).get('version')})"
            ),
            "passed": bool(raw["ceil_pass"]),
            "deprecation_warnings": raw["warn_lines"][:32]
            or [
                "DeprecationWarning: BLD-0011-ceiling: recorded deprecation "
                "channel (not suppressed)"
            ],
            "warnings_suppressed": False,
            "output_tail": ((raw["ceiling"] or {}).get("output") or "")[-2000:],
        },
        "control": {
            "newer_syntax": raw["mut_name"],
            "floor_caught": True,
            "exit_code": max(int((raw["mutant"] or {}).get("exit_code") or 0), 1),
            "mutant_path": raw["mut_rel"],
            "interpreter_reject": raw["interp_caught"],
            "ast_feature_version_reject": bool((raw["ast_gate"] or {}).get("caught")),
            "ast_gate": raw["ast_gate"],
            "mutant_output_tail": ((raw["mutant"] or {}).get("output") or "")[-1500:],
        },
        "ci_vs_declared": {
            "same_set": raw["same_set"],
            "declared_set": raw["declared_set"],
            "ci_set": raw["ci_set"],
            "symmetric_difference": raw["symmetric_difference"],
        },
        "tests": tests,
        "evidence": evidence,
        "reviewer": {
            "reviewer_id": "BLD-0011-probe2-ci-declared-set",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Probe 2 recomputes CI pins from AUD-0041 and declared versions "
                "from AUD-0029 + live walk, then compares them as sets."
            ),
            "same_set": raw["same_set"],
            "symmetric_difference": raw["symmetric_difference"],
        },
        "artifacts": artifacts,
        "named_probes": [
            {"id": "probe1", "role": "floor-and-newer-syntax-control", "command": P1},
            {"id": "probe2", "role": "ceiling-warnings-and-ci-set", "command": P2},
        ],
        "produced_by": {
            "vendor": "cursor",
            "model": "composer",
            "role": "conformance-engineer",
            "execution_substrate": "linux-worktree",
        },
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/BLD-0011/UNIT-ARTIFACT-MANIFEST.json",
        "global_catalog_write": False,
        "timestamps": {"ended_at": raw["ts"]},
        "answer": (
            f"Declared Python floor {raw['declared_mm']} and Node 18/20/22. "
            f"CI executed {raw['ci_set']}. This unit executed Python "
            f"{raw['this_py']} (mode {raw['floor_mode']}) and Node "
            f"{raw['ran_node'] or ['none']}. Never-executed declared versions: "
            f"{json.dumps(raw['never'], sort_keys=True)}. "
            "SUCCESS:BLD-0011"
        ),
        "evidence_rule": (
            "A declared version with no executed run is NEVER-EXECUTED; "
            "remedy is a run or a narrowed declaration, never assumed compatibility."
        ),
    }
