#!/usr/bin/env python3
"""Enumerate A4 activation entry points and prove each crosses authorize_activation."""
from __future__ import annotations

import ast
import inspect
import shutil
import tempfile
import textwrap
from pathlib import Path
from typing import Any

import gateway as G
import sequence as S

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATEWAY_REL = "command-center/p2-wave/probes/ARC-0027/gateway.py"


def _line_of(fn) -> int:
    return int(inspect.getsourcelines(fn)[1])


def listed_paths() -> list[dict[str, Any]]:
    src = (REPO / GATEWAY_REL).read_text(encoding="utf-8")
    tree = ast.parse(src)
    authorize_line = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "authorize_activation":
            authorize_line = int(node.lineno)
    if authorize_line is None:
        raise RuntimeError("authorize_activation missing")

    rows = []
    for name in G.ACTIVATION_ENTRY_POINTS:
        fn = G.ENTRY_DISPATCH[name]
        rows.append(
            {
                "id": name,
                "function": name,
                "path": GATEWAY_REL,
                "line": _line_of(fn),
                "check_function": "authorize_activation",
                "check_path": GATEWAY_REL,
                "check_line": authorize_line,
                "crosses_check": _calls_authorize(src, name),
            }
        )
    return rows


def _calls_authorize(src: str, func_name: str) -> bool:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    callee = child.func
                    if isinstance(callee, ast.Name) and callee.id == "authorize_activation":
                        return True
            return False
    return False


def discover_activation_defs(src: str) -> set[str]:
    tree = ast.parse(src)
    found: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name in G.ACTIVATION_ENTRY_POINTS or node.name.startswith("activate_"):
            found.add(node.name)
    return found


def completeness(src: str | None = None) -> dict[str, Any]:
    text = src if src is not None else (REPO / GATEWAY_REL).read_text(encoding="utf-8")
    listed = set(G.ACTIVATION_ENTRY_POINTS)
    discovered = discover_activation_defs(text)
    uncovered = sorted(discovered - listed)
    extra = sorted(listed - discovered)
    missing_check = [
        name
        for name in sorted(listed & discovered)
        if not _calls_authorize(text, name)
    ]
    controls_ok = all(
        not _calls_authorize(text, name) for name in G.NON_ACTIVATION_CONTROLS
    )
    return {
        "listed": sorted(listed),
        "discovered": sorted(discovered),
        "uncovered": uncovered,
        "listed_but_absent": extra,
        "missing_check": missing_check,
        "controls_do_not_use_activate_choke": controls_ok,
        "complete": not uncovered and not extra and not missing_check and controls_ok,
    }


def runtime_each_path_crosses() -> dict[str, Any]:
    tmp = tempfile.TemporaryDirectory(prefix="arc0027-paths-")
    try:
        estate = Path(tmp.name) / "estate"
        shutil.copytree(S.FIXTURE, estate)
        G.edit_declared(estate, S.SUBJECT, S.ESCALATED)
        gw = G.make_gateway(estate, "activation")
        G.index_capabilities(gw)
        results = []
        for name, fn in G.ENTRY_DISPATCH.items():
            rec = fn(gw, S.SUBJECT)
            results.append(
                {
                    "id": name,
                    "outcome": rec["outcome"],
                    "crosses": rec["outcome"] == "DENY" and rec["used_cache"] is False,
                }
            )
        return {"pass": all(r["crosses"] for r in results), "rows": results}
    finally:
        tmp.cleanup()


def planted_bypass_caught() -> dict[str, Any]:
    src = (REPO / GATEWAY_REL).read_text(encoding="utf-8")
    mutant = src + textwrap.dedent(
        """

        def activate_side_door(gw, cap_id):
            declared = gw.read_declared(cap_id)
            return {"id": cap_id, "via": "activate_side_door", "outcome": "ALLOW",
                    "declared": declared, "effective_grant": declared,
                    "check_epoch": gw.check_epoch, "used_cache": False,
                    "reason": "planted-bypass"}
        """
    )
    live = completeness(src)
    bad = completeness(mutant)
    return {
        "live_complete": bool(live["complete"]),
        "mutant_complete": bool(bad["complete"]),
        "mutant_uncovered": bad["uncovered"],
        "pass": bool(live["complete"])
        and not bool(bad["complete"])
        and "activate_side_door" in bad["uncovered"],
    }


def run() -> dict[str, Any]:
    paths = listed_paths()
    comp = completeness()
    runtime = runtime_each_path_crosses()
    plant = planted_bypass_caught()
    ok = (
        bool(comp["complete"])
        and bool(runtime["pass"])
        and bool(plant["pass"])
        and len(paths) == len(G.ACTIVATION_ENTRY_POINTS)
        and all(p["crosses_check"] for p in paths)
    )
    return {
        "pass": ok,
        "paths": paths,
        "completeness": comp,
        "runtime": runtime,
        "planted_bypass": plant,
    }


if __name__ == "__main__":
    result = run()
    print(f"complete={result['completeness']['complete']} runtime={result['runtime']['pass']} plant={result['planted_bypass']['pass']}")
    raise SystemExit(0 if result["pass"] else 1)
