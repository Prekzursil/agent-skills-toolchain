#!/usr/bin/env python3
"""Compact shard-19 dump into API + assert briefs."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "_shard19_dump.json").read_text(encoding="utf-8"))
SKIP = {
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
    "importlib.util",
    "shlex",
}

LOCAL_HINTS = (
    "probe1",
    "probe2",
    "probe_common",
    "scenario",
    "fixtures",
    "schema_local",
    "anchors",
    "live",
    "overclaim",
    "common",
    "measure",
    "checker",
    "measures",
    "taxonomy",
    "inventory",
    "sources",
    "bands",
    "calibrate",
    "constants",
    "detector",
    "adapter",
    "audit",
    "auditor",
    "census",
    "clock_lib",
    "lineage",
    "ir",
    "topology",
    "change_surface",
    "rubric",
    "secret_shapes",
    "sink_scrub",
    "schema_validate",
    "fixture",
    "compat_diagnostics",
    "gc_index_lockfile",
    "gc_provenance",
    "gc_store",
    "detector_self_test",
    "coverage_gate",
    "simulate_inside_client",
    "test_coverage_gate",
    "validate_receipt_schema",
    "p2_jsonschema_hook",
)

out = []
for r in rows:
    froms = []
    for src in (r.get("imports") or []):
        root = src.split(".")[0]
        if root in SKIP or src in SKIP:
            continue
        froms.append(src)
    names = r.get("probe_names") or {}
    interesting = {}
    for pname, nmap in names.items():
        if not isinstance(nmap, dict):
            continue
        keep = {}
        for k, attrs in nmap.items():
            if k in SKIP or k in {"Path", "REPO", "HERE", "WAVE", "PROBES"}:
                continue
            if attrs:
                keep[k] = attrs[:20]
        if keep:
            interesting[pname] = keep
    compact = {
        "id": r["id"],
        "title": r["title"][:140],
        "output_path": r["output_path"],
        "sentinel": r["sentinel"][:160],
        "py_files": r["py_files"],
        "imports": froms,
        "asserts": (r.get("asserts") or [])[:25],
        "named_cmds": r.get("named_cmds") or [],
        "sha_match": all(x.get("sha_match") for x in (r.get("manifest_rows") or []) or [{"sha_match": True}]),
        "manifest_rows": r.get("manifest_rows"),
        "attrs": interesting,
        "heads": {k: v[:16] for k, v in (r.get("probe_heads") or {}).items()},
        "tails": {k: v[-18:] for k, v in (r.get("probe_tails") or {}).items()},
    }
    out.append(compact)

path = HERE / "_shard19_compact.json"
path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print("n", len(out), "bytes", path.stat().st_size)
for c in out:
    print("---", c["id"], c["title"][:70])
    print("  imports", c["imports"][:10])
    print("  asserts", len(c["asserts"]), (c["asserts"][:3] if c["asserts"] else "NONE"))
    print("  sha", c["sha_match"], "cmds", len(c["named_cmds"]))
