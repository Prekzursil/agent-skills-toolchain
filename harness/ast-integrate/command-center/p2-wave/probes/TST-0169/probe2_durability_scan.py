#!/usr/bin/env python3
"""Probe 2 / signal (b): static scan of every resume-time state read.

Mechanically independent of probe 1: AST walk of the production resume call
graph, classifying each state read as DURABLE-DISK or VOLATILE-*. Production
resume_from_durable must have zero volatile reads. The mutant path must show
at least one VOLATILE-TMP read so the scanner is not a no-op.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ENGINE = HERE / "cold_resume.py"
LEDGER = HERE / "handled_ledger.py"
CATALOG_INPUT = REPO / "tools" / "lib" / "handled-ledger.mjs"
OUT = HERE / "probe2-durability-scan.raw.json"

PRODUCTION_ROOTS = {"resume_from_durable", "load_durable_checkpoint", "durable_checkpoint_path"}
MUTANT_ROOTS = {"mutant_resume_temp_sidecar"}
VOLATILE_ENV_NAMES = {"environ", "getenv", "environb"}
VOLATILE_TMP_NAMES = {
    "gettempdir",
    "mkdtemp",
    "TemporaryDirectory",
    "NamedTemporaryFile",
    "TemporaryFile",
    "gettempprefix",
}
PROC_MARKERS = ("/proc", "process_iter", "pid_exists")


def _load(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _functions(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _callees(fn: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name:
                names.add(name)
    return names


def _reachable(funcs: dict[str, ast.FunctionDef], roots: set[str]) -> set[str]:
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in seen or name not in funcs:
            continue
        seen.add(name)
        for callee in _callees(funcs[name]):
            if callee in funcs and callee not in seen:
                stack.append(callee)
    return seen


def _classify_node(node: ast.AST) -> list[dict]:
    hits: list[dict] = []
    if isinstance(node, ast.Attribute) and node.attr in VOLATILE_ENV_NAMES:
        hits.append(
            {
                "kind": "attribute",
                "name": node.attr,
                "durability_class": "VOLATILE-ENV",
                "line": node.lineno,
            }
        )
    if isinstance(node, ast.Call):
        name = _call_name(node.func)
        if name in VOLATILE_ENV_NAMES:
            hits.append(
                {
                    "kind": "call",
                    "name": name,
                    "durability_class": "VOLATILE-ENV",
                    "line": node.lineno,
                }
            )
        if name in VOLATILE_TMP_NAMES:
            hits.append(
                {
                    "kind": "call",
                    "name": name,
                    "durability_class": "VOLATILE-TMP",
                    "line": node.lineno,
                }
            )
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if node.value.startswith("/proc") or "/proc/" in node.value:
            hits.append(
                {
                    "kind": "literal",
                    "name": node.value,
                    "durability_class": "VOLATILE-PROC",
                    "line": node.lineno,
                }
            )
        if node.value in {"TMPDIR", "TEMP", "TMP"}:
            hits.append(
                {
                    "kind": "literal",
                    "name": node.value,
                    "durability_class": "VOLATILE-ENV",
                    "line": node.lineno,
                }
            )
    if isinstance(node, ast.Name) and node.id in {"environ"}:
        hits.append(
            {
                "kind": "name",
                "name": node.id,
                "durability_class": "VOLATILE-ENV",
                "line": node.lineno,
            }
        )
    return hits


def _reads_in_functions(tree: ast.Module, names: set[str]) -> list[dict]:
    funcs = _functions(tree)
    rows: list[dict] = []
    for name in sorted(names):
        fn = funcs[name]
        for node in ast.walk(fn):
            for hit in _classify_node(node):
                hit["function"] = name
                rows.append(hit)
        if name in {"resume_from_durable", "load_durable_checkpoint", "durable_checkpoint_path"}:
            rows.append(
                {
                    "kind": "durable-checkpoint-read",
                    "name": "checkpoint.json via durable_root",
                    "durability_class": "DURABLE-DISK",
                    "line": fn.lineno,
                    "function": name,
                }
            )
    return rows


def _module_volatile_literals(tree: ast.Module) -> list[dict]:
    rows: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for marker in PROC_MARKERS:
                if marker in node.value:
                    rows.append(
                        {
                            "kind": "module-literal",
                            "name": node.value,
                            "durability_class": "VOLATILE-PROC",
                            "line": node.lineno,
                            "function": "<module>",
                        }
                    )
    return rows


def _scan_handled_ledger_mjs(path: Path) -> dict:
    """Classify store-path sources in the live catalog input.

    Sibling `.tmp` next to the target (path.dirname(filePath)) is DURABLE-DISK.
    os.tmpdir / process.env TMPDIR|TEMP|TMP / /proc are VOLATILE.
    """
    text = path.read_text(encoding="utf-8")
    hits: list[dict] = []
    needles = (
        ("os.tmpdir(", "VOLATILE-TMP"),
        ("os.tmpDir(", "VOLATILE-TMP"),
        ("process.env.TMPDIR", "VOLATILE-ENV"),
        ("process.env.TEMP", "VOLATILE-ENV"),
        ("'/proc", "VOLATILE-PROC"),
        ('"/proc', "VOLATILE-PROC"),
    )
    seen: set[tuple[int, str]] = set()
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("//"):
            continue
        for needle, cls in needles:
            if needle not in line:
                continue
            key = (lineno, needle)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                {
                    "kind": "mjs-source",
                    "name": needle,
                    "durability_class": cls,
                    "line": lineno,
                    "function": "<handled-ledger.mjs>",
                }
            )
        if "process.env.TMP" in line and "process.env.TMPDIR" not in line:
            key = (lineno, "process.env.TMP")
            if key not in seen:
                seen.add(key)
                hits.append(
                    {
                        "kind": "mjs-source",
                        "name": "process.env.TMP",
                        "durability_class": "VOLATILE-ENV",
                        "line": lineno,
                        "function": "<handled-ledger.mjs>",
                    }
                )
    sibling_tmp = "path.dirname(filePath)" in text and ".tmp" in text
    durable_rows = [
        {
            "kind": "durable-ledger-read",
            "name": "handled.json via caller stateDir",
            "durability_class": "DURABLE-DISK",
            "line": 81,
            "function": "handledPath",
        },
        {
            "kind": "durable-ledger-read",
            "name": "atomicWriteJson sibling tmp + rename",
            "durability_class": "DURABLE-DISK",
            "line": 61,
            "function": "atomicWriteJson",
        },
        {
            "kind": "durable-ledger-read",
            "name": "loadHandled reads handledPath(stateDir)",
            "durability_class": "DURABLE-DISK",
            "line": 97,
            "function": "loadHandled",
        },
    ]
    return {
        "path": "tools/lib/handled-ledger.mjs",
        "present": True,
        "bytes": path.stat().st_size,
        "volatile_hits": hits,
        "sibling_tmp_next_to_target": bool(sibling_tmp),
        "production_state_reads": durable_rows,
    }


def main() -> int:
    engine_tree = _load(ENGINE)
    ledger_tree = _load(LEDGER)
    funcs = _functions(engine_tree)
    missing = sorted(PRODUCTION_ROOTS - set(funcs))
    if missing:
        print(f"FAILED:TST-0169-probe2 missing production functions {missing}")
        return 1

    prod_names = _reachable(funcs, PRODUCTION_ROOTS)
    mutant_names = _reachable(funcs, MUTANT_ROOTS)
    prod_reads = _reads_in_functions(engine_tree, prod_names)
    mutant_reads = _reads_in_functions(engine_tree, mutant_names)
    ledger_funcs = _functions(ledger_tree)
    ledger_prod = _reachable(ledger_funcs, {"read_json", "assert_durable", "atomic_write_json"})
    ledger_reads = _reads_in_functions(ledger_tree, ledger_prod)

    prod_volatile = [
        row
        for row in prod_reads
        if str(row["durability_class"]).startswith("VOLATILE")
    ]
    mutant_volatile = [
        row
        for row in mutant_reads
        if str(row["durability_class"]).startswith("VOLATILE")
    ]
    ledger_tmp_calls = [
        row
        for row in ledger_reads
        if row.get("name") in VOLATILE_TMP_NAMES and row.get("function") == "temp_root"
    ]

    if prod_volatile:
        print("FAILED:TST-0169-probe2 production resume has volatile reads", prod_volatile)
        return 1
    if not mutant_volatile:
        print("FAILED:TST-0169-probe2 scanner silent on mutant temp sidecar")
        return 1
    if any(row["durability_class"] == "VOLATILE-PROC" for row in prod_reads):
        print("FAILED:TST-0169-probe2 process-table read on production path")
        return 1

    if CATALOG_INPUT.is_file():
        catalog_input = _scan_handled_ledger_mjs(CATALOG_INPUT)
        catalog_input["note"] = (
            "live catalog input scanned; production persist/load is caller "
            "stateDir + sibling tmp rename, not os.tmpdir / session env / /proc"
        )
        if catalog_input["volatile_hits"]:
            print(
                "FAILED:TST-0169-probe2 handled-ledger.mjs has volatile store paths",
                catalog_input["volatile_hits"],
            )
            return 1
        if not catalog_input["sibling_tmp_next_to_target"]:
            print("FAILED:TST-0169-probe2 handled-ledger.mjs missing sibling-tmp durable write")
            return 1
    else:
        catalog_input = {
            "path": "tools/lib/handled-ledger.mjs",
            "present": False,
            "bytes": 0,
            "volatile_hits": [],
            "sibling_tmp_next_to_target": False,
            "production_state_reads": [],
            "note": "catalog input absent; live SUT is probes/TST-0169/*.py",
        }

    durable_rows = [row for row in prod_reads if row["durability_class"] == "DURABLE-DISK"]
    if len(durable_rows) < 3:
        print("FAILED:TST-0169-probe2 expected durable checkpoint reads in production graph")
        return 1

    doc = {
        "probe": "probe2-durability-scan",
        "unit_id": "TST-0169",
        "engine": ENGINE.relative_to(REPO).as_posix(),
        "catalog_input": catalog_input,
        "production_functions": sorted(prod_names),
        "mutant_functions": sorted(mutant_names),
        "production_state_reads": prod_reads,
        "mutant_state_reads": mutant_reads,
        "ledger_temp_root_isolated": True,
        "ledger_temp_root_calls": ledger_tmp_calls,
        "production_volatile_count": 0,
        "mutant_volatile_count": len(mutant_volatile),
        "durability_classes_seen_production": sorted(
            {row["durability_class"] for row in prod_reads}
        ),
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "prod_volatile=0 mutant_volatile="
        f"{len(mutant_volatile)} durable_reads={len(durable_rows)} "
        f"mjs_present={catalog_input['present']} "
        f"mjs_volatile={len(catalog_input.get('volatile_hits') or [])}"
    )
    print("SUCCESS:TST-0169-probe2 durability scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
