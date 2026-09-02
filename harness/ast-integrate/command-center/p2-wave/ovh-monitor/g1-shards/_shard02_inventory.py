#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
WAVE = REPO / "command-center" / "p2-wave"
FAILS = [
    ln.split("\n", 1)[0].strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "_shard02_fails.txt")
    .read_text(encoding="utf-8")
    .split("=" * 72)
    if ln.strip() and not ln.strip().startswith("FAILED")
]
# better parse
ids = []
for block in (WAVE / "ovh-monitor" / "g1-shards" / "_shard02_fails.txt").read_text(encoding="utf-8").split("=" * 72):
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if lines and lines[0][0:3].isalpha() and "-" in lines[0][:8]:
        ids.append(lines[0].split()[0])

STDLIB = {
    "abc", "argparse", "array", "ast", "asyncio", "base64", "binascii", "builtins",
    "codecs", "collections", "contextlib", "copy", "csv", "ctypes", "dataclasses",
    "datetime", "decimal", "difflib", "email", "enum", "errno", "fnmatch", "functools",
    "glob", "gzip", "hashlib", "hmac", "html", "http", "importlib", "inspect", "io",
    "itertools", "json", "keyword", "locale", "logging", "math", "mimetypes", "mmap",
    "multiprocessing", "numbers", "operator", "os", "pathlib", "pickle", "pkgutil",
    "platform", "pprint", "queue", "random", "re", "reprlib", "secrets", "shlex",
    "shutil", "signal", "socket", "sqlite3", "ssl", "stat", "string", "struct",
    "subprocess", "sys", "tarfile", "tempfile", "textwrap", "threading", "time",
    "tokenize", "traceback", "types", "typing", "unicodedata", "unittest", "urllib",
    "uuid", "warnings", "weakref", "xml", "zipfile", "zlib", "__future__",
}


def is_stub(path: Path) -> bool:
    if not path.is_file():
        return False
    head = path.read_text(encoding="utf-8", errors="replace")[:900]
    return "g1-surface: generated" in head or "class _NS:" in head


def imports_of(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                if top not in STDLIB:
                    mods.append(a.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top not in STDLIB:
                names = [n.name for n in node.names]
                mods.append(node.module + ":" + ",".join(names))
    return sorted(set(mods))


def resolve(mod: str) -> list[Path]:
    dotted = mod.split(":", 1)[0]
    parts = dotted.split(".")
    cands = []
    for root in (REPO, REPO / "tools", REPO / "platform" / "lib", REPO / "command-center"):
        p = root.joinpath(*parts)
        if p.with_suffix(".py").is_file():
            cands.append(p.with_suffix(".py"))
        if (p / "__init__.py").is_file():
            cands.append(p / "__init__.py")
    return cands


def harvest_copies(rel: str) -> list[Path]:
    out = []
    mon = WAVE / "ovh-monitor"
    for kind in ("delivery-pull", "missing-pull", "error-pull"):
        root = mon / kind
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in ("tree", "delta", "extracted", "extracted-delta"):
                cand = box / sub / rel
                if cand.is_file() and cand.stat().st_size > 40:
                    out.append(cand)
    return out


def main() -> None:
    rows = []
    stub_hits: dict[str, list[str]] = {}
    missing: dict[str, list[str]] = {}
    for uid in ids:
        pdir = WAVE / "probes" / uid
        if not pdir.is_dir():
            continue
        py_files = sorted(pdir.glob("*.py"))
        imps = []
        for py in py_files:
            imps.extend(imports_of(py))
        imps = sorted(set(imps))
        rec = {"id": uid, "imports": imps, "resolved": []}
        for mod in imps:
            cands = resolve(mod)
            if not cands:
                missing.setdefault(mod, []).append(uid)
                rec["resolved"].append({"mod": mod, "status": "missing"})
                continue
            stubbed = [str(p.relative_to(REPO).as_posix()) for p in cands if is_stub(p)]
            real = [str(p.relative_to(REPO).as_posix()) for p in cands if not is_stub(p)]
            if stubbed and not real:
                stub_hits.setdefault(mod, []).append(uid)
            rec["resolved"].append({"mod": mod, "real": real, "stub": stubbed})
        rows.append(rec)
    dest = WAVE / "ovh-monitor" / "g1-shards" / "_shard02_inventory.json"
    dest.write_text(
        json.dumps({"n": len(ids), "ids": ids, "missing": missing, "stubs": stub_hits, "rows": rows}, indent=2),
        encoding="utf-8",
    )
    print("ids", len(ids))
    print("STUBS")
    for k, v in sorted(stub_hits.items(), key=lambda kv: -len(kv[1])):
        print(f"  {k}\t{len(v)}\t{','.join(v[:6])}")
    print("MISSING")
    for k, v in sorted(missing.items(), key=lambda kv: -len(kv[1])):
        print(f"  {k}\t{len(v)}\t{','.join(v[:6])}")
    print("wrote", dest)


if __name__ == "__main__":
    main()
