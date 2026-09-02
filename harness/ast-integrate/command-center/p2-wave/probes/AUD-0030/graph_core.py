"""AST import graph + Tarjan SCC for AUD-0030 (tools/ and tools/lib/)."""
from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
UNIT = "AUD-0030"
SKIP = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "vendor",
}


def repo_root() -> Path:
    for d in [HERE, *HERE.parents]:
        if (d / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return d
    raise RuntimeError("repo root not found")


REPO = repo_root()
TOOLS = REPO / "tools"
FIXTURE = HERE / "cycle-fixture"


def catalog_unit() -> dict[str, Any]:
    data = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == UNIT:
            return row
    raise RuntimeError("AUD-0030 missing from catalog")


def modname(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def iter_py_files(root: Path) -> list[Path]:
    out: list[Path] = []
    if not root.is_dir():
        return out
    for p in root.rglob("*.py"):
        if any(part in SKIP for part in p.parts):
            continue
        if p.is_file():
            out.append(p)
    return sorted(out)


def tarjan(nodes: list[str], edges: dict[str, list[str]]) -> list[list[str]]:
    """Iterative Tarjan SCC. Returns components of size>1, plus self-loops."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    onstack: dict[str, bool] = {}
    stack: list[str] = []
    out: list[list[str]] = []
    counter = [0]
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(edges.get(root, ())))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        onstack[root] = True
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]
                    counter[0] += 1
                    stack.append(w)
                    onstack[w] = True
                    work.append((w, iter(edges.get(w, ()))))
                    advanced = True
                    break
                if onstack.get(w):
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                pv = work[-1][0]
                low[pv] = min(low[pv], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    onstack[w] = False
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1 or v in edges.get(v, ()):
                    out.append(sorted(comp))
    return out


def build_graph(files: list[Path], root: Path) -> tuple[dict[str, list[str]], dict[str, int], dict[str, int]]:
    known = {modname(p, root): p for p in files}
    prefixes: set[str] = set()
    for m in known:
        parts = m.split(".")
        for i in range(1, len(parts) + 1):
            prefixes.add(".".join(parts[:i]))
    siblings: dict[tuple[str, str], str] = {}
    for p in files:
        siblings[(p.parent.as_posix(), p.stem)] = modname(p, root)
    edges: dict[str, set[str]] = defaultdict(set)
    unresolved: Counter[str] = Counter()
    for p in files:
        me = modname(p, root)
        edges.setdefault(me, set())
        try:
            tree = ast.parse(
                p.read_text(encoding="utf-8", errors="replace"), filename=str(p)
            )
        except SyntaxError:
            unresolved["<syntax-error>"] += 1
            continue
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = me.split(".")[: max(len(me.split(".")) - node.level, 0)]
                    targets = [".".join(base + ([node.module] if node.module else []))]
                elif node.module:
                    targets = [node.module]
            for t in targets:
                if not t:
                    continue
                hit = None
                parts = t.split(".")
                for i in range(len(parts), 0, -1):
                    cand = ".".join(parts[:i])
                    if cand in known:
                        hit = cand
                        break
                    if cand in prefixes and cand in known:
                        hit = cand
                        break
                if hit is None:
                    hit = siblings.get((p.parent.as_posix(), parts[0]))
                if hit and hit != me:
                    edges[me].add(hit)
                elif not hit:
                    unresolved[parts[0]] += 1
    fanin: Counter[str] = Counter()
    for src, dsts in edges.items():
        for d in dsts:
            fanin[d] += 1
    return {k: sorted(v) for k, v in edges.items()}, dict(fanin), dict(unresolved)


def run_control() -> dict[str, Any]:
    """Planted 2-cycle must yield exactly one SCC of length 2; acyclic twin silent."""
    cycle_files = [FIXTURE / "fixture_mod_a.py", FIXTURE / "fixture_mod_b.py"]
    ok_files = [FIXTURE / "fixture_ok_a.py", FIXTURE / "fixture_ok_b.py"]
    missing = [str(p) for p in cycle_files + ok_files if not p.is_file()]
    if missing:
        return {
            "pass": False,
            "error": "fixture-missing",
            "missing": missing,
        }
    be, _, _ = build_graph(cycle_files, REPO)
    ge, _, _ = build_graph(ok_files, REPO)
    bad_cycles = tarjan(sorted(be), be)
    good_cycles = tarjan(sorted(ge), ge)
    fires = len(bad_cycles) == 1 and len(bad_cycles[0]) == 2
    silent = len(good_cycles) == 0
    payload = {
        "pass": bool(fires and silent),
        "fires_on_planted_cycle": fires,
        "silent_on_acyclic_twin": silent,
        "cycle_fixture_edges": be,
        "cycles_found": bad_cycles,
        "acyclic_fixture_edges": ge,
        "cycles_found_acyclic": good_cycles,
    }
    (HERE / "control-scc.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def scan_tools() -> dict[str, Any]:
    files = iter_py_files(TOOLS)
    libdir = TOOLS / "lib"
    lib_py = iter_py_files(libdir) if libdir.is_dir() else []
    edges, fanin, unresolved = build_graph(files, REPO)
    cycles = tarjan(sorted(edges), edges)
    top_fanin = sorted(fanin.items(), key=lambda kv: (-kv[1], kv[0]))[:25]
    n_edges = sum(len(v) for v in edges.values())
    return {
        "files_scanned": len(files),
        "module_count": len(edges),
        "edge_count": n_edges,
        "cycle_count": len(cycles),
        "cycles": cycles,
        "edges": edges,
        "fan_in": fanin,
        "top_fan_in": [{"module": m, "fan_in": n} for m, n in top_fanin],
        "unresolved_external": dict(
            sorted(unresolved.items(), key=lambda kv: (-kv[1], kv[0]))[:40]
        ),
        "tools_lib_exists": libdir.is_dir(),
        "tools_lib_py_count": len(lib_py),
        "tools_lib_modules": [modname(p, REPO) for p in lib_py],
    }
