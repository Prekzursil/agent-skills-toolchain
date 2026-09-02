"""Lockfile inventory for AUD-0023.

Production lockfiles are first-party files outside other units' probe
fixtures. The known-advisory control lockfile is always admitted.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTROL_LOCK = (
    "command-center/p2-wave/probes/AUD-0023/fixtures/known-advisory/"
    "package-lock.json"
)
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    # Vendored third-party trees and p2-wave scratch copies are not the
    # product closure. scw-pull mirrors other units' known-vuln locks and
    # would inflate the production headline / trip the sibling-fixture guard.
    "vendor",
    "scw-pull",
    "ovh-monitor",
}
LOCK_NAMES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "poetry.lock",
    "Pipfile.lock",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.lock",
    "composer.lock",
    "uv.lock",
}


def _rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def is_other_probe_fixture(rel: str) -> bool:
    if rel == CONTROL_LOCK:
        return False
    marker = "command-center/p2-wave/probes/"
    if not rel.startswith(marker):
        return False
    rest = rel[len(marker) :]
    return not rest.startswith("AUD-0023/")


def parse_npm_lock(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pkgs: list[dict] = []
    packages = data.get("packages") or {}
    if isinstance(packages, dict):
        for key, meta in packages.items():
            if not key or not isinstance(meta, dict):
                continue
            version = meta.get("version")
            if not isinstance(version, str) or not version:
                continue
            name = meta.get("name")
            if not isinstance(name, str) or not name:
                name = key.rsplit("node_modules/", 1)[-1]
            pkgs.append(
                {
                    "ecosystem": "npm",
                    "name": name,
                    "version": version,
                    "lock_key": key,
                }
            )
        return pkgs
    deps = data.get("dependencies") or {}
    stack = [deps] if isinstance(deps, dict) else []
    while stack:
        cur = stack.pop()
        if not isinstance(cur, dict):
            continue
        for name, meta in cur.items():
            if not isinstance(meta, dict):
                continue
            version = meta.get("version")
            if isinstance(version, str) and version:
                pkgs.append(
                    {
                        "ecosystem": "npm",
                        "name": name,
                        "version": version,
                        "lock_key": name,
                    }
                )
            nested = meta.get("dependencies")
            if isinstance(nested, dict):
                stack.append(nested)
    return pkgs


def parse_lockfile(path: Path) -> tuple[list[dict], str | None]:
    name = path.name
    try:
        if name in {"package-lock.json", "npm-shrinkwrap.json"}:
            return parse_npm_lock(path), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [], f"{type(exc).__name__}: {exc}"
    return [], f"parser-not-implemented:{name}"


def inventory(repo: Path | None = None) -> dict:
    root = repo or REPO
    found: list[dict] = []
    seen: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        current = Path(dirpath)
        try:
            rel_dir = current.resolve().relative_to(root).as_posix()
        except ValueError:
            dirnames[:] = []
            continue
        if rel_dir == "command-center/p2-wave/probes":
            dirnames[:] = [d for d in dirnames if d == "AUD-0023"]
        elif rel_dir.startswith("command-center/p2-wave/probes/") and not rel_dir.startswith(
            "command-center/p2-wave/probes/AUD-0023"
        ):
            dirnames[:] = []
            continue
        for name in filenames:
            if name not in LOCK_NAMES:
                continue
            path = current / name
            rel = _rel(path)
            if rel in seen:
                continue
            seen.add(rel)
            if is_other_probe_fixture(rel):
                found.append(
                    {
                        "path": rel,
                        "kind": name,
                        "scope": "sibling-probe-fixture",
                        "admitted": False,
                        "packages": [],
                        "parse_error": None,
                        "note": "other unit fixture; not the AUD-0023 closure",
                    }
                )
                continue
            pkgs, err = parse_lockfile(path)
            scope = "control" if rel == CONTROL_LOCK else "production"
            found.append(
                {
                    "path": rel,
                    "kind": name,
                    "scope": scope,
                    "admitted": True,
                    "packages": pkgs,
                    "parse_error": err,
                    "note": None,
                }
            )
    control = next((row for row in found if row["path"] == CONTROL_LOCK), None)
    if control is None:
        path = root / CONTROL_LOCK
        pkgs, err = parse_lockfile(path) if path.is_file() else ([], "absent")
        found.append(
            {
                "path": CONTROL_LOCK,
                "kind": "package-lock.json",
                "scope": "control",
                "admitted": True,
                "packages": pkgs,
                "parse_error": err,
                "note": "control lockfile",
            }
        )
    admitted = [row for row in found if row["admitted"]]
    skipped = [row for row in found if not row["admitted"]]
    return {
        "lockfiles": found,
        "admitted": admitted,
        "skipped_sibling_fixtures": skipped,
        "aud0022_path": "command-center/audit/AUD-0022-transitive-dep-graph.json",
        "aud0022_present": (root / "command-center/audit/AUD-0022-transitive-dep-graph.json").is_file(),
        "control_lock": CONTROL_LOCK,
        "production_admitted": [
            row["path"] for row in admitted if row["scope"] == "production"
        ],
    }
