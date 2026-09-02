#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

WAVE = Path(__file__).resolve().parents[2]
rows = json.loads((WAVE / "ovh-monitor" / "g1-shards" / "_shard06_diag.json").read_text(encoding="utf-8"))
REPO = WAVE.parents[1]


def compact_one(r: dict) -> dict:
    named = [c for c in (r.get("named_probes") or []) if c]
    missing_cmds = []
    for cmd in named:
        # last token that looks like a path
        parts = cmd.split()
        py = next((p for p in parts if p.endswith(".py")), None)
        if py:
            p = REPO / py
            if not p.is_file():
                missing_cmds.append(py)
    # key imports from probe_detail
    froms = []
    assert_tails = {}
    for name, det in (r.get("probe_detail") or {}).items():
        im = det.get("imports") or {}
        froms.extend(im.get("froms") or [])
        a = det.get("asserts") or []
        if a:
            assert_tails[name] = a[-12:]
    skip = {
        "__future__", "json", "sys", "os", "pathlib", "subprocess", "tempfile",
        "unittest", "hashlib", "re", "ast", "copy", "inspect", "shutil",
        "datetime", "typing", "dataclasses", "enum", "collections", "io",
        "argparse", "textwrap", "functools", "itertools", "uuid", "math",
        "struct", "base64", "gzip", "zipfile", "tarfile", "csv", "configparser",
        "fnmatch", "glob", "traceback", "logging", "time", "random", "string",
        "contextlib", "abc", "weakref", "types", "operator", "heapq",
    }
    froms_u = sorted({f for f in froms if f and f.split(".")[0] not in skip and not f.startswith(".")})
    return {
        "id": r["id"],
        "title": r.get("title"),
        "output": r.get("output_path"),
        "artifact_exists": r.get("artifact_exists"),
        "artifact_bytes": r.get("artifact_bytes"),
        "probe_files": r.get("probe_files"),
        "helpers": r.get("helpers"),
        "all_files": r.get("all_files"),
        "ret_status": r.get("ret_status"),
        "named_probes": named,
        "missing_probe_py": missing_cmds,
        "has_return": r.get("has_return"),
        "has_manifest": r.get("has_manifest"),
        "man_row_present": bool(r.get("man_row")),
        "man_sha": (r.get("man_row") or {}).get("sha256"),
        "froms": froms_u,
        "assert_tails": assert_tails,
    }


def main() -> None:
    out = [compact_one(r) for r in rows]
    path = WAVE / "ovh-monitor" / "g1-shards" / "_shard06_compact.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    missing = [x["id"] for x in out if x["missing_probe_py"]]
    no_art = [x["id"] for x in out if not x["artifact_exists"]]
    no_ret = [x["id"] for x in out if not x["has_return"]]
    print(f"n={len(out)} missing_probe_py={len(missing)} no_artifact={len(no_art)} no_return={len(no_ret)}")
    print("missing_probe_py", missing)
    print("no_artifact", no_art)
    print("no_return", no_ret)
    print("froms_union")
    all_froms = sorted({f for x in out for f in x["froms"]})
    print(all_froms)


if __name__ == "__main__":
    main()
