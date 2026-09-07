#!/usr/bin/env python3
"""AUD-0032 Probe 1: AST-level module reference resolution (use, not mention).

Reports modules with zero inbound AST import edges as DEAD under probe 1.
Includes a planted string-registry-only module that MUST be DEAD here.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent
SCOPE_ROOTS = ["tools"]
CONTROL_DIR = OUT_DIR / "string-registry-control"


def module_name_for(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def collect_modules() -> dict[str, Path]:
    mods: dict[str, Path] = {}
    for root_name in SCOPE_ROOTS:
        root = REPO / root_name
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            if any(x in p.parts for x in (".venv", "node_modules", "__pycache__")):
                continue
            # skip tests for dead-code primary surface? include them — refs from tests count
            name = module_name_for(p, REPO)
            mods[name] = p
    # Planted control module (string-registry only)
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    planted = CONTROL_DIR / "planted_registry_only_mod.py"
    if not planted.exists():
        planted.write_text(
            '"""Planted control: only reached via string registry, never imported."""\n'
            "DEFINITELY_LIVE_IF_STRING_REACHED = True\n",
            encoding="utf-8",
        )
    registry = CONTROL_DIR / "registry.py"
    if not registry.exists():
        registry.write_text(
            "PLUGIN_REGISTRY = {\n"
            '    "planted": "command-center.p2-wave.probes.AUD-0032.string-registry-control.planted_registry_only_mod",\n'
            "}\n\n"
            "def load(name):\n"
            "    import importlib\n"
            "    return importlib.import_module(PLUGIN_REGISTRY[name])\n",
            encoding="utf-8",
        )
    for p in CONTROL_DIR.glob("*.py"):
        name = module_name_for(p, REPO)
        mods[name] = p
    return mods


def resolve_import(module: str, level: int, cur: str, known: set[str]) -> str | None:
    if level == 0:
        # absolute
        if module in known:
            return module
        # prefix match for package imports
        parts = module.split(".")
        for i in range(len(parts), 0, -1):
            cand = ".".join(parts[:i])
            if cand in known:
                return cand
        return None
    # relative
    cur_parts = cur.split(".")[:-1]  # drop module leaf
    if level > len(cur_parts) + 1:
        return None
    base = cur_parts[: len(cur_parts) - (level - 1)]
    if module:
        cand = ".".join(base + module.split("."))
    else:
        cand = ".".join(base)
    if cand in known:
        return cand
    parts = cand.split(".")
    for i in range(len(parts), 0, -1):
        c = ".".join(parts[:i])
        if c in known:
            return c
    return None


def build_graph(mods: dict[str, Path]) -> tuple[dict[str, set[str]], int]:
    known = set(mods)
    edges: dict[str, set[str]] = {m: set() for m in mods}
    sites = 0
    for name, path in mods.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    sites += 1
                    tgt = resolve_import(alias.name, 0, name, known)
                    if tgt and tgt != name:
                        edges[name].add(tgt)
            elif isinstance(node, ast.ImportFrom):
                sites += 1
                mod = node.module or ""
                tgt = resolve_import(mod, node.level, name, known)
                if tgt and tgt != name:
                    edges[name].add(tgt)
    return edges, sites


def main() -> int:
    mods = collect_modules()
    edges, sites = build_graph(mods)
    inbound: dict[str, int] = {m: 0 for m in mods}
    for src, tgts in edges.items():
        for t in tgts:
            inbound[t] = inbound.get(t, 0) + 1

    planted_name = module_name_for(CONTROL_DIR / "planted_registry_only_mod.py", REPO)
    registry_name = module_name_for(CONTROL_DIR / "registry.py", REPO)

    dead = sorted([m for m, n in inbound.items() if n == 0 and m != registry_name])
    # registry itself may also be unreferenced — that's fine
    live = sorted([m for m, n in inbound.items() if n > 0])

    planted_dead = planted_name in dead or inbound.get(planted_name, 0) == 0

    result = {
        "unit": "AUD-0032",
        "probe": 1,
        "scope": SCOPE_ROOTS + ["planted-control"],
        "module_count": len(mods),
        "import_sites": sites,
        "edge_count": sum(len(v) for v in edges.values()),
        "live_count": len(live),
        "dead_count": len([m for m in dead if inbound.get(m, 0) == 0]),
        "dead_sample": [m for m in dead if m != planted_name][:40],
        "planted_module": planted_name,
        "planted_ast_dead": planted_dead,
        "inbound": {k: inbound[k] for k in sorted(inbound)[:200]},
        "ok": planted_dead and len(mods) > 10,
    }
    (OUT_DIR / "probe1-ast-refs.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "AUD-0032 NAMED PROBE 1: AST-level symbol/module reference resolution",
        f"unit=AUD-0032",
        f"module_count={len(mods)}",
        f"import_sites={sites}",
        f"edge_count={result['edge_count']}",
        f"live_count={result['live_count']}",
        f"dead_count={result['dead_count']}",
        f"planted_module={planted_name}",
        f"planted_ast_dead={planted_dead}",
        f"dead_sample={result['dead_sample']!r}",
        "SUCCESS:AUD-0032-probe1" if result["ok"] else "FAILED:AUD-0032-probe1",
    ]
    raw = "\n".join(lines) + "\n"
    (OUT_DIR / "probe1-ast.raw.txt").write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
