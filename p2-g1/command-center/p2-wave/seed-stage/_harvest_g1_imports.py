#!/usr/bin/env python3
"""Harvest probe import surfaces for G-1 missing modules (incl. parenthesized lists)."""
from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
OUT = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "g1-import-harvest.json"

PREFIXES = (
    "tools.council",
    "council",
    "marketplace",
    "tools.marketplace",
    "workflow_foundry",
    "router",
    "tools.router",
    "bench",
    "tools.bench",
    "plugin",
    "tools.plugin",
    "foundry",
)


def keep(name: str) -> bool:
    for pref in PREFIXES:
        if name == pref or name.startswith(pref + "."):
            return True
    return False


def alias_name(alias: ast.alias) -> str:
    return alias.asname or alias.name


def main() -> int:
    mods: Counter[str] = Counter()
    by_mod: dict[str, set[str]] = defaultdict(set)
    imported_names: dict[str, Counter[str]] = defaultdict(Counter)
    files_checked = 0
    parse_fail = 0
    for path in PROBES.rglob("*.py"):
        files_checked += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(REPO)).replace("\\", "/")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            parse_fail += 1
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if keep(name):
                        mods[name] += 1
                        by_mod[name].add(rel)
            elif isinstance(node, ast.ImportFrom):
                if not node.module:
                    continue
                name = node.module
                if not keep(name):
                    continue
                mods[name] += 1
                by_mod[name].add(rel)
                for alias in node.names:
                    if alias.name == "*":
                        imported_names[name]["*"] += 1
                        continue
                    imported_names[name][alias.name] += 1
    out = {
        "files_checked": files_checked,
        "parse_fail": parse_fail,
        "unique_mods": len(mods),
        "mods": {
            k: {
                "n": v,
                "names": dict(imported_names[k].most_common(80)),
                "files": sorted(by_mod[k])[:16],
            }
            for k, v in mods.most_common()
        },
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"files {files_checked} parse_fail {parse_fail} unique {len(mods)}", flush=True)
    for name, c in mods.most_common(120):
        names = ",".join(list(imported_names[name])[:8])
        print(f"{c:4d} {name} :: {names}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
