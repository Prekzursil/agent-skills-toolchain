"""Four lifecycle operations and their declared change sets.

Package files are the only paths a correct operation may create, mutate,
or remove. Owner-authored paths are never in a correct declared set.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from walker import census, safe_relpath

V1 = {
    "pkg/manifest.json": b'{"version": "1.0.0", "name": "ast-canary"}\n',
    "pkg/hooks/pre-tool.json": b'{"event": "pre-tool", "v": 1}\n',
    "pkg/rules/base.md": b"# package rule v1\n",
    "pkg/bin/cli.py": b'print("v1")\n',
}
V2 = {
    "pkg/manifest.json": b'{"version": "2.0.0", "name": "ast-canary"}\n',
    "pkg/hooks/pre-tool.json": V1["pkg/hooks/pre-tool.json"],
    "pkg/rules/base.md": V1["pkg/rules/base.md"],
    "pkg/bin/cli.py": b'print("v2")\n',
    "pkg/migrations/001.json": b'{"id": "001", "from": "1.0.0", "to": "2.0.0"}\n',
}
PACKAGE_RELS = tuple(V1.keys())
UPGRADE_CREATE = ("pkg/migrations/001.json",)
UPGRADE_MUTATE = ("pkg/manifest.json", "pkg/bin/cli.py")


@dataclass(frozen=True)
class ChangeSet:
    creates: tuple[str, ...]
    mutates: tuple[str, ...]
    removes: tuple[str, ...]

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "creates": list(self.creates),
            "mutates": list(self.mutates),
            "removes": list(self.removes),
        }

    def all_paths(self) -> set[str]:
        return set(self.creates) | set(self.mutates) | set(self.removes)


INSTALL_DECLARED = ChangeSet(creates=PACKAGE_RELS, mutates=(), removes=())
UPGRADE_DECLARED = ChangeSet(
    creates=UPGRADE_CREATE, mutates=UPGRADE_MUTATE, removes=()
)
ROLLBACK_DECLARED = ChangeSet(
    creates=(), mutates=UPGRADE_MUTATE, removes=UPGRADE_CREATE
)
UNINSTALL_DECLARED = ChangeSet(
    creates=(),
    mutates=(),
    removes=PACKAGE_RELS + UPGRADE_CREATE,
)

OPS: dict[str, ChangeSet] = {
    "install": INSTALL_DECLARED,
    "upgrade": UPGRADE_DECLARED,
    "rollback": ROLLBACK_DECLARED,
    "uninstall": UNINSTALL_DECLARED,
}


def _write_rel(profile: Path, rel: str, data: bytes) -> None:
    dest = profile.joinpath(*rel.split("/"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def _unlink_rel(profile: Path, rel: str) -> None:
    dest = profile.joinpath(*rel.split("/"))
    if dest.is_file() or dest.is_fifo():
        dest.unlink()


def apply_install(profile: Path) -> None:
    for rel, data in V1.items():
        _write_rel(profile, rel, data)


def apply_upgrade(profile: Path) -> None:
    for rel, data in V2.items():
        _write_rel(profile, rel, data)


def apply_rollback(profile: Path) -> None:
    for rel, data in V1.items():
        _write_rel(profile, rel, data)
    _unlink_rel(profile, "pkg/migrations/001.json")


def apply_uninstall(profile: Path) -> None:
    for rel in UNINSTALL_DECLARED.removes:
        _unlink_rel(profile, rel)


def apply_install_deletes_owner(profile: Path, owner_rel: str) -> None:
    """Broken installer: declared install, then deletes a seeded owner file."""
    apply_install(profile)
    _unlink_rel(profile, owner_rel)


def apply_uninstall_casefold_wipe(profile: Path) -> None:
    """Broken uninstall: case-insensitive delete, destroying the owner sibling."""
    declared_cf = {p.casefold() for p in UNINSTALL_DECLARED.removes}
    snap = census(profile)
    for rel in list(snap):
        if rel.casefold() in declared_cf:
            _unlink_rel(profile, rel)


APPLICATORS = {
    "install": apply_install,
    "upgrade": apply_upgrade,
    "rollback": apply_rollback,
    "uninstall": apply_uninstall,
}


def join_rel(profile: Path, rel: str) -> Path:
    return profile.joinpath(*rel.split("/"))


def rel_of(profile: Path, path: Path) -> str:
    return safe_relpath(path, profile)
