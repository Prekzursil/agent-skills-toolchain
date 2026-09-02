#!/usr/bin/env python3
"""Dump probe surface for shard-11 (Windows-safe, no G-1 measure)."""
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
    for ln in (HERE / "shard-11.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT.get("work_units") or []}
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z0-9_.]+)", re.M)
ASSERT_RE = re.compile(r"^\s*assert .+$", re.M)
FAIL_RE = re.compile(r"fail\(|FAILED:|raise AssertionError|sys\.exit\(1\)")


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
        names[k] = sorted(set(v))[:24]
    return {"froms": sorted(set(froms)), "names": names}


def digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


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
                    "head": lines[:16],
                    "tail": lines[-18:] if len(lines) > 16 else lines,
                    "froms": ast_info.get("froms"),
                    "names": ast_info.get("names"),
                    "syntax_error": ast_info.get("syntax_error"),
                    "fail_hits": FAIL_RE.findall(text)[:12],
                    "asserts": [m.group(0).strip() for m in ASSERT_RE.finditer(text)][:24],
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
    man_rows = []
    live_sha = digest(out) if out and out.is_file() else ""
    if isinstance(man_doc, dict):
        for a in man_doc.get("artifacts") or []:
            if isinstance(a, dict) and a.get("unit_id") == uid:
                man_rows.append(
                    {
                        "path": a.get("path"),
                        "sha256": str(a.get("sha256") or ""),
                        "present": a.get("present"),
                        "bytes": a.get("bytes"),
                        "sha_match": str(a.get("sha256") or "") == live_sha,
                    }
                )
    art_state = None
    art_sentinel_ok = None
    if out and out.is_file():
        try:
            doc = json.loads(out.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                art_state = doc.get("state") or doc.get("status")
            sent = str(u.get("completion_sentinel") or "")
            art_sentinel_ok = bool(sent) and sent in out.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            art_state = f"ERR:{type(exc).__name__}"
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
        "asserts": asserts[:30],
        "has_return": ret.is_file(),
        "has_manifest": man.is_file(),
        "return_status": (
            (ret_doc or {}).get("status") or (ret_doc or {}).get("state")
            if isinstance(ret_doc, dict)
            else None
        ),
        "named_cmds": cmds[:8],
        "manifest_rows": man_rows[:4],
    }


def main() -> None:
    rows = [brief(uid) for uid in IDS]
    out = HERE / "_shard11_dump.json"
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
                "live_sha16": r["live_sha16"],
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
                "probes": [
                    {
                        "name": p["name"],
                        "lines": p["lines"],
                        "froms": p["froms"],
                        "names": {k: v[:16] for k, v in (p.get("names") or {}).items()},
                        "tail": p["tail"][-14:],
                        "head": p["head"][:10],
                        "asserts": p.get("asserts"),
                        "fail_hits": p.get("fail_hits"),
                        "syntax_error": p.get("syntax_error"),
                    }
                    for p in r["probes"]
                ],
            }
        )
    out.write_text(json.dumps({"n": len(slim), "rows": slim}, indent=2), encoding="utf-8")
    print(f"wrote {out} n={len(slim)}")
    missing = []
    for r in slim:
        flags = []
        if not r["in_catalog"]:
            flags.append("NOCAT")
        if not r["probe_dir"]:
            flags.append("NOPROBE")
        if not r["output_exists"]:
            flags.append("NOOUT")
        if not r["has_return"]:
            flags.append("NORET")
        if not r["has_manifest"]:
            flags.append("NOMAN")
        if r["art_sentinel_ok"] is False:
            flags.append("NOSENT")
        if r["manifest_rows"] and not any(x.get("sha_match") for x in r["manifest_rows"]):
            flags.append("SHADRIFT")
        if flags:
            missing.append(r["id"])
        print(
            f"{r['id']}\tcat={r['in_catalog']}\tret={r['return_status']}\t"
            f"out={r['output_exists']}:{r['output_bytes']}\t"
            f"{len(r['probes'])}p\t{' '.join(flags) or 'ok-surface'}\t{r['title'][:50]}"
        )
    print(f"flagged={len(missing)}")


if __name__ == "__main__":
    main()
