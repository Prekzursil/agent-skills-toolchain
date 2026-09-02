#!/usr/bin/env python3
"""Extract called names/attrs from shard-19 failing probe files."""
from __future__ import annotations

import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
FAIL = [
    "ADV-0020",
    "ADV-0105",
    "ADV-0128",
    "ARC-0021",
    "ARC-0032",
    "AUD-0006",
    "AUD-0037",
    "AUD-0068",
    "BLD-0009",
    "BLD-0047",
    "CC-0016",
    "CNF-0037",
    "CNF-0085",
    "CNF-0132",
    "CNF-0171",
    "CNL-0098",
    "IMP-0008",
    "IMP-0033",
    "IMP-0080",
    "IMP-0107",
    "IMP-0115",
    "IMP-0155",
    "IMP-0194",
    "IMP-0216",
    "IMP-0248",
    "IMP-0274",
    "IMP-0300",
    "IMP-0320",
    "IMP-0348",
    "IMP-0369",
    "IMP-0406",
    "IMP-0469",
    "RES-0064",
    "RES-0132",
    "RES-0163",
    "RES-0193",
    "SYN-0040",
    "TST-0032",
    "TST-0073",
    "TST-0116",
    "TST-0151",
    "TST-0178",
    "TST-0244",
    "TST-0275",
    "TST-0302",
    "TST-0335",
    "WFA-0055",
    "WFA-0099",
]


def walk(uid: str) -> dict:
    pdir = PROBES / uid
    files = []
    for p in sorted(pdir.glob("*.py")):
        text = p.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            files.append({"file": p.name, "syntax": str(exc)})
            continue
        imports: list[str] = []
        froms: list[str] = []
        calls: list[str] = []
        attrs: list[str] = []
        fails: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imports.append(a.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for a in node.names:
                    froms.append(f"{mod}:{a.name}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.append(ast.unparse(node.func) if hasattr(ast, "unparse") else node.func.attr)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                attrs.append(f"{node.value.id}.{node.attr}")
        for ln in text.splitlines():
            if "FAILED:" in ln or "SUCCESS:" in ln:
                fails.append(ln.strip()[:220])
        files.append(
            {
                "file": p.name,
                "imports": sorted(set(imports)),
                "froms": sorted(set(froms)),
                "calls": sorted(set(calls))[:80],
                "attrs": sorted(set(attrs))[:80],
                "markers": fails[:30],
            }
        )
    return {"id": uid, "files": files}


def main() -> None:
    rows = [walk(uid) for uid in FAIL]
    dest = HERE / "_shard19_api.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("wrote", dest, "n", len(rows))
    for r in rows:
        froms = []
        for f in r["files"]:
            froms.extend(f.get("froms") or [])
        interesting = [x for x in sorted(set(froms)) if not x.startswith(("os", "sys", "json", "pathlib", "typing", "hashlib", "datetime", "tempfile", "subprocess", "unittest", "re:", "copy:", "io:", "tarfile", "shutil", "ast:", "importlib"))]
        print(r["id"], interesting[:12])


if __name__ == "__main__":
    main()
