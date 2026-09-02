#!/usr/bin/env python3
"""Lockfile-pinned origin+integrity resolver (TST-0219 SUT).

A private package name is satisfied only from the lockfile-pinned origin
after the integrity hash matches. A public mirror offering the same name
is refused by name. A lockfile without an origin pin fails closed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

PKG = "acme-internal-sdk"
PRIVATE_ORIGIN = "https://registry.private.example/acme-internal-sdk"
PUBLIC_ORIGIN = "https://registry.public.example/acme-internal-sdk"
PRIVATE_VERSION = "1.0.0"
PUBLIC_VERSION = "9.9.9"
PRIVATE_PAYLOAD = b"PRIVATE-ACME-INTERNAL-SDK-v1.0.0\ncanonical-bytes\n"
PUBLIC_PAYLOAD = b"PUBLIC-CONFUSION-PAYLOAD-MALICIOUS-v9.9.9\nnot-private\n"
INSTALLED_NAME = "acme-internal-sdk.bin"

CODE_OK = "OK"
CODE_ORIGIN_PIN_MISSING = "ORIGIN_PIN_MISSING"
CODE_INTEGRITY_PIN_MISSING = "INTEGRITY_PIN_MISSING"
CODE_LOCK_MISSING = "LOCK_MISSING"
CODE_ORIGIN_UNREACHABLE = "ORIGIN_UNREACHABLE"
CODE_INTEGRITY_MISMATCH = "INTEGRITY_MISMATCH"
CODE_DEPENDENCY_CONFUSION = "DEPENDENCY_CONFUSION"
CODE_PACKAGE_ABSENT = "PACKAGE_ABSENT"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def integrity_tag(data: bytes) -> str:
    return "sha256:" + sha256_hex(data)


def census(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = sha256_hex(path.read_bytes())
    return out


def tree_hash(root: Path) -> str:
    blob = json.dumps(census(root), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_hex(blob)


EMPTY_TREE_HASH = sha256_hex(b"{}")


@dataclass(frozen=True)
class Artifact:
    name: str
    version: str
    origin: str
    payload: bytes

    @property
    def sha256(self) -> str:
        return sha256_hex(self.payload)

    @property
    def integrity(self) -> str:
        return integrity_tag(self.payload)


@dataclass
class Registry:
    origin: str
    artifacts: dict[str, Artifact] = field(default_factory=dict)

    def put(self, art: Artifact) -> None:
        self.artifacts[art.name] = art

    def get(self, name: str) -> Artifact | None:
        return self.artifacts.get(name)


@dataclass(frozen=True)
class ResolveResult:
    ok: bool
    code: str
    message: str
    origin_used: str | None
    artifact_sha256: str | None
    tree_hash: str
    census: dict[str, str]
    wrote_any: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "message": self.message,
            "origin_used": self.origin_used,
            "artifact_sha256": self.artifact_sha256,
            "tree_hash": self.tree_hash,
            "census": dict(self.census),
            "wrote_any": self.wrote_any,
        }


def _fail(
    dest: Path,
    code: str,
    message: str,
    *,
    before: dict[str, str] | None = None,
) -> ResolveResult:
    after = census(dest)
    return ResolveResult(
        ok=False,
        code=code,
        message=message,
        origin_used=None,
        artifact_sha256=None,
        tree_hash=tree_hash(dest),
        census=after,
        wrote_any=bool(after) and after != (before or {}),
    )


def lock_entry(lock: Mapping[str, Any], name: str) -> dict[str, Any] | None:
    packages = lock.get("packages")
    if not isinstance(packages, dict):
        return None
    entry = packages.get(name)
    return entry if isinstance(entry, dict) else None


def pinned_lockfile(art: Artifact) -> dict[str, Any]:
    return {
        "lockfileVersion": 1,
        "packages": {
            art.name: {
                "version": art.version,
                "origin": art.origin,
                "integrity": art.integrity,
            }
        },
    }


def unpinned_lockfile(art: Artifact) -> dict[str, Any]:
    """Integrity present, origin pin absent — the catalog negative control."""
    return {
        "lockfileVersion": 1,
        "packages": {
            art.name: {
                "version": art.version,
                "integrity": art.integrity,
            }
        },
    }


def origin_only_lockfile(art: Artifact) -> dict[str, Any]:
    return {
        "lockfileVersion": 1,
        "packages": {
            art.name: {
                "version": art.version,
                "origin": art.origin,
            }
        },
    }


def _write_payload(dest: Path, payload: bytes) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / INSTALLED_NAME).write_bytes(payload)


def resolve_install(
    lock: Mapping[str, Any],
    name: str,
    registries: Mapping[str, Registry],
    dest: Path,
    *,
    offered_origin: str | None = None,
) -> ResolveResult:
    """Install `name` from the lockfile-pinned origin only.

    `offered_origin` models a caller trying to satisfy the name from a
    specific registry. If that origin is not the pin, refuse.
    """
    before = census(dest)
    entry = lock_entry(lock, name)
    if entry is None:
        return _fail(
            dest,
            CODE_LOCK_MISSING,
            f"ERROR: {CODE_LOCK_MISSING}: package {name} is not in the lockfile",
            before=before,
        )
    origin = entry.get("origin")
    integrity = entry.get("integrity")
    if not isinstance(origin, str) or not origin.strip():
        return _fail(
            dest,
            CODE_ORIGIN_PIN_MISSING,
            (
                f"ERROR: {CODE_ORIGIN_PIN_MISSING}: lockfile for {name} has no "
                "registry origin pin; refusing to satisfy the name from any mirror"
            ),
            before=before,
        )
    origin = origin.strip()
    if not isinstance(integrity, str) or not integrity.strip():
        return _fail(
            dest,
            CODE_INTEGRITY_PIN_MISSING,
            (
                f"ERROR: {CODE_INTEGRITY_PIN_MISSING}: lockfile for {name} has "
                f"origin={origin} but no integrity hash"
            ),
            before=before,
        )
    integrity = integrity.strip()

    if offered_origin is not None and offered_origin.strip() != origin:
        offered = offered_origin.strip()
        return _fail(
            dest,
            CODE_DEPENDENCY_CONFUSION,
            (
                f"ERROR: {CODE_DEPENDENCY_CONFUSION}: refusing to satisfy "
                f"package {name} from public/offered origin={offered}; "
                f"lockfile pins origin={origin} integrity={integrity}"
            ),
            before=before,
        )

    registry = registries.get(origin)
    if registry is None:
        return _fail(
            dest,
            CODE_ORIGIN_UNREACHABLE,
            (
                f"ERROR: {CODE_ORIGIN_UNREACHABLE}: pinned origin={origin} "
                f"for package {name} is not a configured registry"
            ),
            before=before,
        )
    art = registry.get(name)
    if art is None:
        return _fail(
            dest,
            CODE_PACKAGE_ABSENT,
            f"ERROR: {CODE_PACKAGE_ABSENT}: {name} missing at origin={origin}",
            before=before,
        )
    got = integrity_tag(art.payload)
    if got != integrity:
        return _fail(
            dest,
            CODE_INTEGRITY_MISMATCH,
            (
                f"ERROR: {CODE_INTEGRITY_MISMATCH}: package {name} at "
                f"origin={origin} integrity got={got} want={integrity}"
            ),
            before=before,
        )
    _write_payload(dest, art.payload)
    after = census(dest)
    return ResolveResult(
        ok=True,
        code=CODE_OK,
        message=(
            f"OK: installed {name}@{art.version} from origin={origin} "
            f"integrity={integrity} sha256={art.sha256}"
        ),
        origin_used=origin,
        artifact_sha256=art.sha256,
        tree_hash=tree_hash(dest),
        census=after,
        wrote_any=True,
    )


def confused_install(
    lock: Mapping[str, Any],
    name: str,
    registries: Mapping[str, Registry],
    dest: Path,
) -> ResolveResult:
    """Known-broken resolver: highest version across all origins, ignore pin.

    Detector control: proves the public artifact is live and would be
    selected without origin pinning. Must not be used as the SUT.
    """
    del lock  # mutant ignores the lock origin pin on purpose
    candidates: list[Artifact] = []
    for reg in registries.values():
        art = reg.get(name)
        if art is not None:
            candidates.append(art)
    if not candidates:
        return _fail(
            dest,
            CODE_PACKAGE_ABSENT,
            f"ERROR: confused resolver found no candidates for {name}",
        )

    def ver_key(a: Artifact) -> tuple:
        parts = []
        for piece in a.version.split("."):
            try:
                parts.append((0, int(piece)))
            except ValueError:
                parts.append((1, piece))
        return tuple(parts)

    chosen = max(candidates, key=ver_key)
    _write_payload(dest, chosen.payload)
    after = census(dest)
    return ResolveResult(
        ok=True,
        code=CODE_OK,
        message=(
            f"MUTANT: installed {name}@{chosen.version} from origin={chosen.origin} "
            "(ignored lock origin pin)"
        ),
        origin_used=chosen.origin,
        artifact_sha256=chosen.sha256,
        tree_hash=tree_hash(dest),
        census=after,
        wrote_any=True,
    )


def make_world() -> dict[str, Any]:
    private = Artifact(PKG, PRIVATE_VERSION, PRIVATE_ORIGIN, PRIVATE_PAYLOAD)
    public = Artifact(PKG, PUBLIC_VERSION, PUBLIC_ORIGIN, PUBLIC_PAYLOAD)
    priv_reg = Registry(PRIVATE_ORIGIN)
    pub_reg = Registry(PUBLIC_ORIGIN)
    priv_reg.put(private)
    pub_reg.put(public)
    registries = {PRIVATE_ORIGIN: priv_reg, PUBLIC_ORIGIN: pub_reg}
    return {
        "package": PKG,
        "private": private,
        "public": public,
        "registries": registries,
        "pinned_lock": pinned_lockfile(private),
        "unpinned_lock": unpinned_lockfile(private),
        "origin_only_lock": origin_only_lockfile(private),
        "private_sha256": private.sha256,
        "public_sha256": public.sha256,
        "private_integrity": private.integrity,
        "public_integrity": public.integrity,
        "empty_tree_hash": EMPTY_TREE_HASH,
    }
