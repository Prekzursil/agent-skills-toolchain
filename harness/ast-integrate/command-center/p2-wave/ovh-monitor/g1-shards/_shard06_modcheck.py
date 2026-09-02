#!/usr/bin/env python3
"""Locate imported modules and report missing names for shard-06 IDs."""
from __future__ import annotations

import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DUMP = json.loads((HERE / "_shard06_dump.json").read_text(encoding="utf-8"))

CANDIDATE_ROOTS = [
    REPO / "tools",
    REPO / "tools" / "plugin",
    REPO / "tools" / "marketplace",
    REPO / "tools" / "agentspec",
    REPO / "tools" / "council",
    REPO / "tools" / "lib",
    REPO / "command-center",
    REPO / "platform" / "lib",
]


def resolve_mod(mod: str, probe_dir: Path) -> Path | None:
    rel = Path(*mod.split("."))
    local = probe_dir / (rel.as_posix() + ".py")
    if local.is_file():
        return local
    local_pkg = probe_dir / rel / "__init__.py"
    if local_pkg.is_file():
        return local_pkg
    for root in [REPO, *CANDIDATE_ROOTS]:
        p = root / (rel.as_posix() + ".py")
        if p.is_file():
            return p
        p = root / rel / "__init__.py"
        if p.is_file():
            return p
    # tools.foo.bar already includes tools/
    p = REPO / (rel.as_posix() + ".py")
    if p.is_file():
        return p
    p = REPO / rel / "__init__.py"
    if p.is_file():
        return p
    return None


def defined_names(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                names.add(a.asname or a.name)
    return names


def main() -> None:
    rows = []
    for rec in DUMP:
        uid = rec["id"]
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        froms = rec.get("froms") or []
        attrs = rec.get("attrs") or {}
        mods = []
        for mod in froms:
            path = resolve_mod(mod, pdir)
            wanted = set(attrs.get(mod) or [])
            # also attrs under last component
            leaf = mod.split(".")[-1]
            wanted |= set(attrs.get(leaf) or [])
            defined = defined_names(path) if path else set()
            missing = sorted(wanted - defined) if wanted else []
            mods.append(
                {
                    "mod": mod,
                    "path": (str(path.relative_to(REPO)) if path else None),
                    "exists": bool(path),
                    "bytes": (path.stat().st_size if path else 0),
                    "wanted": sorted(wanted),
                    "missing": missing,
                    "defined_n": len(defined),
                }
            )
        rows.append({"id": uid, "mods": mods})
        miss_any = [m for m in mods if (not m["exists"]) or m["missing"]]
        if miss_any:
            print(uid)
            for m in miss_any:
                print(
                    f"  {m['mod']} exists={m['exists']} path={m['path']} "
                    f"missing={m['missing']} wanted={m['wanted'][:12]}"
                )
    out = HERE / "_shard06_modcheck.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
