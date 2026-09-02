#!/usr/bin/env python3
"""Dump catalog + probe surface for current shard-06 IDs (Windows-safe)."""
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
    for ln in (HERE / "shard-06.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT.get("work_units") or []}
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_.]+)", re.M)
SKIP = {
    "__future__", "json", "sys", "os", "pathlib", "subprocess", "tempfile",
    "unittest", "hashlib", "re", "ast", "copy", "inspect", "shutil",
    "datetime", "typing", "dataclasses", "enum", "collections", "io",
    "argparse", "textwrap", "functools", "itertools", "uuid", "math",
    "struct", "base64", "gzip", "zipfile", "tarfile", "csv", "configparser",
    "fnmatch", "glob", "traceback", "logging", "time", "random", "string",
    "contextlib", "abc", "weakref", "types", "operator", "heapq", "pprint",
    "stat", "errno", "signal", "threading", "concurrent", "multiprocessing",
    "platform", "socket", "ssl", "urllib", "http", "email", "jsonschema",
    "referencing", "pytest", "unittest",
}


def last_asserts(text: str, n: int = 30) -> list[str]:
    lines = text.splitlines()
    hits = [
        f"{i}:{ln}"
        for i, ln in enumerate(lines, 1)
        if "assert " in ln or ln.strip().startswith("raise ") or "FAILED:" in ln
    ]
    if hits:
        return hits[-n:]
    return [f"{i}:{ln}" for i, ln in enumerate(lines[-n:], max(1, len(lines) - n + 1))]


def imports_and_attrs(text: str) -> dict:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"syntax_error": str(exc), "froms": [], "names": {}}
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
                names.setdefault(mod or ".", []).append(a.name)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            names.setdefault(node.value.id, []).append(node.attr)
    for k, v in list(names.items()):
        names[k] = sorted(set(v))
    froms_u = sorted({f for f in froms if f and f.split(".")[0] not in SKIP})
    return {"froms": froms_u, "names": names}


def named_py(ret: dict) -> list[str]:
    out: list[str] = []
    for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
        if not isinstance(item, dict):
            continue
        cmd = item.get("command")
        if not isinstance(cmd, str):
            continue
        for tok in cmd.split():
            t = tok.replace("\\", "/")
            if t.endswith(".py"):
                out.append(t)
    return out


def brief(uid: str) -> dict:
    u = BY.get(uid) or {}
    pdir = WAVE / "probes" / uid
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel if out_rel else None
    rec: dict = {
        "id": uid,
        "title": (u.get("title") or u.get("name") or "")[:200],
        "output_path": out_rel,
        "output_exists": bool(out and out.is_file() and out.stat().st_size > 0),
        "output_bytes": out.stat().st_size if out and out.is_file() else 0,
        "sentinel": (u.get("completion_sentinel") or "")[:240],
        "catalog_present": bool(u),
        "probe_dir": pdir.is_dir(),
        "py_files": [],
        "froms": [],
        "attrs": {},
        "assert_tails": {},
        "heads": {},
        "has_return": False,
        "has_manifest": False,
        "return_status": None,
        "named_cmds": [],
        "named_py": [],
        "missing_named_py": [],
        "manifest_rows": [],
    }
    if not pdir.is_dir():
        return rec
    rec["py_files"] = sorted(p.name for p in pdir.glob("*.py"))
    rec["all_files"] = sorted(p.name for p in pdir.iterdir() if p.is_file())[:50]
    retp = pdir / "SUBAGENT-RETURN.json"
    manp = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    rec["has_return"] = retp.is_file()
    rec["has_manifest"] = manp.is_file()
    ret_doc = None
    if retp.is_file():
        try:
            ret_doc = json.loads(retp.read_text(encoding="utf-8"))
        except Exception as exc:
            rec["return_status"] = f"unparseable:{type(exc).__name__}"
    if isinstance(ret_doc, dict):
        rec["return_status"] = ret_doc.get("status") or ret_doc.get("state")
        cmds = []
        for key in ("named_probes", "probes"):
            for item in ret_doc.get(key) or []:
                if isinstance(item, dict) and item.get("command"):
                    cmds.append(item["command"])
        rec["named_cmds"] = cmds[:8]
        rec["named_py"] = named_py(ret_doc)
        rec["missing_named_py"] = [p for p in rec["named_py"] if not (REPO / p).is_file()]
    if manp.is_file():
        try:
            man = json.loads(manp.read_text(encoding="utf-8"))
            for a in man.get("artifacts") or []:
                if isinstance(a, dict) and a.get("unit_id") == uid:
                    rec["manifest_rows"].append(
                        {
                            "path": a.get("path"),
                            "sha256": (a.get("sha256") or "")[:16],
                            "present": a.get("present"),
                            "bytes": a.get("bytes"),
                        }
                    )
        except Exception as exc:
            rec["man_err"] = type(exc).__name__
    all_froms: list[str] = []
    attrs: dict[str, list[str]] = {}
    for p in sorted(pdir.glob("*.py")):
        text = p.read_text(encoding="utf-8", errors="replace")
        rec["assert_tails"][p.name] = last_asserts(text, 20)
        rec["heads"][p.name] = text.splitlines()[:30]
        im = imports_and_attrs(text)
        all_froms.extend(im.get("froms") or [])
        for k, v in (im.get("names") or {}).items():
            if k.split(".")[0] in SKIP:
                continue
            attrs.setdefault(k, [])
            attrs[k].extend(v)
    rec["froms"] = sorted(set(all_froms))
    rec["attrs"] = {k: sorted(set(v)) for k, v in attrs.items() if v}
    return rec


def main() -> None:
    rows = [brief(uid) for uid in IDS]
    out = HERE / "_shard06_dump.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {out} n={len(rows)}")
    for r in rows:
        print(
            f"{r['id']:10} cat={int(r['catalog_present'])} out={int(r['output_exists'])} "
            f"B={r['output_bytes']:<7} py={len(r['py_files']):<2} ret={int(r['has_return'])} "
            f"man={int(r['has_manifest'])} miss={len(r['missing_named_py'])} "
            f"st={r['return_status']} froms={r['froms'][:6]}"
        )


if __name__ == "__main__":
    main()
