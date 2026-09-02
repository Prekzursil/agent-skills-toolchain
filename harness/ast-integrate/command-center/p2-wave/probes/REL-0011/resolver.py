#!/usr/bin/env python3
"""Independent component-closure resolver for REL-0011.

Tool B. Mechanically different from generator.py:
  * BFS of npm lockfile dependency edges starting at packages[""]
  * pip-compile via-comment depth (not column-0 only)
  * os.walk of vendor/ looking for component.json (not vendor-manifest.json)

Does not emit CycloneDX. Does not import generator. A missing peer or a
lockfile edge with no packages map entry is NOT-CHECKED, never invented.
"""
from __future__ import annotations

import json
import os
import re
from collections import deque
from pathlib import Path
from typing import Any

TOOL_NAME = "rel0011-lockfile-graph-and-vendored-resolver"
TOOL_KIND = "lockfile-bfs-plus-vendor-walk"
MAX_WALK_DEPTH = 32

_PIP_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+)")
_VIA = re.compile(r"#\s*via\s+(.+)$")


def _npm_lookup(packages: dict, name: str) -> dict | None:
    meta = packages.get(f"node_modules/{name}")
    return meta if isinstance(meta, dict) else None


def resolve_npm_graph(lock: dict) -> tuple[list[dict], int, list[dict]]:
    packages = lock.get("packages") if isinstance(lock, dict) else None
    if not isinstance(packages, dict):
        return [], 0, [
            {
                "name": "package-lock.json",
                "status": "NOT-CHECKED",
                "reason": "packages map absent; resolver refused to invent a closure",
                "depth": 0,
            }
        ]
    root = packages.get("") if isinstance(packages.get(""), dict) else {}
    queue: deque[tuple[str, int]] = deque()
    for name in (root.get("dependencies") or {}):
        queue.append((str(name), 1))
    seen: dict[str, dict] = {}
    not_checked: list[dict] = []
    walked = 0
    while queue:
        name, depth = queue.popleft()
        if depth > MAX_WALK_DEPTH:
            not_checked.append(
                {
                    "name": name,
                    "status": "NOT-CHECKED",
                    "reason": f"resolver refused to walk past depth {MAX_WALK_DEPTH}",
                    "depth": depth,
                }
            )
            continue
        if name in seen:
            continue
        meta = _npm_lookup(packages, name)
        if meta is None:
            not_checked.append(
                {
                    "name": name,
                    "status": "NOT-CHECKED",
                    "reason": (
                        "dependency name not in lockfile packages map; "
                        "resolver refused to invent a version"
                    ),
                    "depth": depth,
                }
            )
            continue
        version = str(meta.get("version") or "").strip()
        if not version:
            not_checked.append(
                {
                    "name": name,
                    "status": "NOT-CHECKED",
                    "reason": "packages map entry has no version; resolver refused to invent one",
                    "depth": depth,
                }
            )
            continue
        walked = max(walked, depth)
        purl = f"pkg:npm/{name}@{version}"
        seen[name] = {
            "name": name,
            "version": version,
            "purl": purl,
            "depth": depth,
            "ecosystem": "npm",
        }
        for child in meta.get("dependencies") or {}:
            queue.append((str(child), depth + 1))
        for peer in meta.get("peerDependencies") or {}:
            peer_name = str(peer)
            if _npm_lookup(packages, peer_name) is None and peer_name not in seen:
                not_checked.append(
                    {
                        "name": peer_name,
                        "status": "NOT-CHECKED",
                        "reason": (
                            f"peerDependency of {name} not present in lockfile "
                            "packages map; resolver refused to invent a version"
                        ),
                        "depth": depth + 1,
                    }
                )
    return list(seen.values()), walked, not_checked


def resolve_pip_via_depth(text: str) -> tuple[list[dict], int]:
    """Token-scan pins and attach via-comment depth. Not column-0 filtering."""
    comps: list[dict] = []
    pending: dict | None = None
    walked = 0
    for line in text.splitlines():
        stripped = line.strip()
        pin = _PIP_PIN.match(stripped)
        if pin and not line.startswith((" ", "\t")):
            name, version = pin.group(1), pin.group(2)
            pending = {
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name}@{version}",
                "depth": 1,
                "ecosystem": "pypi",
            }
            comps.append(pending)
            walked = max(walked, 1)
            continue
        if pending is None:
            continue
        via = _VIA.search(line)
        if not via:
            continue
        parent = via.group(1).strip()
        if parent and parent != "ast-release":
            pending["depth"] = 2
            walked = max(walked, 2)
    return comps, walked


def resolve_vendor_tree(root: Path) -> list[dict]:
    vendor = root / "vendor"
    found: list[dict] = []
    if not vendor.is_dir():
        return found
    for dirpath, _dirnames, filenames in os.walk(vendor):
        if "component.json" not in filenames:
            continue
        ident = Path(dirpath) / "component.json"
        try:
            data = json.loads(ident.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        name = str(data.get("name") or "").strip()
        version = str(data.get("version") or "").strip()
        if not name or not version:
            continue
        found.append(
            {
                "name": name,
                "version": version,
                "purl": f"pkg:generic/{name}@{version}",
                "depth": 1,
                "ecosystem": "generic",
                "path": str(Path(dirpath).resolve().relative_to(root.resolve())),
            }
        )
    found.sort(key=lambda c: str(c.get("purl") or ""))
    return found


def resolve(release_root: Path) -> dict[str, Any]:
    root = Path(release_root)
    components: list[dict] = []
    not_checked: list[dict] = []
    walked = 0
    lock_path = root / "package-lock.json"
    if lock_path.is_file():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        npm, npm_depth, npm_nc = resolve_npm_graph(lock)
        components.extend(npm)
        walked = max(walked, npm_depth)
        not_checked.extend(npm_nc)
    else:
        not_checked.append(
            {
                "name": "package-lock.json",
                "status": "NOT-CHECKED",
                "reason": "lockfile absent on the unpacked distributable",
                "depth": 0,
            }
        )
    pip_path = root / "python-requirements.lock"
    if pip_path.is_file():
        pip_comps, pip_depth = resolve_pip_via_depth(pip_path.read_text(encoding="utf-8"))
        components.extend(pip_comps)
        walked = max(walked, pip_depth)
    components.extend(resolve_vendor_tree(root))
    components.sort(key=lambda c: str(c.get("purl") or ""))
    return {
        "tool": TOOL_NAME,
        "kind": TOOL_KIND,
        "components": components,
        "walked_depth": walked,
        "not_checked": not_checked,
    }


def closure_purls(report: dict) -> list[str]:
    out = []
    for c in report.get("components") or []:
        if isinstance(c, dict) and c.get("purl"):
            out.append(str(c["purl"]))
    return sorted(out)


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    json.dump(resolve(target), sys.stdout, indent=2)
    sys.stdout.write("\n")
