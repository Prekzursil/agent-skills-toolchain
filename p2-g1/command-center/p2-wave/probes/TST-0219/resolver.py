"""TST-0219 resolver-under-test: origin+integrity pinning defeats dependency confusion.

A lockfile entry MUST pin both:
  origin    - the exact registry base URL the artifact may come from
  integrity - the sha256 of the artifact payload

Resolution rules (fail closed):
  * no origin pin            -> ORIGIN_PIN_MISSING, nothing written
  * pinned origin missing the artifact, while another registry offers the same
    name                     -> DEPENDENCY_CONFUSION naming package, pinned
                                origin, offered origin and integrity; nothing
                                written
  * integrity mismatch       -> INTEGRITY_MISMATCH, nothing written
  * pinned origin serves the artifact and integrity matches -> installed

``install_confused_mutant`` is the named defect: it ignores origin pins and
picks the highest version from ANY registry.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


class ResolutionRefused(Exception):
    def __init__(self, code: str, detail: dict[str, Any]) -> None:
        super().__init__(code)
        self.code = code
        self.detail = dict(detail)


def _registry_get(registry_root: Path, name: str, version: str) -> tuple[bytes, str] | None:
    entry = registry_root / name / version / "payload.txt"
    if not entry.is_file():
        return None
    data = entry.read_bytes()
    return data, hashlib.sha256(data).hexdigest()


def dest_tree_hash(dest: Path) -> str:
    """Tree hash via sorted rglob of (relpath + bytes)."""
    h = hashlib.sha256()
    if not dest.exists():
        return h.hexdigest()
    for path in sorted(dest.rglob("*")):
        if path.is_file():
            h.update(str(path.relative_to(dest)).replace(chr(92), "/").encode("utf-8"))
            h.update(path.read_bytes())
    return h.hexdigest()


def _versions(registry_root: Path, name: str) -> list[str]:
    base = registry_root / name
    if not base.is_dir():
        return []
    return [p.name for p in base.iterdir() if p.is_dir()]


def install(lockfile: dict[str, Any], dest: Path, registries: dict[str, Path]) -> dict[str, Any]:
    name = str(lockfile.get("name") or "")
    version = str(lockfile.get("version") or "")
    origin = lockfile.get("origin")
    integrity = lockfile.get("integrity")
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    if not origin or not str(origin).strip():
        raise ResolutionRefused(
            "ORIGIN_PIN_MISSING",
            {"name": name, "message": "lockfile pins integrity only; registry origin is not pinned"},
        )
    origin_key = str(origin)
    registry_root = registries.get(origin_key)
    if registry_root is None:
        raise ResolutionRefused(
            "ORIGIN_UNREACHABLE",
            {"name": name, "pinned_origin": origin_key, "known_origins": sorted(registries)},
        )
    got = _registry_get(registry_root, name, version)
    if got is None:
        offered_origins = [
            k for k, root in registries.items()
            if root is not registry_root and _versions(root, name)
        ]
        offered = sorted({v for other_key, root in registries.items() for v in _versions(root, name)})
        raise ResolutionRefused(
            "DEPENDENCY_CONFUSION",
            {
                "name": name,
                "pinned_origin": origin_key,
                "offered_origin": offered_origins,
                "offered_versions": offered,
                "integrity": integrity,
                "message": (
                    "dependency confusion refused: package "
                    + name
                    + "@"
                    + version
                    + " is pinned to origin "
                    + origin_key
                    + " which does not serve it; same-named package offered elsewhere"
                ),
            },
        )
    data, actual = got
    if integrity and actual != integrity:
        raise ResolutionRefused(
            "INTEGRITY_MISMATCH",
            {"name": name, "expected": integrity, "actual": actual},
        )
    (dest / name / version).mkdir(parents=True, exist_ok=True)
    (dest / name / version / "payload.txt").write_bytes(data)
    manifest = {"name": name, "version": version, "origin": origin_key, "integrity": actual}
    (dest / name / version / "install.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return {"outcome": "SUCCESS", "installed": manifest, "tree_sha256": dest_tree_hash(dest), "dest": str(dest)}


def install_confused_mutant(lockfile: dict[str, Any], dest: Path, registries: dict[str, Path]) -> dict[str, Any]:
    """Defect: ignore the origin pin, pick the highest version from ANY registry."""
    name = str(lockfile.get("name") or "")
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)

    def vkey(v: str) -> tuple:
        return tuple(int(x) if x.isdigit() else x for x in v.split("."))

    best: tuple[str, str, Path] | None = None
    for origin_key, root in registries.items():
        for version in _versions(root, name):
            if best is None or vkey(version) > vkey(best[0]):
                best = (version, origin_key, root)
    if best is None:
        raise ResolutionRefused("NOT_FOUND", {"name": name})
    version, origin_key, root = best
    got = _registry_get(root, name, version)
    assert got is not None
    data, actual = got
    (dest / name / version).mkdir(parents=True, exist_ok=True)
    (dest / name / version / "payload.txt").write_bytes(data)
    return {
        "outcome": "SUCCESS",
        "installed": {"name": name, "version": version, "origin": origin_key, "integrity": actual},
        "tree_sha256": dest_tree_hash(dest),
        "dest": str(dest),
    }
