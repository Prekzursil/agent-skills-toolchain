"""Collections: a named set of packages with a single resolved lockfile (IMP-0104).

Installing a collection is one atomic, reproducible operation: members are
resolved together, the lockfile is canonical (member-order independent), and
installation is all-or-nothing -- a failure or simulated kill after the first
member write rolls back to zero package files and no lock. An incompatible
member is reported at collection-DEFINITION time, never at install time.

Restored by the w4s8 resume session (2026-10-26) to the recorded IMP-0104
contract after the file had been reduced to a generated no-op surface stub.
Public API names match the stub so importers keep working.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class CollectionDefinitionError(ValueError):
    """A collection definition is invalid (unknown member or incompatible pair)."""


class InstallRolledBack(RuntimeError):
    """A simulated mid-install kill occurred; the target was rolled back."""


DEFAULT_INCOMPATIBILITIES = frozenset({frozenset({"capstone", "keystone"})})

RE_TOOLCHAIN_MEMBERS = ("binwalk", "ghidra", "radare2")

DEFAULT_DEMO_VERSIONS = {
    "binwalk": "2.3.3",
    "ghidra": "11.0.3",
    "radare2": "5.9.2",
    "capstone": "5.0.1",
    "keystone": "0.9.2",
    "demo-kit": "1.1.0",
    "sibling-kit": "1.1.0",
}


@dataclass
class CollectionDefinition:
    name: str
    members: tuple
    resolved_versions: dict = field(default_factory=dict)

    @property
    def member_set(self):
        return frozenset(self.members)


def build_demo_index():
    packages = {}
    for name, version in sorted(DEFAULT_DEMO_VERSIONS.items()):
        packages[name] = {"versions": [version], "latest": version}
    return {"packages": packages}


def _incompatible_pairs(index):
    pairs = {frozenset(p) for p in DEFAULT_INCOMPATIBILITIES}
    extra = (index or {}).get("incompatibilities") or []
    for pair in extra:
        try:
            pairs.add(frozenset(str(x) for x in pair))
        except TypeError:
            continue
    return pairs


def define_collection(index, members, name="collection"):
    packages = (index or {}).get("packages") or {}
    unknown = sorted(m for m in members if m not in packages)
    if unknown:
        raise CollectionDefinitionError("unknown members: %s" % unknown)
    member_set = set(members)
    for pair in _incompatible_pairs(index):
        if pair <= member_set:
            raise CollectionDefinitionError(
                "incompatible members at definition time: " + ", ".join(sorted(pair))
            )
    resolved = {}
    for m in sorted(set(members)):
        info = packages[m]
        version = info.get("latest") or (info.get("versions") or ["0.0.0"])[0]
        resolved[m] = str(version)
    return CollectionDefinition(name=name, members=tuple(sorted(set(members))), resolved_versions=resolved)


def re_toolchain_collection(index=None):
    return define_collection(
        index if index is not None else build_demo_index(),
        list(RE_TOOLCHAIN_MEMBERS),
        name="re-toolchain",
    )


def resolve_lockfile(definition, index=None):
    resolved = {m: definition.resolved_versions[m] for m in sorted(definition.members)}
    lock = {
        "name": definition.name,
        "members": sorted(definition.members),
        "resolved": resolved,
    }
    canonical = json.dumps(lock, sort_keys=True, separators=(",", ":"))
    lock["lockfile_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return lock


def dumps_lockfile(lockfile):
    body = {k: v for k, v in lockfile.items() if k != "lockfile_sha256"}
    return (json.dumps(body, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _rollback(target):
    for p in target.glob("*.pkg"):
        p.unlink()
    lock = target / "collection-lock.json"
    if lock.is_file():
        lock.unlink()


def install_collection(definition, index, target, crash_after_first_write=False):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    staged = target / ".staged-install"
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir(parents=True)
    lockfile = resolve_lockfile(definition, index)
    written = []
    try:
        for member in definition.members:
            if crash_after_first_write and written:
                raise InstallRolledBack(
                    "simulated kill after first write (wrote %s)" % written[0]
                )
            (staged / (member + ".pkg")).write_text(
                json.dumps({"package": member, "version": definition.resolved_versions[member]}),
                encoding="utf-8",
            )
            written.append(member)
        (staged / "collection-lock.json").write_bytes(dumps_lockfile(lockfile))
        for p in sorted(staged.iterdir()):
            shutil.move(str(p), str(target / p.name))
    except Exception:
        shutil.rmtree(staged, ignore_errors=True)
        _rollback(target)
        raise
    finally:
        shutil.rmtree(staged, ignore_errors=True)
    return {
        "installed": sorted(definition.members),
        "lockfile": "collection-lock.json",
        "lockfile_sha256": lockfile["lockfile_sha256"],
        "rolled_back": False,
    }


def incompatible_collection(index, members):
    try:
        define_collection(index, members)
    except CollectionDefinitionError as exc:
        return {"ok": False, "reason": str(exc), "reported_at": "definition"}
    return {"ok": True, "reason": "", "reported_at": "definition"}


def observed_matches_guarantee(definition, target):
    target = Path(target)
    locks = list(target.glob("collection-lock.json"))
    pkgs = sorted(p.stem for p in target.glob("*.pkg"))
    return {
        "one_lockfile": len(locks) == 1,
        "member_files_match": set(pkgs) == set(definition.members),
        "observed": pkgs,
    }


__all__ = [
    "build_demo_index",
    "define_collection",
    "re_toolchain_collection",
    "CollectionDefinition",
    "CollectionDefinitionError",
    "InstallRolledBack",
    "dumps_lockfile",
    "incompatible_collection",
    "install_collection",
    "observed_matches_guarantee",
    "resolve_lockfile",
]
