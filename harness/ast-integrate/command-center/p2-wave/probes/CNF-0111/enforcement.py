"""Runtime permission gate used as the detector-control instrument.

The product worktree has no IMP-0059 interceptor. This gate is the variable
the catalog asks us to isolate: same actions, grant present vs absent.
"""
from __future__ import annotations

from typing import Iterable

PERMISSIONS = (
    "filesystem",
    "network",
    "process-spawn",
    "credential-read",
)

DENY_CODE = {
    "filesystem": "FS-DENIED",
    "network": "NET-DENIED",
    "process-spawn": "PROC-DENIED",
    "credential-read": "CRED-DENIED",
}


class PermissionDenied(Exception):
    def __init__(self, permission: str, action: str, code: str) -> None:
        self.permission = permission
        self.action = action
        self.code = code
        super().__init__(f"{code}: undeclared {permission} action {action}")


class Gate:
    """Call-time enforcer. A metadata-only permission set is a NullGate."""

    def __init__(
        self,
        declared: Iterable[str],
        *,
        enabled: bool = True,
        enforce_containment: bool = True,
    ) -> None:
        extra = [p for p in declared if p not in PERMISSIONS]
        if extra:
            raise ValueError(f"unknown permissions: {extra}")
        self.declared = frozenset(declared)
        self.enabled = enabled
        self.enforce_containment = enforce_containment
        self.log: list[dict] = []

    def check(self, permission: str, action: str) -> None:
        record = {
            "permission": permission,
            "action": action,
            "declared": permission in self.declared,
            "enabled": self.enabled,
        }
        self.log.append(record)
        if not self.enabled:
            return
        if permission not in self.declared:
            raise PermissionDenied(
                permission, action, DENY_CODE.get(permission, "PERM-DENIED")
            )

    def deny_outside_root(self, action: str = "write-outside-root") -> None:
        if not self.enabled or not self.enforce_containment:
            return
        raise PermissionDenied("filesystem", action, "FS-OUTSIDE-ROOT")


class NullGate(Gate):
    """Product fail-open: declarations are recorded, never enforced."""

    def __init__(self, declared: Iterable[str]) -> None:
        super().__init__(declared, enabled=False, enforce_containment=False)
