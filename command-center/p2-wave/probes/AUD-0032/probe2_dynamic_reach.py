#!/usr/bin/env python3
"""AUD-0032 Probe 2: dynamic reachability from entry points + CI + string registries.

A module reached only through a string-named plugin registry must be LIVE here
and DEAD under probe 1 — independence control.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent


def module_name_for(path: Path) -> str:
    rel = path.relative_to(REPO).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def entry_points_from_pyproject_and_mains() -> set[str]:
    found: set[str] = set()
    for p in (REPO / "tools").rglob("*.py"):
        if p.name in {"__main__.py", "app.py", "cli.py", "validate.py", "render.py", "seed.py"}:
            found.add(module_name_for(p))
        # if __name__ == "__main__"
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]', text):
            found.add(module_name_for(p))
    return found


def ci_python_targets() -> set[str]:
    """Map python path args in workflows to module names when under tools/."""
    mods: set[str] = set()
    wf = REPO / ".github" / "workflows"
    if not wf.is_dir():
        return mods
    for yml in wf.glob("*.yml"):
        text = yml.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"(?:python(?:3)?\s+(?:-B\s+)?)([\w./_-]+\.py)", text):
            rel = m.group(1)
            path = REPO / rel
            if path.is_file() and path.suffix == ".py":
                try:
                    mods.add(module_name_for(path))
                except ValueError:
                    pass
        for m in re.finditer(r"python\s+-m\s+([\w.]+)", text):
            mods.add(m.group(1))
    return mods


def doc_command_modules() -> set[str]:
    mods: set[str] = set()
    for rel in ["README.md", "AGENTS.md", "CLAUDE.md"]:
        p = REPO / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"(?:python(?:3)?\s+(?:-B\s+)?)([\w./_-]+\.py)", text):
            path = REPO / m.group(1)
            if path.is_file():
                try:
                    mods.add(module_name_for(path))
                except ValueError:
                    pass
    return mods


def string_registry_targets() -> set[str]:
    """Find importlib.import_module(x) and registry dict string module paths."""
    mods: set[str] = set()
    # Explicit planted registry
    registry = OUT_DIR / "string-registry-control" / "registry.py"
    if registry.is_file():
        text = registry.read_text(encoding="utf-8")
        for m in re.finditer(r'["\']([A-Za-z0-9_.-]+(?:\.[A-Za-z0-9_.-]+)+)["\']', text):
            mods.add(m.group(1))
    # Broader: tools/** registry-like string module names near import_module
    for p in (REPO / "tools").rglob("*.py"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "import_module" not in text and "PLUGIN" not in text and "registry" not in text.lower():
            continue
        for m in re.finditer(r'import_module\(\s*["\']([^"\']+)["\']', text):
            mods.add(m.group(1))
        for m in re.finditer(r'["\']((?:tools|command-center)[A-Za-z0-9_.-]*)["\']', text):
            cand = m.group(1)
            if cand.count(".") >= 1:
                mods.add(cand)
    return mods


def bfs_ast_closure(seeds: set[str], all_mods: dict[str, Path]) -> set[str]:
    """Expand seeds via AST imports."""
    known = set(all_mods)
    # build outbound edges
    edges: dict[str, set[str]] = {m: set() for m in known}
    for name, path in all_mods.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    for i in range(len(parts), 0, -1):
                        cand = ".".join(parts[:i])
                        if cand in known:
                            edges[name].add(cand)
                            break
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if node.level:
                    cur = name.split(".")[:-1]
                    base = cur[: len(cur) - (node.level - 1)] if node.level <= len(cur) else []
                    absmod = ".".join(base + ([mod] if mod else []))
                else:
                    absmod = mod
                parts = absmod.split(".") if absmod else []
                for i in range(len(parts), 0, -1):
                    cand = ".".join(parts[:i])
                    if cand in known:
                        edges[name].add(cand)
                        break
    reach = set()
    stack = [s for s in seeds if s in known]
    while stack:
        cur = stack.pop()
        if cur in reach:
            continue
        reach.add(cur)
        for nxt in edges.get(cur, ()):
            if nxt not in reach:
                stack.append(nxt)
    return reach


def collect_all_modules() -> dict[str, Path]:
    mods: dict[str, Path] = {}
    for p in (REPO / "tools").rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        mods[module_name_for(p)] = p
    control = OUT_DIR / "string-registry-control"
    for p in control.glob("*.py"):
        mods[module_name_for(p)] = p
    return mods


def main() -> int:
    p1 = json.loads((OUT_DIR / "probe1-ast-refs.json").read_text(encoding="utf-8"))
    planted = p1["planted_module"]
    all_mods = collect_all_modules()

    seeds = set()
    seeds |= entry_points_from_pyproject_and_mains()
    seeds |= ci_python_targets()
    seeds |= doc_command_modules()
    string_hits = string_registry_targets()
    # String registry targets are DIRECTLY live under probe 2 even without AST edge
    seeds |= {s for s in string_hits if s in all_mods}

    reached_ast = bfs_ast_closure(seeds & set(all_mods), all_mods)
    # Also mark string registry targets as live
    live = set(reached_ast) | ({planted} if planted in string_hits else set())
    # If planted is in string_hits, it is LIVE for probe 2
    planted_live = planted in string_hits or planted in live
    if planted_live:
        live.add(planted)

    dead = sorted(m for m in all_mods if m not in live)
    planted_ast_dead = bool(p1.get("planted_ast_dead"))
    control_ok = planted_ast_dead and planted_live

    result = {
        "unit": "AUD-0032",
        "probe": 2,
        "seed_entrypoints": sorted(entry_points_from_pyproject_and_mains())[:50],
        "seed_ci": sorted(ci_python_targets())[:50],
        "seed_docs": sorted(doc_command_modules())[:50],
        "string_registry_hits": sorted(string_hits)[:50],
        "seed_count": len(seeds),
        "live_count": len(live),
        "dead_count": len(dead),
        "dead_sample": dead[:40],
        "planted_module": planted,
        "planted_ast_dead": planted_ast_dead,
        "planted_dynamic_live": planted_live,
        "control_independent": control_ok,
        "ok": control_ok and len(all_mods) > 10,
    }
    (OUT_DIR / "probe2-dynamic-reachability.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "AUD-0032 NAMED PROBE 2: dynamic reachability from entry points + CI + string registries",
        f"unit=AUD-0032",
        f"seed_count={result['seed_count']}",
        f"live_count={result['live_count']}",
        f"dead_count={result['dead_count']}",
        f"planted_module={planted}",
        f"planted_ast_dead={planted_ast_dead}",
        f"planted_dynamic_live={planted_live}",
        f"control_independent={control_ok}",
        f"dead_sample={result['dead_sample']!r}",
        "SUCCESS:AUD-0032-probe2" if result["ok"] else "FAILED:AUD-0032-probe2",
    ]
    raw = "\n".join(lines) + "\n"
    (OUT_DIR / "probe2-dynamic.raw.txt").write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
