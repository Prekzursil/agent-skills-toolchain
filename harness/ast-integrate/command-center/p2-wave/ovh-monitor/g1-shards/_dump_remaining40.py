#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "class-probe-missing.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
][12:]


def usage(tree: ast.AST) -> dict:
    imports: list[str] = []
    names: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                imports.append(f"{mod}:{a.name}")
                names.setdefault(mod.split(".")[-1] if mod else "_", set()).add(a.name)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            names.setdefault(node.value.id, set()).add(node.attr)
    return {
        "imports": imports,
        "attrs": {k: sorted(v) for k, v in names.items()},
    }


def main() -> None:
    rows = []
    dump_lines: list[str] = []
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        rec = {"id": uid, "files": []}
        dump_lines.append("=" * 78)
        dump_lines.append(uid)
        for p in sorted(pdir.glob("*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(text)
                u = usage(tree)
            except SyntaxError:
                u = {"imports": [], "attrs": {}, "syntax": True}
            rec["files"].append({"name": p.name, "bytes": len(text), **u})
            if p.name.startswith("probe") or p.name in {"scenario.py", "emit_receipt.py", "emit.py", "load.py"}:
                dump_lines.append(f"--- {p.name} ---")
                dump_lines.extend(text.splitlines()[:100])
                dump_lines.append("")
        rows.append(rec)
    out = WAVE / "ovh-monitor" / "g1-shards" / "_remaining40_api.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    txt = WAVE / "ovh-monitor" / "g1-shards" / "_remaining40_probes.txt"
    txt.write_text("\n".join(dump_lines) + "\n", encoding="utf-8")
    print("wrote", out, "and", txt, "n=", len(rows))


if __name__ == "__main__":
    main()
