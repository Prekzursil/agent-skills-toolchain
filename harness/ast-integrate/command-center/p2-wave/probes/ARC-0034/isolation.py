"""A5 worktree PathJail: fail-closed file IO for an isolated unit.

A5-PATH-JAIL-FAIL-CLOSED: every read the unit runtime performs is classified
against the unit worktree. Sibling worktrees and owner credential stores are
refused and appended to an isolation-denial log. Default is deny.

This is the unit-runtime contract. An unconfined subprocess can still read
sibling trees on an unsandboxed host; A5 therefore also requires an OS
sandbox (namespaces / landlock / bwrap) around the worker. The jail is not
a kernel guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Decision = Literal["allow", "sibling", "credential-store", "outside"]


class IsolationDenied(Exception):
    def __init__(self, path: str, reason: Decision, logged: bool):
        self.path = path
        self.reason = reason
        self.logged = logged
        super().__init__(f"A5-PATH-JAIL-FAIL-CLOSED {reason} path={path}")


@dataclass
class DenialRecord:
    path: str
    reason: Decision
    action: str = "refuse"


@dataclass
class PathJail:
    allowed_root: Path
    sibling_roots: list[Path] = field(default_factory=list)
    credential_stores: list[Path] = field(default_factory=list)
    log: list[DenialRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.allowed_root = Path(self.allowed_root).resolve(strict=False)
        self.sibling_roots = [Path(p).resolve(strict=False) for p in self.sibling_roots]
        self.credential_stores = [
            Path(p).resolve(strict=False) for p in self.credential_stores
        ]

    def resolve(self, path: Path | str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.allowed_root / p
        return p.resolve(strict=False)

    def _is_under(self, path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def classify(self, path: Path | str) -> Decision:
        resolved = self.resolve(path)
        for store in self.credential_stores:
            if self._is_under(resolved, store):
                return "credential-store"
        for sibling in self.sibling_roots:
            if self._is_under(resolved, sibling):
                return "sibling"
        if self._is_under(resolved, self.allowed_root):
            return "allow"
        return "outside"

    def _deny(self, resolved: Path, reason: Decision) -> None:
        rec = DenialRecord(path=str(resolved), reason=reason)
        self.log.append(rec)
        raise IsolationDenied(str(resolved), reason, logged=True)

    def open_bytes(self, path: Path | str) -> bytes:
        resolved = self.resolve(path)
        decision = self.classify(resolved)
        if decision != "allow":
            self._deny(resolved, decision)
        return resolved.read_bytes()

    def open_text(self, path: Path | str, encoding: str = "utf-8") -> str:
        return self.open_bytes(path).decode(encoding, errors="replace")
