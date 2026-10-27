"""Independent lockfile identity oracle (does not import sbom)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REQ = re.compile(r"^([A-Za-z0-9_.-]+)==([^;#\s]+)")


def _npm_tree_identities(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    out: set[tuple[str, str]] = set()

    def walk(tree: Any) -> None:
        if not isinstance(tree, dict):
            return
        for name, meta in tree.items():
            if not isinstance(meta, dict):
                continue
            ver = str(meta.get("version") or "")
            if ver:
                out.add((str(name), ver))
            nested = meta.get("dependencies")
            if isinstance(nested, dict):
                walk(nested)

    deps = data.get("dependencies")
    if isinstance(deps, dict):
        walk(deps)
    return out


def _requirements_identities(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    out: set[tuple[str, str]] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = _REQ.match(raw.strip())
        if m:
            out.add((m.group(1), m.group(2)))
    return out


def _poetry_identities(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    out: set[tuple[str, str]] = set()
    name = ""
    version = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "[[package]]":
            if name and version:
                out.add((name, version))
            name, version = "", ""
            continue
        if line.startswith("name ="):
            name = line.split("=", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("version ="):
            version = line.split("=", 1)[1].strip().strip('"').strip("'")
    if name and version:
        out.add((name, version))
    return out


def independent_lockfile_identities(root: Path) -> set[tuple[str, str]]:
    root = Path(root)
    return (
        _npm_tree_identities(root / "package-lock.json")
        | _requirements_identities(root / "requirements.lock")
        | _poetry_identities(root / "poetry.lock")
    )


def vendored_dir_names(root: Path) -> set[str]:
    vendor = Path(root) / "vendor"
    if not vendor.is_dir():
        return set()
    return {p.name for p in vendor.iterdir() if p.is_dir()}


def compare_sets(left: set[tuple[str, str]], right: set[tuple[str, str]]) -> dict[str, Any]:
    return {
        "equal": set(left) == set(right),
        "only_left": sorted(set(left) - set(right)),
        "only_right": sorted(set(right) - set(left)),
        "n_left": len(left),
        "n_right": len(right),
    }
