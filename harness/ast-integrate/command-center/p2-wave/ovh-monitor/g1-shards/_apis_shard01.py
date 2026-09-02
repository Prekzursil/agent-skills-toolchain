#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-01.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]
STDLIB = {
    "abc","argparse","ast","asyncio","base64","binascii","builtins","collections",
    "contextlib","copy","csv","ctypes","dataclasses","datetime","decimal","difflib",
    "enum","fnmatch","functools","glob","hashlib","hmac","html","http","importlib",
    "inspect","io","itertools","json","logging","math","mmap","multiprocessing",
    "os","pathlib","pickle","platform","plistlib","pprint","queue","random","re",
    "secrets","shlex","shutil","signal","socket","sqlite3","ssl","stat","string",
    "struct","subprocess","sys","tempfile","textwrap","threading","time","tomllib",
    "traceback","types","typing","unicodedata","unittest","urllib","uuid","warnings",
    "weakref","xml","zipfile","zlib","__future__","jsonschema","pytest",
}


def calls_of(tree: ast.AST) -> list[str]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
            if name:
                out.append(name.split("(")[0][:80])
    return out[:80]


def main() -> None:
    rows = []
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        if not pdir.is_dir():
            continue
        files = []
        for p in sorted(pdir.glob("*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            imps = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        imps.append({"mod": a.name, "as": a.asname, "names": ["*"]})
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imps.append(
                        {
                            "mod": node.module,
                            "as": None,
                            "names": [a.name for a in node.names],
                        }
                    )
            files.append(
                {
                    "name": p.name,
                    "imports": imps,
                    "calls": sorted(set(calls_of(tree)))[:60],
                }
            )
        rows.append({"id": uid, "files": files})
    dest = WAVE / "ovh-monitor" / "g1-shards" / "_apis_shard01.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    # print non-stdlib imports
    for r in rows:
        mods = set()
        for f in r["files"]:
            for im in f["imports"]:
                top = im["mod"].split(".")[0]
                if top not in STDLIB:
                    mods.add(im["mod"] + ":" + ",".join(im["names"][:8]))
        if mods:
            print(f"{r['id']}:")
            for m in sorted(mods):
                print(f"  {m}")
    print("wrote", dest)


if __name__ == "__main__":
    main()
