#!/usr/bin/env python3
"""Probe 2: alias transitivity + loaders consume the map (not documentation).

Renaming twice must still resolve to the current record. Graph loaders must
call resolve() when loading provenance and compat edges.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import graph_loaders as L  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0010-id-stability-and-migration-map.json"
SHIPPED = REPO / "command-center/wfa/graph_loaders.py"
SENTINEL = "SUCCESS:WFA-0010"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0010-probe2 {msg}")
    return 1


def _calls_resolve(src: str, func_name: str) -> bool:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    fn = child.func
                    if isinstance(fn, ast.Name) and fn.id == "resolve":
                        return True
                    if isinstance(fn, ast.Attribute) and fn.attr == "resolve":
                        return True
    return False


def main() -> int:
    data = C.build_corpus()
    trans = data["transitivity"]
    print(
        f"transitivity start={trans['start']} once={trans['after_first']} "
        f"twice={trans['after_second']} resolve_start={trans['resolve_start']} "
        f"ok={trans['ok']}"
    )
    if not trans["ok"]:
        return fail("double rename did not resolve to the current record")

    src = (HERE / "graph_loaders.py").read_text(encoding="utf-8")
    if not _calls_resolve(src, "load_provenance"):
        return fail("load_provenance does not call resolve")
    if not _calls_resolve(src, "load_compat"):
        return fail("load_compat does not call resolve")
    if "documentation" in src.lower() and "call resolve" not in src:
        # Keep the module honest: the docstring may mention documentation,
        # but the functions must still call resolve (already checked).
        pass

    if not SHIPPED.is_file():
        return fail("shipped command-center/wfa/graph_loaders.py missing")
    shipped_src = SHIPPED.read_text(encoding="utf-8")
    if not _calls_resolve(shipped_src, "load_provenance"):
        return fail("shipped load_provenance does not call resolve")

    # Live consume: two-step rename through the shipped resolver.
    freeze = data["freeze_rows"]
    sample = trans["start"]
    aliases = L.alias_map_from_rows(freeze)
    aliases[sample] = trans["after_first"]
    aliases[trans["after_first"]] = trans["after_second"]
    aliases[trans["after_second"]] = trans["after_second"]
    got = L.resolve(sample, aliases)
    if got != trans["after_second"]:
        return fail(f"shipped resolve {got!r} != {trans['after_second']!r}")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    mmap = doc.get("migration_map") or {}
    rows = mmap.get("alias_rows") or []
    if not isinstance(rows, list) or not rows:
        return fail("migration map is empty or not machine-readable")
    if mmap.get("format") != "wfa-id-alias-v1":
        return fail("migration map format missing")
    loaders = doc.get("graph_loaders") or {}
    if loaders.get("documentation_only") is not False:
        return fail("artifact claims documentation-only loaders")
    if loaders.get("consumes_map") is not True:
        return fail("artifact does not claim loaders consume the map")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if not (tests.get("alias-rows-transitive") or {}).get("pass"):
        return fail("artifact transitivity test not pass")
    print("SUCCESS:WFA-0010-probe2 transitive aliases and loaders consume map")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
