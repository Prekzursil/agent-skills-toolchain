"""A3 marketplace client: every content-execution path crosses the choke.

execute_package_content is the sink. It is reached only from _after_choke,
which calls verify_package first. Public lifecycle functions do not call
the sink directly. There is no public-registry fallback.
"""
from __future__ import annotations

import hashlib
from typing import Any

from verify import verify_package

PUBLIC_EXECUTE_PATHS = (
    "install_from_index",
    "install_from_export",
    "upgrade",
    "execute_cached",
    "rollback_restore",
)


def execute_package_content(content: bytes) -> dict[str, str]:
    """Sink: record that package bytes would run. Does not eval or exec."""
    return {"executed": "yes", "sha256": hashlib.sha256(content).hexdigest()}


def _after_choke(
    package: dict[str, Any],
    lockfile: dict[str, Any],
    *,
    now: int,
    key: bytes,
) -> dict[str, Any]:
    decision = verify_package(package, lockfile, now=now, key=key)
    if not decision.get("allow"):
        return {"executed": False, "decision": decision}
    from verify import content_bytes

    sink = execute_package_content(content_bytes(package))
    return {"executed": True, "decision": decision, "sink": sink}


def install_from_index(
    package: dict[str, Any], lockfile: dict[str, Any], *, now: int, key: bytes
) -> dict[str, Any]:
    return _after_choke(package, lockfile, now=now, key=key)


def install_from_export(
    package: dict[str, Any], lockfile: dict[str, Any], *, now: int, key: bytes
) -> dict[str, Any]:
    return _after_choke(package, lockfile, now=now, key=key)


def upgrade(
    package: dict[str, Any], lockfile: dict[str, Any], *, now: int, key: bytes
) -> dict[str, Any]:
    return _after_choke(package, lockfile, now=now, key=key)


def execute_cached(
    package: dict[str, Any], lockfile: dict[str, Any], *, now: int, key: bytes
) -> dict[str, Any]:
    return _after_choke(package, lockfile, now=now, key=key)


def rollback_restore(
    package: dict[str, Any], lockfile: dict[str, Any], *, now: int, key: bytes
) -> dict[str, Any]:
    return _after_choke(package, lockfile, now=now, key=key)
