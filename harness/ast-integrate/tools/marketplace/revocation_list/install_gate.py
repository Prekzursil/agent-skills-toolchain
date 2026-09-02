"""Install-time revocation gate (IMP-0079).

:func:`install` is the one call an installer makes.  It asks the
:class:`~tools.marketplace.revocation_list.revocation.RevocationClient` for a
decision on ``package_id@version`` signed by ``key_id`` and

* on ``REFUSE`` places **nothing** - not even the package directory - and
  returns the decision so the caller can surface the reason;
* on ``ALLOW`` writes the payload atomically to
  ``<dest>/<package_id>/<version>/payload.bin`` and returns how many bytes
  landed, together with the decision's degrade context (``list_state``,
  ``warnings``) which the caller must surface alongside its own result.

Anything that is not an explicit ``ALLOW`` refuses (fail closed).  The gate
never talks to the network itself and never decides revocation on its own: the
client's policy (verified live list, cached list when unreachable or rejected,
STALE recorded durably) is the single source of truth.

:func:`census_payloads` is the independent instrument the probes use: a sorted
list of every non-directory entry under ``dest``, so a refused install that
leaked a file - or a torn write that left a temporary - is visible regardless
of what the returned objects claim.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .degrade import atomic_write_bytes
from .revocation import ALLOW, RevocationDecision, sha256_hex

__all__ = [
    "DEFAULT_PAYLOAD_NAME",
    "InstallGateError",
    "InstallRefused",
    "InstallRequest",
    "InstallResult",
    "InvalidInstallRequest",
    "census_payloads",
    "install",
    "install_or_raise",
]

DEFAULT_PAYLOAD_NAME = "payload.bin"

# One path component: no separators, no NUL, never "." or "..", no leading dot.
_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+~-]{0,127}$")


class InstallGateError(Exception):
    """Base class for install-gate failures."""


class InvalidInstallRequest(InstallGateError, ValueError):
    """The request cannot be turned into a safe filesystem placement."""


class InstallRefused(InstallGateError):
    """Raised by :func:`install_or_raise` when the revocation decision is not ``ALLOW``."""

    def __init__(self, result: InstallResult) -> None:
        super().__init__(f"{result.request.package_id}@{result.request.version}: {result.decision.reason}")
        self.result = result


def _component(value: object, what: str) -> str:
    if not isinstance(value, str):
        raise InvalidInstallRequest(f"{what} must be a string, not {type(value).__name__}")
    if not _COMPONENT_RE.match(value):
        raise InvalidInstallRequest(
            f"{what} {value!r} is not a safe path component "
            "(alphanumeric start; letters, digits, '.', '_', '+', '~', '-'; max 128 chars)"
        )
    return value


@dataclass(frozen=True)
class InstallRequest:
    """What an installer wants to place: ``package_id@version`` from publisher ``key_id`` with ``payload``."""

    package_id: str
    version: str
    key_id: str | None
    payload: bytes

    def __post_init__(self) -> None:
        _component(self.package_id, "package_id")
        _component(self.version, "version")
        if self.key_id is not None and (not isinstance(self.key_id, str) or not self.key_id.strip()):
            raise InvalidInstallRequest("key_id must be a non-empty string or None")
        if not isinstance(self.payload, (bytes, bytearray, memoryview)):
            raise InvalidInstallRequest(
                f"payload must be bytes, not {type(self.payload).__name__}"
            )
        object.__setattr__(self, "payload", bytes(self.payload))

    @property
    def relative_dir(self) -> PurePosixPath:
        """``<package_id>/<version>`` - where the payload lands below ``dest``."""
        return PurePosixPath(self.package_id) / self.version

    @property
    def payload_sha256(self) -> str:
        """Hex SHA-256 of the payload bytes."""
        return sha256_hex(self.payload)

    def target_path(self, dest: Path | str, payload_name: str = DEFAULT_PAYLOAD_NAME) -> Path:
        """Absolute placement path for this request under ``dest``."""
        return Path(dest) / self.package_id / self.version / _component(payload_name, "payload_name")

    def as_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "version": self.version,
            "key_id": self.key_id,
            "payload_bytes": len(self.payload),
            "payload_sha256": self.payload_sha256,
        }


@dataclass(frozen=True)
class InstallResult:
    """Outcome of one :func:`install`: the decision plus what actually landed on disk."""

    request: InstallRequest
    decision: RevocationDecision
    placed: bool
    placed_bytes: int
    path: Path | None

    @property
    def refused(self) -> bool:
        return not self.placed

    @property
    def list_state(self) -> str:
        return self.decision.list_state

    @property
    def warnings(self) -> list[str]:
        return list(self.decision.warnings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.as_dict(),
            "decision": self.decision.as_dict(),
            "placed": self.placed,
            "placed_bytes": self.placed_bytes,
            "relative_path": (
                self.request.relative_dir.joinpath(self.path.name).as_posix()
                if self.path is not None
                else None
            ),
        }


def _decide(client: object, request: InstallRequest) -> RevocationDecision:
    check = getattr(client, "check", None)
    if not callable(check):
        raise TypeError("client must provide check(package_id, version, key_id)")
    decision = check(request.package_id, request.version, request.key_id)
    if not isinstance(decision, RevocationDecision):
        raise TypeError(
            f"client.check must return a RevocationDecision, not {type(decision).__name__}"
        )
    return decision


def install(
    client: object,
    request: InstallRequest,
    dest: Path | str,
    *,
    payload_name: str = DEFAULT_PAYLOAD_NAME,
) -> InstallResult:
    """Gate one install on the revocation decision and place the payload only on ``ALLOW``.

    Refusals touch nothing under ``dest``.  An allowed payload is written with
    :func:`~tools.marketplace.revocation_list.degrade.atomic_write_bytes`
    (temporary file, fsync, rename) so a crash or a full disk leaves either the
    complete file or no file - never a partial payload.  Re-installing the same
    ``package_id@version`` replaces the payload atomically.
    """
    if not isinstance(request, InstallRequest):
        raise TypeError(f"request must be an InstallRequest, not {type(request).__name__}")
    _component(payload_name, "payload_name")
    dest_path = Path(dest)
    decision = _decide(client, request)
    if decision.action != ALLOW:
        return InstallResult(request=request, decision=decision, placed=False, placed_bytes=0, path=None)
    target = request.target_path(dest_path, payload_name)
    atomic_write_bytes(target, request.payload)
    return InstallResult(
        request=request,
        decision=decision,
        placed=True,
        placed_bytes=len(request.payload),
        path=target,
    )


def install_or_raise(
    client: object,
    request: InstallRequest,
    dest: Path | str,
    *,
    payload_name: str = DEFAULT_PAYLOAD_NAME,
) -> InstallResult:
    """Like :func:`install` but raises :class:`InstallRefused` instead of returning a refusal."""
    result = install(client, request, dest, payload_name=payload_name)
    if not result.placed:
        raise InstallRefused(result)
    return result


def census_payloads(dest: Path | str) -> list[str]:
    """Sorted POSIX-relative paths of every non-directory entry under ``dest`` (``[]`` if absent).

    Symlinked directories are not followed, and nothing is filtered: stray
    temporary files or leaked payloads from a refused install show up here,
    which is the point of an independent census.
    """
    root = Path(dest)
    if not root.is_dir():
        return []
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        # Symlinks to directories are reported as entries, not descended into.
        for name in list(dirnames):
            if (base / name).is_symlink():
                dirnames.remove(name)
                found.append((base / name).relative_to(root).as_posix())
        for name in filenames:
            found.append((base / name).relative_to(root).as_posix())
    return sorted(found)
