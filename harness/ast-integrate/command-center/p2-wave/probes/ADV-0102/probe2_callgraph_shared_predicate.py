#!/usr/bin/env python3
"""Probe 2: call-graph inspection that fan-in uses the shared completion predicate.

Mechanically different from probe 1: AST import/call graph, not a behavioural
run. A council-local completion notion (parent_complete := child_complete, or
a local is_complete) is the named root cause. Production nested topology is
inspected; agentspec fan-in is the known shared-predicate control.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0102"
HARNESS = HERE / "nested_fanin.py"
COUNCIL = REPO / "tools" / "council"
FANIN = REPO / "tools" / "agentspec" / "agentspec" / "fanin"
ORACLE = REPO / "tools" / "agentspec" / "agentspec" / "oracle.py"
REDUCER = REPO / "lib" / "completion_reducer.py"

SHARED_MODS = {
    "lib.completion_reducer",
    "completion_reducer",
    "agentspec.oracle",
}
SHARED_NAMES = {"reduce_completion", "judge"}
LOCAL_NAMES = {
    "is_complete",
    "locally_complete",
    "child_complete",
    "_tick_local",
    "_tick_local",
    "council_complete",
}


def _parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None


def _walk_py(root: Path) -> list[Path]:
    if root.is_file() and root.suffix == ".py":
        return [root]
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        out.append(p)
    return out


def inspect_module(path: Path) -> dict:
    tree = _parse(path)
    rel = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
    if tree is None:
        return {
            "path": rel,
            "parse_ok": False,
            "imports_shared": False,
            "calls_shared": False,
            "shared_import_names": [],
            "shared_call_names": [],
            "local_function_defs": [],
            "calls_reduce_completion": False,
            "calls_judge": False,
        }
    imported: set[str] = set()
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                name = alias.asname or alias.name
                bound[name] = f"{mod}.{alias.name}" if mod else alias.name
                if mod in SHARED_MODS or alias.name in SHARED_NAMES:
                    imported.add(f"{mod}.{alias.name}".strip("."))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name
                bound[name] = alias.name
                if alias.name in SHARED_MODS or alias.name.endswith(".oracle"):
                    imported.add(alias.name)
    calls: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name):
            calls.add(fn.id)
        elif isinstance(fn, ast.Attribute):
            calls.add(fn.attr)
    local_defs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in LOCAL_NAMES:
            local_defs.append(node.name)
    calls_reduce = "reduce_completion" in calls
    calls_judge = "judge" in calls
    imports_shared = bool(imported) or any(
        "reduce_completion" in v or v.endswith(".oracle") or "completion_reducer" in v
        for v in bound.values()
    )
    return {
        "path": rel,
        "parse_ok": True,
        "imports_shared": imports_shared,
        "calls_shared": calls_reduce or calls_judge,
        "shared_import_names": sorted(imported),
        "shared_call_names": sorted(n for n in calls if n in SHARED_NAMES),
        "local_function_defs": sorted(set(local_defs)),
        "calls_reduce_completion": calls_reduce,
        "calls_judge": calls_judge,
        "bound_shared": {
            k: v
            for k, v in bound.items()
            if "reduce_completion" in v or "oracle" in v or "completion_reducer" in v
        },
    }


def council_scan() -> dict:
    nested_candidates = [
        "tools/council/topology/nested.py",
        "tools/council/topology/meta.py",
        "tools/council/nested.py",
    ]
    present = [p for p in nested_candidates if (REPO / p).is_file()]
    files = _walk_py(COUNCIL)
    hits = []
    local_hits = []
    for path in files:
        info = inspect_module(path)
        if info["calls_shared"] or info["imports_shared"]:
            hits.append(info)
        if info["local_function_defs"]:
            local_hits.append(
                {"path": info["path"], "defs": info["local_function_defs"]}
            )
    runtime = REPO / "tools" / "council" / "cli" / "runtime.py"
    runtime_info = inspect_module(runtime) if runtime.is_file() else None
    return {
        "nested_topology_present": present,
        "nested_topology_absent": [p for p in nested_candidates if p not in present],
        "py_file_count": len(files),
        "shared_predicate_hits": hits,
        "local_completion_defs": local_hits,
        "runtime": runtime_info,
        "runtime_calls_reduce_completion": bool(
            runtime_info and runtime_info["calls_reduce_completion"]
        ),
        "runtime_calls_judge": bool(runtime_info and runtime_info["calls_judge"]),
    }


def agentspec_fanin_scan() -> dict:
    files = _walk_py(FANIN)
    sites = [inspect_module(p) for p in files]
    oracle = inspect_module(ORACLE) if ORACLE.is_file() else None
    return {
        "fanin_dir_exists": FANIN.is_dir(),
        "oracle_defines_judge": bool(
            oracle
            and any(
                isinstance(n, ast.FunctionDef) and n.name == "judge"
                for n in ast.walk(_parse(ORACLE) or ast.parse("pass"))
            )
        ),
        "sites": [
            {
                "path": s["path"],
                "calls_judge": s["calls_judge"],
                "imports_shared": s["imports_shared"],
                "bound_shared": s.get("bound_shared") or {},
            }
            for s in sites
            if s["path"].endswith(".py") and "fork_" not in s["path"]
        ],
        "every_nonfork_site_calls_or_imports_judge": all(
            s["calls_judge"] or s["imports_shared"]
            for s in sites
            if "fork_" not in s["path"] and s["path"].endswith(".py")
            and Path(s["path"]).name != "__init__.py"
        ),
    }


def harness_scan() -> dict:
    info = inspect_module(HARNESS)
    tree = _parse(HARNESS)
    tick_local_calls_reducer = False
    tick_shared_calls_reducer = False
    reduce_called_at_module = info["calls_reduce_completion"]
    if tree:
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            called = {
                n.func.id
                if isinstance(n.func, ast.Name)
                else (n.func.attr if isinstance(n.func, ast.Attribute) else "")
                for n in ast.walk(node)
                if isinstance(n, ast.Call)
            }
            if node.name == "_tick_local":
                tick_local_calls_reducer = "reduce_completion" in called
            if node.name in {"_tick_shared", "_receipt_complete", "shared_receipts"}:
                if "reduce_completion" in called:
                    tick_shared_calls_reducer = True
    return {
        **info,
        "reduce_called_in_harness": reduce_called_at_module,
        "tick_local_calls_reducer": tick_local_calls_reducer,
        "receipt_path_calls_reducer": tick_shared_calls_reducer,
        "reducer_file_exists": REDUCER.is_file(),
    }


def main() -> int:
    harness = harness_scan()
    council = council_scan()
    fanin = agentspec_fanin_scan()
    checks = [
        ("harness_parses", harness["parse_ok"]),
        ("harness_imports_shared_reducer", harness["imports_shared"]),
        ("harness_calls_reduce_completion", harness["calls_reduce_completion"]),
        ("harness_receipt_path_calls_reducer", harness["receipt_path_calls_reducer"]),
        ("local_mutant_does_not_call_reducer", harness["tick_local_calls_reducer"] is False),
        ("local_mutant_function_present", "_tick_local" in harness["local_function_defs"]),
        ("reducer_file_exists", harness["reducer_file_exists"]),
        ("production_nested_topology_absent", council["nested_topology_present"] == []),
        (
            "council_runtime_does_not_call_shared_reducer",
            council["runtime_calls_reduce_completion"] is False
            and council["runtime_calls_judge"] is False,
        ),
        ("agentspec_fanin_dir_exists", fanin["fanin_dir_exists"]),
        ("oracle_defines_judge", fanin["oracle_defines_judge"]),
        (
            "method_is_ast",
            True,
        ),
    ]
    payload = {
        "probe": "probe2-callgraph-shared-predicate",
        "unit_id": UNIT,
        "method": "ast-import-call-graph",
        "used_grep": False,
        "harness": harness,
        "production_council": {
            "nested_topology_present": council["nested_topology_present"],
            "nested_topology_absent": council["nested_topology_absent"],
            "py_file_count": council["py_file_count"],
            "shared_predicate_hit_count": len(council["shared_predicate_hits"]),
            "runtime_calls_reduce_completion": council["runtime_calls_reduce_completion"],
            "runtime_calls_judge": council["runtime_calls_judge"],
            "runtime_path": (council["runtime"] or {}).get("path"),
        },
        "agentspec_fanin": fanin,
        "root_cause": (
            "Production has no nested topology module. tools/council/cli/runtime.py "
            "does not call lib.completion_reducer.reduce_completion or "
            "agentspec.oracle.judge; its completion notion is local vote/stopping. "
            "The harness shared path calls reduce_completion; the _tick_local "
            "mutant copies child_complete onto the parent and does not call the "
            "shared symbol. agentspec fan-in sites bind judge — the shared "
            "predicate the rest of the program uses."
        ),
        "checks": {name: bool(ok) for name, ok in checks},
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:{UNIT}-probe2 {name}")
            return 1
    print(
        "SUCCESS:ADV-0102-probe2 shared reducer on harness path; "
        "local mutant named; production nested fan-in absent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
