"""Allowlist, deny-guard, and repo-root containment: string vs canonical.

ACCEPT = the guard treats the candidate as in-policy (allowed / not denied /
contained). REJECT = out-of-policy.

The string-comparing CONTROL is deliberately sloppy: separator-fold only, exact
equality for deny, prefix-without-slash-boundary for allow/containment. That is
the hole the catalog asks the probe to detect.
"""
from __future__ import annotations

from pathlib import Path

from winpath import FIXTURE_VOLUME, Volume, sep_fold, win_identity

ACCEPT = "ACCEPT"
REJECT = "REJECT"


def string_eq(a: str, b: str) -> bool:
    return sep_fold(a) == sep_fold(b)


def string_prefix(prefix: str, candidate: str) -> bool:
    """Separator-fold prefix with NO slash boundary (control hole)."""
    p = sep_fold(prefix).rstrip("/")
    c = sep_fold(candidate)
    if not p:
        return False
    return c == p or c.startswith(p)


def string_deny_exact(denied: str, candidate: str) -> str:
    return REJECT if string_eq(denied, candidate) else ACCEPT


def canonical_deny_exact(
    denied: str, candidate: str, volume: Volume | None = None
) -> str:
    ident_d = win_identity(denied, volume or FIXTURE_VOLUME)
    ident_c = win_identity(candidate, volume or FIXTURE_VOLUME)
    return REJECT if ident_d == ident_c else ACCEPT


def string_allow_prefix(allowed: str, candidate: str) -> str:
    return ACCEPT if string_prefix(allowed, candidate) else REJECT


def canonical_allow_prefix(
    allowed: str, candidate: str, volume: Volume | None = None
) -> str:
    vol = volume or FIXTURE_VOLUME
    a = win_identity(allowed, vol)
    c = win_identity(candidate, vol)
    if not a:
        return REJECT
    return ACCEPT if (c == a or c.startswith(a + "\\")) else REJECT


def string_contains(root: str, candidate: str) -> str:
    return ACCEPT if string_prefix(root, candidate) else REJECT


def canonical_contains(
    root: str, candidate: str, volume: Volume | None = None
) -> str:
    return canonical_allow_prefix(root, candidate, volume)


def pathlib_contains(root: str, candidate: str) -> str:
    """Estate-shaped containment: Path.parents membership, no Win32 identity.

    Components are laid onto a fake POSIX tree so the comparison is the same
    operation `test_write_all_does_not_touch_the_real_repo` uses
    (`root in path.parents`) without touching the live checkout.
    """
    def as_posix(win_path: str) -> Path:
        drive, _, rest = sep_fold(win_path).partition(":")
        parts = [p for p in rest.split("/") if p]
        base = Path("/tst0066-estate")
        if drive:
            base = base / drive.rstrip(":")
        for part in parts:
            base = base / part
        return base

    r = as_posix(root)
    c = as_posix(candidate)
    if c == r:
        return ACCEPT
    return ACCEPT if r in c.parents else REJECT
