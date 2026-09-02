#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-15.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
STUB_MARKERS = (
    "# g1-mod: real-surface",
    "# g1-surface: generated",
    "class _NS:",
    "return Result()",
)
STDLIB = {
    "__future__",
    "os",
    "sys",
    "json",
    "pathlib",
    "re",
    "hashlib",
    "typing",
    "unittest",
    "pytest",
    "tempfile",
    "subprocess",
    "collections",
    "datetime",
    "functools",
    "itertools",
    "io",
    "copy",
    "math",
    "enum",
    "abc",
    "dataclasses",
    "argparse",
    "shutil",
    "textwrap",
    "inspect",
    "ast",
    "types",
    "contextlib",
    "warnings",
    "logging",
    "traceback",
    "glob",
    "fnmatch",
    "base64",
    "uuid",
    "time",
    "struct",
    "zlib",
    "gzip",
    "tarfile",
    "zipfile",
    "csv",
    "xml",
    "html",
    "http",
    "urllib",
    "ssl",
    "socket",
    "threading",
    "multiprocessing",
    "concurrent",
    "asyncio",
    "sqlite3",
    "decimal",
    "random",
    "string",
    "pprint",
    "hmac",
    "secrets",
    "platform",
    "errno",
    "signal",
    "importlib",
    "jsonschema",
}


def imports_of(text: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append(a.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append(node.module)
    return out


def find_mod(mod: str) -> list[Path]:
    parts = mod.split(".")
    roots = [
        REPO,
        REPO / "tools",
        REPO / "tools" / "agentspec",
        REPO / "platform" / "lib",
        REPO / "command-center",
        REPO / "command-center" / "p2-wave" / "seed-stage",
    ]
    hits = []
    for root in roots:
        cands = [
            root.joinpath(*parts).with_suffix(".py"),
            root.joinpath(*parts) / "__init__.py",
        ]
        for p in cands:
            if p.is_file():
                hits.append(p)
    return hits


def stubby(path: Path) -> bool:
    head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    return any(m in head for m in STUB_MARKERS)


def main() -> None:
    rows = []
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        mods = []
        for p in sorted(pdir.glob("*.py")):
            for m in imports_of(p.read_text(encoding="utf-8", errors="replace")):
                root = m.split(".")[0]
                if root in STDLIB:
                    continue
                local = pdir / f"{root}.py"
                local_pkg = pdir / root / "__init__.py"
                if local.is_file() or local_pkg.is_file():
                    hits = [local if local.is_file() else local_pkg]
                    kind = "probe-local"
                else:
                    hits = find_mod(m)
                    kind = "shared"
                if not hits:
                    mods.append({"mod": m, "kind": kind, "status": "missing"})
                    continue
                for h in hits:
                    mods.append(
                        {
                            "mod": m,
                            "kind": kind,
                            "status": "stub" if stubby(h) else "ok",
                            "path": str(h.relative_to(REPO)).replace("\\", "/"),
                            "bytes": h.stat().st_size,
                        }
                    )
        # unique
        seen = set()
        uniq = []
        for m in mods:
            key = (m["mod"], m.get("path"), m["status"])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(m)
        rows.append({"id": uid, "mods": uniq})
    dest = HERE / "_shard15_stubscan.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("wrote", dest)
    for r in rows:
        bad = [m for m in r["mods"] if m["status"] in {"missing", "stub"}]
        if bad:
            print(
                r["id"],
                [(m["status"], m["mod"], m.get("path", "")) for m in bad],
            )


if __name__ == "__main__":
    main()
