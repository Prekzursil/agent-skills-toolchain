#!/usr/bin/env python3
"""Blast-radius index for the shared-module (``_NS`` placeholder) class.

For every probe under probes/<ID>/ parse its imports with the stdlib ``ast``
(loaded from the stdlib path explicitly, because tools/ast.py shadows it on
PYTHONPATH) and resolve each dotted name against the roots the measurement puts
on PYTHONPATH (repo, tools/, platform/lib, tools/agentspec, seed-stage). A module
is a placeholder when its file carries ``# g1-surface: generated``.

Output (JSON, stdout or file):
  modules: {dotted: {"path": rel, "units_ok": [...], "units_fail": [...]}}
  units:   {ID: {"ok": bool, "placeholders": [dotted...]}}
  summary: counts (placeholder files, imported placeholders, units touching one, split)

Usage: python3 _g1_blast_radius.py [out.json]   (read-only; 02.09 cloud tool)
"""
from __future__ import annotations

import importlib.util
import json
import sys
import sysconfig
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _g1_paths import ROOT, latest_rows  # noqa: E402

MARKER = "# g1-surface: generated"
PROBES = ROOT / "command-center" / "p2-wave" / "probes"
ROOTS = [ROOT, ROOT / "tools", ROOT / "platform" / "lib", ROOT / "tools" / "agentspec", HERE]


def _stdlib_ast():
    stdlib = Path(sysconfig.get_path("stdlib"))
    path = stdlib / "ast.py"
    if not path.is_file():
        path = stdlib / "ast" / "__init__.py"
    spec = importlib.util.spec_from_file_location("_g1_stdlib_ast", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AST = _stdlib_ast()


def is_placeholder(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(600)
    except OSError:
        return False
    return MARKER in head


def resolve(dotted: str) -> Path | None:
    rel = Path(*dotted.split("."))
    for root in ROOTS:
        cand = root / rel
        if (cand / "__init__.py").is_file():
            return cand / "__init__.py"
        if Path(str(cand) + ".py").is_file():
            return Path(str(cand) + ".py")
    return None


def probe_imports(path: Path) -> set[str]:
    try:
        tree = AST.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return set()
    names: set[str] = set()
    for node in AST.walk(tree):
        if isinstance(node, AST.Import):
            for a in node.names:
                names.add(a.name)
        elif isinstance(node, AST.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            for a in node.names:
                if a.name != "*":
                    names.add(f"{node.module}.{a.name}")
    return names


def main() -> int:
    rows = latest_rows()
    cache: dict[str, Path | None] = {}
    modules: dict[str, dict] = defaultdict(lambda: {"path": "", "units_ok": set(), "units_fail": set()})
    units: dict[str, dict] = {}
    for probe_dir in sorted(p for p in PROBES.iterdir() if p.is_dir()):
        uid = probe_dir.name
        ok = bool((rows.get(uid) or {}).get("ok"))
        found: set[str] = set()
        for py in probe_dir.rglob("*.py"):
            for dotted in probe_imports(py):
                if dotted not in cache:
                    target = resolve(dotted)
                    cache[dotted] = target if (target and is_placeholder(target)) else None
                target = cache[dotted]
                if target is not None:
                    found.add(dotted)
                    modules[dotted]["path"] = target.relative_to(ROOT).as_posix()
                    modules[dotted]["units_ok" if ok else "units_fail"].add(uid)
        units[uid] = {"ok": ok, "placeholders": sorted(found)}
    touching = {u for u, d in units.items() if d["placeholders"]}
    out = {
        "summary": {
            "placeholder_modules_imported": len(modules),
            "units_touching_placeholder": len(touching),
            "units_touching_ok": sum(1 for u in touching if units[u]["ok"]),
            "units_touching_fail": sum(1 for u in touching if not units[u]["ok"]),
            "fails_total": sum(1 for d in units.values() if not d["ok"]),
        },
        "modules": {
            k: {"path": v["path"], "units_ok": sorted(v["units_ok"]), "units_fail": sorted(v["units_fail"])}
            for k, v in sorted(modules.items(), key=lambda kv: -(len(kv[1]["units_ok"]) + len(kv[1]["units_fail"])))
        },
        "units": {u: units[u] for u in sorted(touching)},
    }
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    print(json.dumps(out["summary"]))
    for k, v in list(out["modules"].items())[:40]:
        print(f"{len(v['units_ok']):4d} ok {len(v['units_fail']):4d} fail  {k}  ({v['path']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
