#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
reasons = json.loads((HERE / "_shard11_reasons.json").read_text(encoding="utf-8"))
dump = json.loads((HERE / "_shard11_dump.json").read_text(encoding="utf-8"))
by = {r["id"]: r for r in dump["rows"]}

CANDIDATE_ROOTS = [
    REPO / "tools",
    REPO / "plugin",
    REPO / "marketplace",
    REPO / "platform",
    REPO / "workflow_foundry",
    REPO / "router",
    REPO / "layout",
]


def locate(mod: str) -> list[str]:
    rels = []
    parts = mod.split(".")
    for root in CANDIDATE_ROOTS:
        p = root.joinpath(*parts)
        if p.with_suffix(".py").is_file():
            rels.append(p.with_suffix(".py").relative_to(REPO).as_posix())
        if (p / "__init__.py").is_file():
            rels.append((p / "__init__.py").relative_to(REPO).as_posix())
        # also if first component is skipped because root is that package
        if parts[0] == root.name:
            p2 = root.joinpath(*parts[1:])
            if p2.with_suffix(".py").is_file():
                rels.append(p2.with_suffix(".py").relative_to(REPO).as_posix())
            if (p2 / "__init__.py").is_file():
                rels.append((p2 / "__init__.py").relative_to(REPO).as_posix())
    # probe-local
    return sorted(set(rels))


def head_kind(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    kind = "real"
    if "g1-surface: generated" in text or "g1-mod: real-surface" in text:
        kind = "generated"
    if "class _NS" in text or "class Result" in text:
        kind = "stubbish"
    if "return Result(" in text and text.count("def ") <= 20:
        kind = "result-stub"
    return {
        "path": path.relative_to(REPO).as_posix(),
        "bytes": path.stat().st_size,
        "kind": kind,
        "head": text.splitlines()[:18],
        "n_def": text.count("def "),
        "n_class": text.count("class "),
    }


rows = []
for f in reasons["fails"]:
    uid = f["id"]
    d = by.get(uid) or {}
    imports = d.get("imports") or []
    locs = []
    for imp in imports:
        if imp in {
            "__future__",
            "json",
            "sys",
            "pathlib",
            "hashlib",
            "copy",
            "os",
            "io",
            "tempfile",
            "shutil",
            "ast",
            "random",
            "typing",
            "zipfile",
            "unicodedata",
            "collections",
            "jsonschema",
            "p2_jsonschema_hook",
            "http.server",
            "socket",
            "threading",
            "urllib.error",
            "urllib.request",
            "platform",
        }:
            continue
        found = locate(imp)
        # also probe-local
        pdir = WAVE / "probes" / uid
        local_py = pdir / f"{imp.replace('.', '/')}.py"
        local_init = pdir / imp.split(".")[0] / "__init__.py"
        if local_py.is_file():
            found.append(local_py.relative_to(REPO).as_posix())
        if local_init.is_file():
            found.append(local_init.relative_to(REPO).as_posix())
        info = []
        for rel in found:
            p = REPO / rel
            if p.is_file():
                info.append(head_kind(p))
        locs.append({"imp": imp, "files": info})
    rows.append(
        {
            "id": uid,
            "cls": f["cls"],
            "detail": f["detail"][:180],
            "tail": f["tail8"][-500:],
            "imports": imports,
            "mods": locs,
            "py_files": d.get("py_files"),
        }
    )

dest = HERE / "_shard11_modscan.json"
dest.write_text(json.dumps({"n": len(rows), "rows": rows}, indent=2), encoding="utf-8")
print("wrote", dest)
for r in rows:
    stubby = []
    for m in r["mods"]:
        for fi in m["files"]:
            if fi["kind"] != "real":
                stubby.append(f"{m['imp']}:{fi['path']}:{fi['kind']}:{fi['bytes']}")
    print(f"{r['id']:10} {r['cls']:28} stubby={stubby[:3] or '-'}")
