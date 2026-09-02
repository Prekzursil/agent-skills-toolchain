#!/usr/bin/env python3
"""Dump catalog + probe surface for shard-18 IDs (Windows-safe, no G-1 measure)."""
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
    for ln in (HERE / "shard-18.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT.get("work_units") or []}
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_.]+)", re.M)
ASSERT_RE = re.compile(r"^\s*assert .+$", re.M)
FAIL_RE = re.compile(r"fail\(|FAILED:|raise AssertionError|sys\.exit\(1\)")
STUB_MARKERS = ("# g1-surface: generated", "# g1-mod: real-surface", "class _NS:")


def digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


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
                names.setdefault(root if not mod else mod, []).append(a.name)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            names.setdefault(node.value.id, []).append(node.attr)
    for k, v in list(names.items()):
        names[k] = sorted(set(v))[:40]
    return {"froms": sorted(set(froms)), "names": names}


def module_exists(mod: str) -> dict:
    if not mod or mod.startswith(("os", "sys", "json", "pathlib", "re", "hashlib", "typing", "unittest", "pytest", "tempfile", "subprocess", "collections", "datetime", "functools", "itertools", "io", "copy", "math", "enum", "abc", "dataclasses", "argparse", "shutil", "textwrap", "inspect", "ast", "types", "contextlib", "warnings", "logging", "traceback", "glob", "fnmatch", "base64", "uuid", "time", "struct", "zlib", "gzip", "tarfile", "zipfile", "csv", "xml", "html", "http", "urllib", "ssl", "socket", "threading", "multiprocessing", "concurrent", "asyncio", "sqlite3", "decimal", "fractions", "statistics", "random", "string", "pprint", "difflib", "hmac", "secrets", "platform", "ntpath", "posixpath", "stat", "errno", "signal", "ctypes", "msvcrt", "winreg")):
        return {"skip": True}
    parts = mod.split(".")
    cands = [
        REPO.joinpath(*parts).with_suffix(".py"),
        REPO.joinpath(*parts) / "__init__.py",
        (REPO / "tools").joinpath(*parts).with_suffix(".py"),
        (REPO / "tools").joinpath(*parts) / "__init__.py",
        (REPO / "tools" / "agentspec").joinpath(*parts).with_suffix(".py"),
        (REPO / "tools" / "agentspec").joinpath(*parts) / "__init__.py",
        (REPO / "platform" / "lib").joinpath(*parts).with_suffix(".py"),
        (REPO / "command-center").joinpath(*parts).with_suffix(".py"),
        (REPO / "command-center").joinpath(*parts) / "__init__.py",
    ]
    hits = []
    for p in cands:
        if p.is_file():
            head = p.read_text(encoding="utf-8", errors="replace")[:800]
            stub = any(m in head for m in STUB_MARKERS)
            hits.append({"path": str(p.relative_to(REPO)).replace("\\", "/"), "bytes": p.stat().st_size, "stub": stub})
    return {"hits": hits}


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
                    "head": lines[:20],
                    "tail": lines[-30:] if len(lines) > 20 else lines,
                    "froms": ast_info.get("froms"),
                    "names": ast_info.get("names"),
                    "syntax_error": ast_info.get("syntax_error"),
                    "fail_hits": FAIL_RE.findall(text)[:12],
                    "asserts": [m.group(0).strip() for m in ASSERT_RE.finditer(text)][:30],
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
    live_sha = digest(out) if out and out.is_file() else ""
    man_rows = []
    if isinstance(man_doc, dict):
        for a in man_doc.get("artifacts") or []:
            if isinstance(a, dict) and a.get("unit_id") == uid:
                man_rows.append(
                    {
                        "path": a.get("path"),
                        "sha256": str(a.get("sha256") or "")[:16],
                        "present": a.get("present"),
                        "bytes": a.get("bytes"),
                        "sha_match": str(a.get("sha256") or "") == live_sha,
                    }
                )
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
    mod_map = {}
    for m in sorted(set(imports)):
        info = module_exists(m)
        if not info.get("skip"):
            mod_map[m] = info
    return {
        "id": uid,
        "in_catalog": uid in BY,
        "title": (u.get("title") or u.get("name") or "")[:220],
        "output_path": out_rel,
        "output_exists": bool(out and out.is_file()),
        "output_bytes": out.stat().st_size if out and out.is_file() else 0,
        "live_sha16": live_sha[:16],
        "art_state": art_state,
        "art_sentinel_ok": art_sentinel_ok,
        "sentinel": (u.get("completion_sentinel") or "")[:280],
        "probe_dir": pdir.is_dir(),
        "py_files": py_files,
        "probe_count": len(probes),
        "probes": probes,
        "imports": sorted(set(imports)),
        "asserts": asserts[:40],
        "has_return": ret.is_file(),
        "has_manifest": man.is_file(),
        "return_status": (
            (ret_doc or {}).get("status") or (ret_doc or {}).get("state")
            if isinstance(ret_doc, dict)
            else None
        ),
        "named_cmds": cmds[:8],
        "manifest_rows": man_rows[:4],
        "modules": mod_map,
    }


def main() -> None:
    rows = [brief(uid) for uid in IDS]
    out = HERE / "_shard18_dump.json"
    slim = []
    for r in rows:
        slim.append(
            {
                "id": r["id"],
                "in_catalog": r["in_catalog"],
                "title": r["title"],
                "output_path": r["output_path"],
                "output_exists": r["output_exists"],
                "output_bytes": r["output_bytes"],
                "art_state": r["art_state"],
                "art_sentinel_ok": r["art_sentinel_ok"],
                "sentinel": r["sentinel"],
                "probe_dir": r["probe_dir"],
                "py_files": r["py_files"],
                "imports": r["imports"],
                "asserts": r["asserts"],
                "has_return": r["has_return"],
                "has_manifest": r["has_manifest"],
                "return_status": r["return_status"],
                "named_cmds": r["named_cmds"],
                "manifest_rows": r["manifest_rows"],
                "modules": r["modules"],
                "probe_froms": {p["name"]: p.get("froms") for p in r["probes"]},
                "probe_names": {p["name"]: p.get("names") for p in r["probes"]},
                "probe_heads": {p["name"]: p["head"] for p in r["probes"]},
                "probe_tails": {p["name"]: p["tail"] for p in r["probes"]},
                "probe_asserts": {p["name"]: p.get("asserts") for p in r["probes"]},
            }
        )
    out.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    print(f"wrote {out} n={len(slim)}")
    for r in slim:
        miss = [k for k, v in r["modules"].items() if not v.get("hits")]
        print(
            f"{r['id']} cat={r['in_catalog']} out={r['output_exists']} bytes={r['output_bytes']} "
            f"py={len(r['py_files'])} ret={r['has_return']} man={r['has_manifest']} "
            f"st={r['return_status']} sent={r['art_sentinel_ok']} miss={miss[:6]}"
        )


if __name__ == "__main__":
    main()
