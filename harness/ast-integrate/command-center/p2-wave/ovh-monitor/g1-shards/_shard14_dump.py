#!/usr/bin/env python3
"""Dump catalog + probe surface for shard-14 IDs (Windows-safe, no G-1 measure)."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-14.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT.get("work_units") or []}
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_.]+)", re.M)
ASSERT_RE = re.compile(r"^\s*assert .+$", re.M)
STDLIB = (
    "os", "sys", "json", "pathlib", "re", "hashlib", "typing", "unittest", "pytest",
    "tempfile", "subprocess", "collections", "datetime", "functools", "itertools",
    "io", "copy", "math", "enum", "abc", "dataclasses", "argparse", "shutil",
    "textwrap", "inspect", "ast", "types", "contextlib", "warnings", "logging",
    "traceback", "glob", "fnmatch", "base64", "uuid", "time", "struct", "zlib",
    "gzip", "tarfile", "zipfile", "csv", "xml", "html", "http", "urllib", "ssl",
    "socket", "threading", "multiprocessing", "concurrent", "asyncio", "sqlite3",
    "decimal", "random", "string", "pprint", "hmac", "secrets", "platform",
)


def module_hits(mod: str) -> list[str]:
    if not mod or mod.split(".")[0] in STDLIB:
        return []
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
        (REPO / "command-center" / "lib").joinpath(*parts).with_suffix(".py"),
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
    probes = []
    imports: list[str] = []
    asserts: list[str] = []
    if pdir.is_dir():
        for p in sorted(pdir.glob("probe*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            probes.append(
                {
                    "name": p.name,
                    "lines": len(lines),
                    "head": lines[:18],
                    "tail": lines[-35:] if len(lines) > 18 else lines,
                }
            )
            imports.extend(IMPORT_RE.findall(text))
            asserts.extend(m.group(0).strip() for m in list(ASSERT_RE.finditer(text))[:25])
    ret = pdir / "SUBAGENT-RETURN.json"
    man = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    ret_doc = None
    man_ok = man.is_file()
    cmds = []
    if ret.is_file():
        try:
            ret_doc = json.loads(ret.read_text(encoding="utf-8"))
        except Exception as exc:
            ret_doc = {"_err": type(exc).__name__}
        if isinstance(ret_doc, dict):
            for key in ("named_probes", "probes"):
                for item in ret_doc.get(key) or []:
                    if isinstance(item, dict) and item.get("command"):
                        cmds.append(item["command"])
    mods = {}
    for m in sorted(set(imports)):
        if m.split(".")[0] in STDLIB:
            continue
        mods[m] = module_hits(m)
    return {
        "id": uid,
        "in_catalog": uid in BY,
        "title": (u.get("title") or u.get("name") or "")[:180],
        "output_path": out_rel,
        "output_exists": bool(out and out.is_file()),
        "output_bytes": out.stat().st_size if out and out.is_file() else 0,
        "sentinel": (u.get("completion_sentinel") or "")[:200],
        "probe_dir": pdir.is_dir(),
        "py_files": py_files,
        "imports": sorted(set(imports)),
        "asserts": asserts[:30],
        "has_return": ret.is_file(),
        "has_manifest": man_ok,
        "return_status": (
            (ret_doc or {}).get("status") or (ret_doc or {}).get("state")
            if isinstance(ret_doc, dict)
            else None
        ),
        "named_cmds": cmds[:6],
        "modules": mods,
        "probes": probes,
    }


def main() -> None:
    rows = [brief(uid) for uid in IDS]
    dest = HERE / "_shard14_dump.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {dest} n={len(rows)}")
    missing_probe = [r["id"] for r in rows if not r["probe_dir"]]
    missing_out = [r["id"] for r in rows if not r["output_exists"]]
    missing_ret = [r["id"] for r in rows if not r["has_return"] or not r["has_manifest"]]
    no_mod = []
    for r in rows:
        empty = [k for k, v in r["modules"].items() if not v]
        if empty:
            no_mod.append({"id": r["id"], "missing": empty})
    print(f"missing_probe_dir={missing_probe}")
    print(f"missing_output={missing_out}")
    print(f"missing_ret_or_man={missing_ret}")
    print(f"modules_without_file={json.dumps(no_mod)}")


if __name__ == "__main__":
    main()
