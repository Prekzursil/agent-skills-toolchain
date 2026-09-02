#!/usr/bin/env python3
"""Extract imported production APIs from shard-18 probe files."""
from __future__ import annotations

import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-18.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
SKIP_ROOTS = {
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
    "importlib",
    "jsonschema",
    "cryptography",
    "signal",
}


def walk_calls(tree: ast.AST) -> dict[str, set[str]]:
    names: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                names.setdefault(fn.id, set()).add("()")
            elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                names.setdefault(fn.value.id, set()).add(fn.attr + "()")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            names.setdefault(node.value.id, set()).add(node.attr)
    return names


def main() -> None:
    rows = []
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        imports: dict[str, list[str]] = {}
        uses: dict[str, list[str]] = {}
        if pdir.is_dir():
            for p in sorted(pdir.glob("*.py")):
                text = p.read_text(encoding="utf-8", errors="replace")
                try:
                    tree = ast.parse(text)
                except SyntaxError:
                    continue
                local = {p.stem}
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        root = node.module.split(".")[0]
                        if root in SKIP_ROOTS or node.module in local:
                            continue
                        names = [a.name for a in node.names]
                        imports.setdefault(node.module, [])
                        for n in names:
                            if n not in imports[node.module]:
                                imports[node.module].append(n)
                    elif isinstance(node, ast.Import):
                        for a in node.names:
                            root = a.name.split(".")[0]
                            if root in SKIP_ROOTS:
                                continue
                            imports.setdefault(a.name, [])
                called = walk_calls(tree)
                for k, v in called.items():
                    if k in SKIP_ROOTS:
                        continue
                    uses.setdefault(k, [])
                    for attr in sorted(v):
                        if attr not in uses[k]:
                            uses[k].append(attr)
        prod = {k: v for k, v in imports.items() if k.split(".")[0] not in {"probe1", "probe2"}}
        rows.append({"id": uid, "imports": prod, "uses": uses})
    dest = HERE / "_shard18_apis.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("wrote", dest)
    for r in rows:
        interesting = {
            k: v
            for k, v in r["imports"].items()
            if k.split(".")[0]
            not in {
                "lib",
                "common",
                "engine",
                "scenario",
                "fixtures",
                "schema_local",
                "inventory",
                "gate",
                "anchors",
                "coverage",
                "overclaim",
                "control",
                "catalog_bind",
                "conditions",
                "evaluate",
                "controls",
                "differ",
                "reviewer",
                "fanin",
                "scenarios",
                "both_states",
                "detector",
                "preflight",
                "degrade_loudly",
                "nested_fanin",
                "surface",
                "runtime",
                "injection",
                "evaluator",
                "live_state",
                "predicate_table",
                "recompute",
                "manifest_schema",
                "corpus",
                "parity",
                "pipeline",
                "schema_ctl",
                "host",
                "install",
                "postcondition",
                "harness",
                "fetch_cache",
                "security",
                "blobread",
                "census",
                "durable",
                "ir_vocab",
                "mappings",
                "replay",
                "policy",
                "checks",
                "forge",
                "compute",
                "signals",
                "stats",
                "subtractor",
                "capture",
                "catalog",
                "measure",
                "protocol",
                "p2_jsonschema_hook",
            }
        }
        if interesting:
            print(r["id"], interesting)


if __name__ == "__main__":
    main()
