#!/usr/bin/env python3
"""Path classification for the rollback contract.

CreationSet is the only set an inverse may target. Preserve sets are disjoint
from CreationSet so user data cannot be named as an inverse target.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def _fs(items: Iterable[str]) -> frozenset[str]:
    return frozenset(p.replace("\\", "/") for p in items)


# Installer-created (managed) paths. Inverse may restore or unlink only these.
CREATION_PATHS = _fs(
    (
        "plugin.json",
        "hooks/hook.pre-tool.json",
        "commands/cmd.builtin.json",
        "skills/skill.shipped.md",
        "config/harness.json",
        "plugin-extra.json",  # created at install; backup.existed=false
    )
)

VERSION_PATHS = _fs(("plugin.json", "skills/skill.shipped.md"))
CONFIG_PATHS = _fs(("config/harness.json", "hooks/hook.pre-tool.json"))

OWNER_AUTHORED_PATHS = _fs(("owner/hand-edit.md",))
USER_DATA_PATHS = _fs(
    (
        "data/user-notes.txt",
        "data/user-notes-after-install.txt",
        "settings/user-key.json",
    )
)
USER_COMMAND_PATHS = _fs(("commands/cmd.user-owned.json",))
PREEXISTING_PATHS = _fs(
    (
        "commands/cmd.user-owned.json",
        "skills/skill.user.md",
        "settings/user-key.json",
    )
)
MCP_PATHS = _fs(("mcp/curation.json",))
CREDENTIAL_PATHS = _fs(("credentials/store.synthetic.json",))

PRESERVE_PATHS = (
    OWNER_AUTHORED_PATHS
    | USER_DATA_PATHS
    | USER_COMMAND_PATHS
    | PREEXISTING_PATHS
    | MCP_PATHS
    | CREDENTIAL_PATHS
)

# Construction invariant: preserve ∩ creation must be empty.
if PRESERVE_PATHS & CREATION_PATHS:
    raise RuntimeError(
        "ledger construction failure: preserve paths overlap CreationSet: "
        + ",".join(sorted(PRESERVE_PATHS & CREATION_PATHS))
    )


class ContractViolation(Exception):
    """Inverse named a path the installer did not create."""


@dataclass(frozen=True)
class CreationSet:
    """Installer-created paths. The only legal inverse domain."""

    paths: frozenset[str]

    def __contains__(self, path: object) -> bool:
        return isinstance(path, str) and path.replace("\\", "/") in self.paths

    def __iter__(self):
        return iter(sorted(self.paths))

    def __len__(self) -> int:
        return len(self.paths)


@dataclass(frozen=True)
class InverseAction:
    path: str
    kind: str  # restore-bytes | unlink-created
    backup_sha256: str | None


@dataclass(frozen=True)
class InversePlan:
    """By construction: every action.path is in CreationSet. No other constructor."""

    actions: tuple[InverseAction, ...]
    creation: CreationSet

    @classmethod
    def build(
        cls,
        creation: CreationSet,
        actions: Iterable[InverseAction],
    ) -> "InversePlan":
        frozen = tuple(actions)
        for act in frozen:
            rel = act.path.replace("\\", "/")
            if rel not in creation:
                raise ContractViolation(
                    f"inverse target {rel!r} is not in CreationSet; "
                    "11347 would otherwise be possible by convention"
                )
            if act.kind not in {"restore-bytes", "unlink-created"}:
                raise ContractViolation(f"unknown inverse kind {act.kind!r}")
        return cls(actions=frozen, creation=creation)


@dataclass(frozen=True)
class Ledger:
    creation: CreationSet
    version: frozenset[str]
    config: frozenset[str]
    owner_authored: frozenset[str]
    user_data: frozenset[str]
    user_commands: frozenset[str]
    preexisting: frozenset[str]
    mcp: frozenset[str]
    credentials: frozenset[str]

    @property
    def preserve(self) -> frozenset[str]:
        return (
            self.owner_authored
            | self.user_data
            | self.user_commands
            | self.preexisting
            | self.mcp
            | self.credentials
        )

    def assert_disjoint(self) -> None:
        overlap = self.creation.paths & self.preserve
        if overlap:
            raise ContractViolation(
                "CreationSet overlaps preserve set: " + ",".join(sorted(overlap))
            )


def default_ledger() -> Ledger:
    led = Ledger(
        creation=CreationSet(CREATION_PATHS),
        version=VERSION_PATHS,
        config=CONFIG_PATHS,
        owner_authored=OWNER_AUTHORED_PATHS,
        user_data=USER_DATA_PATHS,
        user_commands=USER_COMMAND_PATHS,
        preexisting=PREEXISTING_PATHS,
        mcp=MCP_PATHS,
        credentials=CREDENTIAL_PATHS,
    )
    led.assert_disjoint()
    return led
