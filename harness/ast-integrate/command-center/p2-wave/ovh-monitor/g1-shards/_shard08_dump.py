#!/usr/bin/env python3
"""Dump probe surface for shard-08 (Windows-safe, no G-1 measure)."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-08.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT.get("work_units") or []}
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_.]+)", re.M)
ASSERT_RE = re.compile(r"^\s*assert .+$", re.M)


def attrs_from(text: str) -> dict:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"syntax_error": str(exc)}
    names: dict[str, list[str]] = {}
    froms: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.setdefault(a.asname or a.name.split(".")[0], [])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            froms.append(mod)
            root = mod.split(".")[0] if mod else "."
            for a in node.names:
                names.setdefault(root, []).append(a.name)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            names.setdefault(node.value.id, []).append(node.attr)
    for k, v in list(names.items()):
        names[k] = sorted(set(v))
    return {"froms": sorted(set(froms)), "names": names}


def brief(uid: str) -> dict:
    u = BY.get(uid) or {}
    pdir = WAVE / "probes" / uid
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel if out_rel else None
    py_files = sorted(p.name for p in pdir.glob("*.py")) if pdir.is_dir() else []
    probes = []
    imports: list[str] = []
    asserts: list[str] = []
    if pdir.is_dir():
        for p in sorted(pdir.glob("probe*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            ast_info = attrs_from(text)
            probes.append(
                {
                    "name": p.name,
                    "bytes": len(text.encode("utf-8", errors="replace")),
                    "lines": len(lines),
                    "head": lines[:25],
                    "tail": lines[-30:] if len(lines) > 25 else lines,
                    "froms": ast_info.get("froms"),
                    "names": ast_info.get("names"),
                    "syntax_error": ast_info.get("syntax_error"),
                }
            )
            imports.extend(IMPORT_RE.findall(text))
            asserts.extend(m.group(0).strip() for m in ASSERT_RE.finditer(text))
    ret = pdir / "SUBAGENT-RETURN.json"
    man = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    ret_doc = None
    man_doc = None
    if ret.is_file():
        try:
            ret_doc = json.loads(ret.read_text(encoding="utf-8"))
        except Exception as exc:
            ret_doc = {"_err": type(exc).__name__}
    if man.is_file():
        try:
            man_doc = json.loads(man.read_text(encoding="utf-8"))
        except Exception as exc:
            man_doc = {"_err": type(exc).__name__}
    cmds = []
    if isinstance(ret_doc, dict):
        for key in ("named_probes", "probes"):
            for item in ret_doc.get(key) or []:
                if isinstance(item, dict) and item.get("command"):
                    cmds.append(item["command"])
    return {
        "id": uid,
        "title": (u.get("title") or u.get("name") or "")[:220],
        "output_path": out_rel,
        "output_exists": bool(out and out.is_file()),
        "output_bytes": out.stat().st_size if out and out.is_file() else 0,
        "sentinel": (u.get("completion_sentinel") or "")[:280],
        "probe_dir": pdir.is_dir(),
        "py_files": py_files,
        "probe_count": len(probes),
        "probes": probes,
        "imports": sorted(set(imports)),
        "asserts": asserts[-24:],
        "has_return": ret.is_file(),
        "has_manifest": man.is_file(),
        "return_status": (
            (ret_doc or {}).get("status") or (ret_doc or {}).get("state")
            if isinstance(ret_doc, dict)
            else None
        ),
        "named_cmds": cmds[:8],
    }


def main() -> None:
    rows = [brief(uid) for uid in IDS]
    out = HERE / "_shard08_dump.json"
    slim = []
    for r in rows:
        slim.append(
            {
                "id": r["id"],
                "title": r["title"],
                "output_path": r["output_path"],
                "output_bytes": r["output_bytes"],
                "sentinel": r["sentinel"],
                "py_files": r["py_files"],
                "imports": r["imports"],
                "asserts": r["asserts"],
                "return_status": r["return_status"],
                "named_cmds": r["named_cmds"],
                "probes": [
                    {
                        "name": p["name"],
                        "lines": p["lines"],
                        "froms": p["froms"],
                        "names": {k: v[:20] for k, v in (p.get("names") or {}).items()},
                        "tail": p["tail"][-18:],
                    }
                    for p in r["probes"]
                ],
            }
        )
    out.write_text(json.dumps({"n": len(slim), "rows": slim}, indent=2), encoding="utf-8")
    print(f"wrote {out} n={len(slim)}")
    for r in slim:
        print(f"{r['id']}\t{r['return_status']}\t{len(r['probes'])}p\t{r['title'][:70]}")


if __name__ == "__main__":
    main()
