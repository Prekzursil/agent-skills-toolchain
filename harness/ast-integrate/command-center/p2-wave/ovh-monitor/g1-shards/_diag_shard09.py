#!/usr/bin/env python3
"""Dump shard-09 unit state: probes, imports, artifacts, missing modules."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-09.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]


def last_asserts(text: str, n: int = 30) -> list[str]:
    lines = text.splitlines()
    hits = [
        f"{i}:{ln.strip()}"
        for i, ln in enumerate(lines, 1)
        if "assert " in ln or ln.strip().startswith("raise ") or "FAILED:" in ln
    ]
    return hits[-n:] if hits else []


def imports_of(text: str) -> dict:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"syntax_error": str(exc)}
    froms: list[str] = []
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                froms.append(node.module)
                for a in node.names:
                    froms.append(f"{node.module}:{a.name}")
    return {"froms": sorted(set(froms)), "mods": sorted(set(mods))}


def resolve_mod(name: str) -> dict:
    root = name.split(":")[0]
    parts = root.split(".")
    py = REPO.joinpath(*parts).with_suffix(".py")
    pkg = REPO.joinpath(*parts) / "__init__.py"
    tools_py = REPO.joinpath("tools", *parts).with_suffix(".py")
    tools_pkg = REPO.joinpath("tools", *parts) / "__init__.py"
    plat_py = REPO.joinpath("platform", "lib", *parts).with_suffix(".py")
    hits = []
    for p in (py, pkg, tools_py, tools_pkg, plat_py):
        if p.is_file():
            hits.append(str(p.relative_to(REPO)).replace("\\", "/"))
    return {"name": root, "hits": hits, "missing": not hits}


def digest_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    rows = []
    missing_mods: dict[str, list[str]] = {}
    for uid in IDS:
        u = BY.get(uid) or {}
        pdir = WAVE / "probes" / uid
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        rec: dict = {
            "id": uid,
            "title": (u.get("title") or u.get("name") or "")[:180],
            "output_path": out_rel,
            "catalog_present": bool(u),
            "artifact_exists": bool(out and out.is_file() and out.stat().st_size > 0),
            "artifact_bytes": (out.stat().st_size if out and out.is_file() else 0),
            "probe_dir": pdir.is_dir(),
            "probe_files": [],
            "helpers": [],
            "missing_named": [],
            "imports_missing": [],
        }
        if pdir.is_dir():
            rec["probe_files"] = sorted(p.name for p in pdir.glob("probe*.py"))
            rec["helpers"] = sorted(
                p.name
                for p in pdir.iterdir()
                if p.suffix == ".py" and not p.name.startswith("probe")
            )
            rec["all_files"] = sorted(p.name for p in pdir.iterdir() if p.is_file())[:50]
            retp = pdir / "SUBAGENT-RETURN.json"
            manp = pdir / "UNIT-ARTIFACT-MANIFEST.json"
            rec["has_return"] = retp.is_file()
            rec["has_manifest"] = manp.is_file()
            named_cmds = []
            if retp.is_file():
                try:
                    ret = json.loads(retp.read_text(encoding="utf-8"))
                    rec["ret_status"] = ret.get("status") or ret.get("state")
                    for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
                        if isinstance(item, dict) and isinstance(item.get("command"), str):
                            named_cmds.append(item["command"])
                except Exception as exc:
                    rec["ret"] = f"unparseable:{exc}"
            rec["named_cmds"] = named_cmds
            for cmd in named_cmds:
                for tok in cmd.split():
                    t = tok.replace("\\", "/")
                    if t.endswith(".py") and "probes/" in t:
                        if not (REPO / t).is_file():
                            rec["missing_named"].append(t)
            if manp.is_file() and out and out.is_file():
                try:
                    man = json.loads(manp.read_text(encoding="utf-8"))
                    live = digest_file(out)
                    rows_m = [
                        a
                        for a in (man.get("artifacts") or [])
                        if isinstance(a, dict) and a.get("unit_id") == uid
                    ]
                    rec["man_rows"] = len(rows_m)
                    rec["live_sha"] = live
                    rec["man_sha_match"] = any(
                        str(a.get("sha256") or "") == live
                        and str(a.get("path") or "").replace("\\", "/") == out_rel
                        for a in rows_m
                    )
                except Exception as exc:
                    rec["man_err"] = str(exc)
            rec["probe_detail"] = {}
            all_froms: set[str] = set()
            for p in sorted(pdir.glob("*.py")):
                text = p.read_text(encoding="utf-8", errors="replace")
                im = imports_of(text)
                rec["probe_detail"][p.name] = {
                    "bytes": len(text),
                    "lines": text.count("\n") + 1,
                    "asserts": last_asserts(text, 25),
                    "imports": im,
                }
                for f in im.get("froms") or []:
                    all_froms.add(f.split(":")[0])
                for m in im.get("mods") or []:
                    all_froms.add(m)
            local_names = {p.stem for p in pdir.glob("*.py")}
            for name in sorted(all_froms):
                if name in {"json", "sys", "os", "re", "hashlib", "pathlib", "typing", "dataclasses",
                            "enum", "collections", "subprocess", "tempfile", "shutil", "copy",
                            "itertools", "functools", "datetime", "time", "math", "io", "ast",
                            "importlib", "runpy", "traceback", "textwrap", "unicodedata", "base64",
                            "struct", "gzip", "zipfile", "tarfile", "csv", "argparse", "unittest",
                            "pytest", "jsonschema", "yaml", "tomllib", "configparser", "http",
                            "urllib", "ssl", "socket", "threading", "concurrent", "multiprocessing",
                            "contextlib", "weakref", "types", "inspect", "pkgutil", "glob", "fnmatch",
                            "stat", "errno", "signal", "platform", "secrets", "hmac", "uuid",
                            "decimal", "fractions", "random", "string", "pprint", "difflib",
                            "html", "xml", "email", "logging", "warnings", "abc", "typing_extensions",
                            "pytest", "jsonschema"}:
                    continue
                if name.split(".")[0] in local_names:
                    continue
                info = resolve_mod(name)
                if info["missing"]:
                    rec["imports_missing"].append(name)
                    missing_mods.setdefault(name, []).append(uid)
        rows.append(rec)
    outp = WAVE / "ovh-monitor" / "g1-shards" / "_shard09_diag.json"
    payload = {"n": len(rows), "missing_mods": missing_mods, "rows": rows}
    outp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {outp} n={len(rows)}")
    print("missing_named", sum(len(r.get("missing_named") or []) for r in rows))
    print("imports_missing", json.dumps({k: v for k, v in missing_mods.items()}, indent=2)[:4000])
    print("no_probe_files", [r["id"] for r in rows if not r.get("probe_files")])
    print("artifact_missing", [r["id"] for r in rows if not r.get("artifact_exists")])
    print("sha_mismatch", [r["id"] for r in rows if r.get("artifact_exists") and r.get("man_sha_match") is False])


if __name__ == "__main__":
    main()
