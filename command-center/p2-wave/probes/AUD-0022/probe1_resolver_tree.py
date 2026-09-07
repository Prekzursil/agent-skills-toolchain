#!/usr/bin/env python3
"""AUD-0022 Probe 1: resolver's own tree output (npm ls + package-lock walk)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe1-resolver-tree.json"
RAW = PROBE / "probe1-resolver.raw.txt"


def walk_lock(lock: dict) -> tuple[list[dict], int, dict[str, set[str]]]:
    """Build edges from package-lock v2/v3 packages map; track version sets."""
    packages = lock.get("packages") or {}
    edges: list[dict] = []
    versions: dict[str, set[str]] = defaultdict(set)
    for path, meta in packages.items():
        if not isinstance(meta, dict):
            continue
        name = meta.get("name")
        if not name and path.startswith("node_modules/"):
            name = path.rsplit("node_modules/", 1)[-1]
        ver = meta.get("version")
        if name and ver:
            versions[name].add(str(ver))
        deps = meta.get("dependencies") or {}
        for dep, dep_ver in deps.items():
            edges.append(
                {
                    "from": name or (path or "(root)"),
                    "to": dep,
                    "declared": dep_ver,
                    "via": path or "(root)",
                }
            )
    # depth: BFS from root packages[""]
    depth = 0
    if packages:
        # approximate: count path segments under node_modules
        for path in packages:
            if not path:
                continue
            segs = [s for s in path.split("/") if s == "node_modules"]
            depth = max(depth, len(segs))
    return edges, depth, {k: sorted(v) for k, v in versions.items()}


def npm_ls() -> tuple[int, dict | None, str]:
    try:
        r = subprocess.run(
            ["npm", "ls", "--all", "--json", "--omit=dev"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=180,
            encoding="utf-8",
            errors="replace",
        )
        raw = (r.stdout or "") + (r.stderr or "")
        try:
            doc = json.loads(r.stdout or "{}")
        except json.JSONDecodeError:
            doc = None
        return r.returncode, doc, raw[:20000]
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, None, f"{type(e).__name__}: {e}"


def count_npm_tree(node: dict | None, seen: set[str] | None = None) -> tuple[int, int]:
    if not isinstance(node, dict):
        return 0, 0
    seen = seen or set()
    deps = node.get("dependencies") or {}
    n = 0
    dmax = 0
    for name, child in deps.items():
        key = f"{name}@{child.get('version') if isinstance(child, dict) else '?'}"
        if key in seen:
            continue
        seen.add(key)
        n += 1
        if isinstance(child, dict):
            cn, cd = count_npm_tree(child, seen)
            n += cn
            dmax = max(dmax, 1 + cd)
        else:
            dmax = max(dmax, 1)
    return n, dmax


def main() -> int:
    lock_path = REPO / "package-lock.json"
    lines: list[str] = []
    lines.append("AUD-0022 NAMED PROBE 1: resolver tree output")
    lines.append("unit=AUD-0022")
    lines.append(f"lock_exists={lock_path.is_file()}")

    edges: list[dict] = []
    max_depth = 0
    versions: dict[str, list[str]] = {}
    lock_packages = 0
    if lock_path.is_file():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        edges, max_depth, versions = walk_lock(lock)
        lock_packages = len(lock.get("packages") or {})
        lines.append(f"lock_lockfileVersion={lock.get('lockfileVersion')}")
        lines.append(f"lock_packages={lock_packages}")
        lines.append(f"lock_edges={len(edges)}")
        lines.append(f"lock_max_node_modules_depth={max_depth}")

    npm_rc, npm_doc, npm_raw = npm_ls()
    npm_nodes, npm_depth = count_npm_tree(npm_doc)
    lines.append(f"npm_ls_exit={npm_rc}")
    lines.append(f"npm_ls_nodes={npm_nodes}")
    lines.append(f"npm_ls_max_depth={npm_depth}")
    lines.append("NPM_LS_HEAD_BEGIN")
    lines.append(npm_raw[:4000])
    lines.append("NPM_LS_HEAD_END")

    dupes = {n: vs for n, vs in versions.items() if len(vs) >= 2}
    lines.append(f"duplicate_version_packages={len(dupes)}")
    for n, vs in sorted(dupes.items())[:40]:
        lines.append(f"DUP\t{n}\t{','.join(vs)}")

    result = {
        "ok": True,
        "unit": "AUD-0022",
        "probe": 1,
        "lock_packages": lock_packages,
        "lock_edges": len(edges),
        "lock_max_depth": max_depth,
        "npm_ls_exit": npm_rc,
        "npm_ls_nodes": npm_nodes,
        "npm_ls_max_depth": npm_depth,
        "unique_packages": len(versions),
        "duplicate_version_count": len(dupes),
        "duplicate_versions": {k: v for k, v in sorted(dupes.items())[:100]},
        "sample_edges": edges[:50],
        "max_depth": max(max_depth, npm_depth),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines.append(
        f"SUMMARY unique={len(versions)} dupes={len(dupes)} "
        f"max_depth={result['max_depth']} edges={len(edges)}"
    )
    lines.append("SUCCESS:AUD-0022-probe1")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
