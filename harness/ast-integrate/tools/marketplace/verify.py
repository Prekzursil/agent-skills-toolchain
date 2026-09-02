"""Install-time verification gates. Fail-closed.

Every gate raises :class:`GateFailure` naming the gate that refused; nothing
here places files or falls back to an unpinned blob.  :func:`run_verification`
runs the gates in :data:`VERIFY_ORDER` against the bytes of the fetched blob
and is the only verification entry point the marketplace installer calls.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from marketplace.signature import VALID, verify_signature

GATE_SIGNATURE = "GATE_SIGNATURE"
GATE_COMPATIBILITY = "GATE_COMPATIBILITY"
GATE_LOCKFILE_DIGEST = "GATE_LOCKFILE_DIGEST"
GATE_REVOCATION = "GATE_REVOCATION"
VERIFY_ORDER = ("signature", "revocation", "compatibility", "lockfile")

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class GateFailure(Exception):
    """A verification gate refused the install.

    ``gate`` names the refusing gate (one of the ``GATE_*`` constants) and
    ``reason`` carries the human-readable refusal so callers can record both
    without parsing the message.
    """

    def __init__(self, message: str, gate: str = GATE_SIGNATURE) -> None:
        super().__init__(message)
        self.gate = gate
        self.reason = message


def normalise_digest(value: Any) -> str:
    """Return the bare lower-case sha256 hex for ``sha256:<hex>``/``<hex>``/``{value}``.

    Raises ``ValueError`` for any other algorithm or a non-64-hex value.
    """
    raw: Any = value
    algorithm = "sha256"
    if isinstance(value, Mapping):
        declared = value.get("algorithm", value.get("alg"))
        if declared is not None:
            algorithm = str(declared).strip().lower()
        raw = value.get("value")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("digest must be a non-empty string")
    text = raw.strip()
    if ":" in text:
        prefix, _, text = text.partition(":")
        algorithm = prefix.strip().lower()
    if algorithm != "sha256":
        raise ValueError(f"unsupported digest algorithm {algorithm!r}")
    text = text.strip().lower()
    if not _HEX64_RE.match(text):
        raise ValueError("sha256 digest must be exactly 64 hex characters")
    return text


def blob_digest(path: str | Path) -> str:
    """sha256 hex of the blob bytes at ``path`` (streamed; the blob is never unpacked)."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_record(record: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    """Return ``record`` with its ``digest`` spelled as bare hex (the signed message).

    A record may spell the digest it signs as ``sha256:<hex>``, bare hex or
    ``{algorithm, value}``; the signature is always over the bare hex, which is
    what :func:`blob_digest` recomputes.  Anything that is not a sha256 digest
    is left untouched so :func:`marketplace.signature.verify_signature` reports
    the mismatch itself.
    """
    if not isinstance(record, Mapping):
        return record
    try:
        bare = normalise_digest(record.get("digest"))
    except ValueError:
        return record
    if record.get("digest") == bare:
        return record
    canonical = dict(record)
    canonical["digest"] = bare
    return canonical


def check_signature(digest: str, record: Mapping[str, Any] | None, store: Mapping[str, str]) -> str:
    """Refuse an unsigned, unknown-key, mismatching or forged signature record."""
    result = verify_signature(digest, _canonical_record(record), store)
    if result.status != VALID:
        raise GateFailure(result.reason or result.status, gate=GATE_SIGNATURE)
    if not result.key_id:
        raise GateFailure("valid without key id", gate=GATE_SIGNATURE)
    return result.key_id


def check_revocation(package_ref: str, key_id: str, revocation: Mapping[str, Any] | None) -> None:
    """Refuse a revoked package version or a revoked signing key."""
    if not isinstance(revocation, Mapping):
        raise GateFailure("revocation list absent; cannot prove the package is not revoked", gate=GATE_REVOCATION)
    versions = revocation.get("revoked_versions")
    keys = revocation.get("revoked_keys")
    if not isinstance(versions, list) or not isinstance(keys, list):
        raise GateFailure("revocation list malformed (revoked_versions/revoked_keys)", gate=GATE_REVOCATION)
    if package_ref in {str(v) for v in versions}:
        raise GateFailure(f"package {package_ref} is revoked", gate=GATE_REVOCATION)
    if key_id in {str(k) for k in keys}:
        raise GateFailure(f"signing key {key_id} is revoked", gate=GATE_REVOCATION)


def _version_tuple(text: Any) -> tuple[int, ...]:
    parts = str(text).strip().split(".")
    out: list[int] = []
    for part in parts:
        match = re.match(r"^\d+", part)
        if match is None:
            raise ValueError(f"unparseable version component {part!r}")
        out.append(int(match.group(0)))
    return tuple(out)


def check_compatibility(compatibility: Mapping[str, Any] | None, platform: str, client_version: str) -> None:
    """Refuse a package that does not declare the running platform or client floor."""
    if not isinstance(compatibility, Mapping):
        raise GateFailure("compatibility declaration absent", gate=GATE_COMPATIBILITY)
    platforms = compatibility.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        raise GateFailure("compatibility.platforms absent or empty", gate=GATE_COMPATIBILITY)
    if str(platform) not in {str(p) for p in platforms}:
        raise GateFailure(f"platform {platform!r} not in {sorted(map(str, platforms))}", gate=GATE_COMPATIBILITY)
    client_min = compatibility.get("client_min")
    if client_min is None:
        raise GateFailure("compatibility.client_min absent", gate=GATE_COMPATIBILITY)
    try:
        if _version_tuple(client_version) < _version_tuple(client_min):
            raise GateFailure(
                f"client {client_version} is below client_min {client_min}", gate=GATE_COMPATIBILITY
            )
    except ValueError as exc:
        raise GateFailure(f"unparseable version: {exc}", gate=GATE_COMPATIBILITY) from exc


def check_lockfile_digest(digest: str, lockfile: Mapping[str, Any] | None, package_ref: str) -> str:
    """Require an exact lockfile pin for ``package_ref`` matching the blob ``digest``.

    An absent lockfile, an absent ``packages`` object, an unpinned package or a
    malformed pin are all refusals: there is no unpinned-allow branch.
    """
    if not isinstance(lockfile, Mapping):
        raise GateFailure("lockfile absent", gate=GATE_LOCKFILE_DIGEST)
    packages = lockfile.get("packages")
    if not isinstance(packages, Mapping):
        raise GateFailure("lockfile has no packages object; refusing unpinned install", gate=GATE_LOCKFILE_DIGEST)
    entry = packages.get(package_ref)
    if not isinstance(entry, Mapping):
        raise GateFailure(f"lockfile does not pin {package_ref}", gate=GATE_LOCKFILE_DIGEST)
    try:
        pinned = normalise_digest(entry.get("digest"))
        actual = normalise_digest(digest)
    except ValueError as exc:
        raise GateFailure(f"lockfile pin unreadable: {exc}", gate=GATE_LOCKFILE_DIGEST) from exc
    if pinned != actual:
        raise GateFailure(
            f"digest mismatch for {package_ref}: blob {actual} != lockfile pin {pinned}",
            gate=GATE_LOCKFILE_DIGEST,
        )
    return pinned


def run_verification(
    blob: str | Path,
    *,
    package_ref: str,
    lockfile: Mapping[str, Any] | None,
    signature: Mapping[str, Any] | None,
    trust_store: Mapping[str, str] | None,
    revocation: Mapping[str, Any] | None,
    compatibility: Mapping[str, Any] | None,
    platform: str,
    client_version: str,
) -> dict[str, Any]:
    """Run every gate in :data:`VERIFY_ORDER` against the fetched ``blob``.

    The digest is recomputed from the blob bytes, so a cache blob mutated after
    fetch fails the signature gate (and would fail the lockfile gate).  Returns
    ``{"digest", "key_id", "package_ref", "trace"}`` where ``trace`` lists the
    gates that passed, in order.  Raises :class:`GateFailure` at the first
    refusing gate.
    """
    digest = blob_digest(blob)
    trace: list[str] = []
    key_id = check_signature(digest, signature, dict(trust_store or {}))
    trace.append("signature")
    check_revocation(package_ref, key_id, revocation)
    trace.append("revocation")
    check_compatibility(compatibility, platform, client_version)
    trace.append("compatibility")
    pinned = check_lockfile_digest(digest, lockfile, package_ref)
    trace.append("lockfile")
    if tuple(trace) != VERIFY_ORDER:
        raise GateFailure(f"gate order {trace} != {list(VERIFY_ORDER)}", gate=GATE_LOCKFILE_DIGEST)
    return {"digest": pinned, "key_id": key_id, "package_ref": package_ref, "trace": trace}


__all__ = [
    "GATE_COMPATIBILITY",
    "GATE_LOCKFILE_DIGEST",
    "GATE_REVOCATION",
    "GATE_SIGNATURE",
    "VERIFY_ORDER",
    "GateFailure",
    "blob_digest",
    "check_compatibility",
    "check_lockfile_digest",
    "check_revocation",
    "check_signature",
    "normalise_digest",
    "run_verification",
]
