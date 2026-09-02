#!/usr/bin/env python3
"""Compact dump for shard-23 (Windows-safe, no G-1 measure)."""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-23.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT.get("work_units") or []}
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_.]+)", re.M)
ASSERT_RE = re.compile(r"^\s*assert .+$", re.M)
STDLIB = {
    "os", "sys", "json", "pathlib", "re", "hashlib", "typing", "unittest",
    "pytest", "tempfile", "subprocess", "collections", "datetime", "functools",
    "itertools", "io", "copy", "math", "enum", "abc", "dataclasses", "argparse",
    "shutil", "textwrap", "inspect", "ast", "types", "contextlib", "warnings",
    "logging", "traceback", "glob", "fnmatch", "base64", "uuid", "time",
    "struct", "zlib", "gzip", "tarfile", "zipfile", "csv", "xml", "html",
    "http", "urllib", "ssl", "socket", "threading", "multiprocessing",
    "concurrent", "asyncio", "sqlite3", "decimal", "random", "string",
    "pprint", "difflib", "hmac", "secrets", "platform", "stat", "errno",
    "signal", "ctypes", "msvcrt", "winreg", "typing_extensions",
}


def digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def module_hits(mod: str) -> list[str]:
    root = mod.split(".")[0]
    if root in STDLIB:
        return ["stdlib"]
    parts = mod.split(".")
    cands = [
        REPO.joinpath(*parts).with_suffix(".py"),
        REPO.joinpath(*parts) / "__init__.py",
        (REPO / "tools").joinpath(*parts).with_suffix(".py"),
        (REPO / "tools").joinpath(*parts) / "__init__.py",
        (REPO / "tools" / "agentspec").joinpath(*parts).with_suffix(".py"),
        (REPO / "platform" / "lib").joinpath(*parts).with_suffix(".py"),
        (REPO / "command-center").joinpath(*parts).with_suffix(".py"),
        (REPO / "command-center").joinpath(*parts) / "__init__.py",
    ]
    hits = []
    for p in cands:
        if p.is_file():
            hits.append(str(p.relative_to(REPO)).replace("\\", "/"))
    return hits


def brief(uid: str) -> dict:
    u = BY.get(uid) or {}
    pdir = WAVE / "probes" / uid
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel if out_rel else None
    py_files = sorted(p.name for p in pdir.glob("*.py")) if pdir.is_dir() else []
    imports: list[str] = []
    asserts: list[str] = []
    probe_tails: dict[str, list[str]] = {}
    syntax: dict[str, str] = {}
    if pdir.is_dir():
        for p in sorted(pdir.glob("probe*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            try:
                ast.parse(text)
            except SyntaxError as exc:
                syntax[p.name] = str(exc)
            imports.extend(IMPORT_RE.findall(text))
            asserts.extend(m.group(0).strip() for m in ASSERT_RE.finditer(text))
            probe_tails[p.name] = lines[-22:]
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
    live_sha = digest(out) if out and out.is_file() else ""
    sha_match = False
    man_row = False
    if isinstance(man_doc, dict):
        for a in man_doc.get("artifacts") or []:
            if isinstance(a, dict) and a.get("unit_id") == uid:
                man_row = True
                if (
                    str(a.get("path") or "").replace("\\", "/") == out_rel
                    and str(a.get("sha256") or "") == live_sha
                    and a.get("present") is True
                ):
                    sha_match = True
    art_state = None
    art_sentinel_ok = None
    if out and out.is_file():
        try:
            text = out.read_text(encoding="utf-8")
            doc = json.loads(text)
            if isinstance(doc, dict):
                art_state = doc.get("state") or doc.get("status")
            sent = str(u.get("completion_sentinel") or "")
            art_sentinel_ok = bool(sent) and sent in text
        except Exception as exc:
            art_state = f"ERR:{type(exc).__name__}"
    miss = []
    for m in sorted(set(imports)):
        hits = module_hits(m)
        if not hits:
            miss.append(m)
    return {
        "id": uid,
        "title": u.get("title") or u.get("name") or "",
        "in_catalog": uid in BY,
        "output_path": out_rel,
        "output_exists": bool(out and out.is_file()),
        "output_bytes": out.stat().st_size if out and out.is_file() else 0,
        "art_state": art_state,
        "art_sentinel_ok": art_sentinel_ok,
        "probe_dir": pdir.is_dir(),
        "py_files": py_files,
        "imports": sorted(set(imports)),
        "miss": miss,
        "asserts": asserts[:40],
        "has_return": ret.is_file(),
        "has_manifest": man.is_file(),
        "return_status": (
            (ret_doc or {}).get("status") or (ret_doc or {}).get("state")
            if isinstance(ret_doc, dict)
            else None
        ),
        "named_cmds": len(cmds),
        "man_row": man_row,
        "sha_match": sha_match,
        "syntax": syntax,
        "probe_tails": probe_tails,
        "sentinel": u.get("completion_sentinel"),
    }


def main() -> None:
    rows = [brief(uid) for uid in IDS]
    dest = HERE / "_shard23_dump.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {dest} n={len(rows)}")
    for r in rows:
        miss = [m for m in (r.get("miss") or []) if m != "__future__"]
        print(
            f"{r['id']} cat={r['in_catalog']} out={r['output_exists']} "
            f"b={r['output_bytes']} py={len(r['py_files'])} ret={r['has_return']} "
            f"man={r['has_manifest']} st={r['return_status']} art={r['art_state']} "
            f"sent={r['art_sentinel_ok']} sha={r['sha_match']} miss={miss[:6]} "
            f"nA={len(r['asserts'])}"
        )


if __name__ == "__main__":
    main()
