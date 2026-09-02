"""Signed revocation-list client for the marketplace install gate (IMP-0079).

The marketplace owner publishes a ``marketplace.revocation-list/v1`` document
listing revoked publisher keys and withdrawn package versions.  Before every
install the gate asks :class:`RevocationClient` for a decision; the client

* fetches the list through a *transport* (:class:`HttpTransport` for real
  URLs; in tests any object whose ``fetch_bytes()`` returns bytes or raises
  :class:`FetchError`), retrying a bounded number of times with injectable
  back-off and sleep;
* verifies the owner's Ed25519 signature over the canonical JSON of the list
  body and validates the body against the schema (verify-only: this module
  never mints or rotates keys);
* keeps the last accepted list in a JSON cache written atomically, so an
  attacker who blocks the network or serves an unsigned, untrusted, or
  lower-sequence list cannot un-revoke anything already known;
* records every degraded decision durably on a
  :class:`~tools.marketplace.revocation_list.degrade.DegradeSink`
  (``STALE`` when the served list is not provably fresh, ``REJECTED`` when a
  fetched list failed verification) - silence is failure.

Decision policy (fail-closed on knowledge, loud on ignorance)::

    FRESH        live list verified, inside its freshness window
    STALE        live list verified but past ``expires_at``      -> enforced, STALE
    UNREACHABLE  every fetch attempt failed                      -> cache enforced, STALE
    REJECTED     live list unsigned/untrusted/malformed/rollback -> cache enforced,
                                                                    REJECTED + STALE

Anything on the effective list is ``REFUSE``; everything else is ``ALLOW``
with the warnings above attached to the decision and already on the sink.

Wire formats
------------

Signed envelope (what :func:`sign_envelope` produces and the client expects)::

    {
      "schema": "marketplace.revocation-list-envelope/v1",
      "body": { ...marketplace.revocation-list/v1 document... },
      "signature": {"algorithm": "ed25519", "key_id": "<owner key id>",
                    "signature": "<hex of the 64-byte Ed25519 signature>"}
    }

``"signatures": [...]`` (several signature objects) is accepted in place of
``"signature"``: at least one must be a valid signature by a trusted owner key,
and a trusted key whose signature does not verify rejects the whole document.
A flat document (the list body carrying its own ``"signature"`` member) is
accepted too; the signed message is then the body without that member.  The
signed message is always :func:`signing_message` = :func:`canonical_json` of
the body: ``json.dumps(body, sort_keys=True, separators=(",", ":"),
ensure_ascii=True)``.  Public keys and signatures may be supplied as hex,
base64, raw bytes or ``cryptography`` key objects (keys also as PEM).

List body (``marketplace.revocation-list/v1``)::

    {"schema": "marketplace.revocation-list/v1",
     "issued_at": "2026-08-24T00:00:00Z", "expires_at": "2026-08-25T00:00:00Z",
     "sequence": 2,
     "revoked_keys":     [{"key_id": "key-compromised", "reason": "compromised",
                           "revoked_at": "2026-08-24T00:00:00Z"}],
     "revoked_versions": [{"package_id": "pkg.evil", "version": "1.0.0",
                           "reason": "withdrawn"}]}

Cache (``cache_path``, ``marketplace.revocation-cache/v1``)::

    {"schema": "marketplace.revocation-cache/v1", "accepted_at": "...Z",
     "verified_by": "<key id>", "body_sha256": "<hex>", "body": {...}}

Install-gate contract: ``decision = client.check(package_id, version, key_id)``
and refuse when ``decision.action == REFUSE``.  ``decision.list_state``,
``decision.warnings`` and ``decision.known_revoked`` carry the degrade
information the gate must surface alongside its own result.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import http.client
import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from .degrade import (
    REJECTED,
    STALE,
    DegradeSink,
    atomic_write_bytes,
    clock_now,
    iso_utc,
    parse_iso8601,
)

try:  # the same dependency tools/marketplace/signature.py already relies on
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError:  # pragma: no cover - only where cryptography is absent
    InvalidSignature = None  # type: ignore[assignment,misc]
    serialization = None  # type: ignore[assignment]
    Ed25519PrivateKey = None  # type: ignore[assignment,misc]
    Ed25519PublicKey = None  # type: ignore[assignment,misc]

LIST_SCHEMA = "marketplace.revocation-list/v1"
ENVELOPE_SCHEMA = "marketplace.revocation-list-envelope/v1"
CACHE_SCHEMA = "marketplace.revocation-cache/v1"
ALG = "ed25519"

# List states carried on every decision.
FRESH = "FRESH"
UNREACHABLE = "UNREACHABLE"
# ``STALE`` and ``REJECTED`` are imported from ``degrade`` so the state name and
# the sink warning code are the same string.

# Decision actions.
ALLOW = "ALLOW"
REFUSE = "REFUSE"

DEFAULT_ATTEMPTS = 3
DEFAULT_BACKOFF: tuple[float, ...] = (0.5, 1.0, 2.0)
MAX_LIST_BYTES = 4 * 1024 * 1024
USER_AGENT = "ast-integrate-marketplace-revocation/1"

_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_SIGNATURE_MEMBERS = ("signature", "signatures")

__all__ = [
    "ALG",
    "ALLOW",
    "CACHE_SCHEMA",
    "DEFAULT_ATTEMPTS",
    "DEFAULT_BACKOFF",
    "ENVELOPE_SCHEMA",
    "FRESH",
    "FetchError",
    "HttpTransport",
    "LIST_SCHEMA",
    "ListSchemaError",
    "ListSequenceError",
    "ListSignatureError",
    "MAX_LIST_BYTES",
    "REFUSE",
    "REJECTED",
    "RefreshResult",
    "RevocationClient",
    "RevocationDecision",
    "RevocationList",
    "RevocationListError",
    "STALE",
    "Transport",
    "UNREACHABLE",
    "canonical_json",
    "load_private_key",
    "load_public_key",
    "parse_document",
    "sha256_hex",
    "sign_envelope",
    "signing_message",
    "split_envelope",
    "verify_owner_signatures",
]


# --------------------------------------------------------------------------- errors


class FetchError(Exception):
    """The transport could not deliver the list bytes.

    Raised for HTTP error statuses (``kind="http"``, ``status`` set), network
    failures (``"network"``), timeouts (``"timeout"``), protocol violations
    (``"protocol"``), unsupported URLs (``"url"``) and oversize bodies
    (``"too-large"``).  It is raised immediately - the transport never retries.
    """

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        status: int | None = None,
        kind: str = "network",
    ) -> None:
        super().__init__(message)
        self.url = url
        self.status = status
        self.kind = kind


class RevocationListError(Exception):
    """A fetched document cannot be accepted as the owner's revocation list."""


class ListSignatureError(RevocationListError):
    """The document is unsigned, signed by an untrusted key, or its signature does not verify."""


class ListSchemaError(RevocationListError):
    """The document is not a well-formed ``marketplace.revocation-list/v1`` body or envelope."""


class ListSequenceError(RevocationListError):
    """The document would roll the accepted list back (lower or reused sequence)."""


# --------------------------------------------------------------------------- transport


class Transport(Protocol):
    """Anything that can deliver the raw list bytes once."""

    def fetch_bytes(self) -> bytes:  # pragma: no cover - protocol
        ...


def _error_body_head(exc: urllib.error.HTTPError) -> str:
    try:
        head = exc.read(200)
    except Exception:  # noqa: BLE001 - the body is diagnostic only
        return ""
    return head.decode("utf-8", "replace")


class HttpTransport:
    """Single-shot HTTP(S) ``GET`` that returns the response body or raises loudly.

    No automatic retry, no silent fallback: a non-2xx status, a network error,
    a timeout or an oversize body all raise :class:`FetchError` right away.
    Retrying is the client's decision (bounded, with back-off), never the
    transport's.
    """

    def __init__(
        self,
        url: str,
        timeout: float | None = 10.0,
        *,
        max_bytes: int = MAX_LIST_BYTES,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url must be a non-empty string")
        if timeout is not None and float(timeout) <= 0:
            raise ValueError("timeout must be positive (seconds) or None")
        if int(max_bytes) < 1:
            raise ValueError("max_bytes must be >= 1")
        self.url = url.strip()
        self.timeout = None if timeout is None else float(timeout)
        self.max_bytes = int(max_bytes)
        self.headers = dict(headers or {})

    def __repr__(self) -> str:
        return f"HttpTransport({self.url!r}, timeout={self.timeout!r})"

    def fetch_bytes(self) -> bytes:
        """Perform one GET and return the body bytes, or raise :class:`FetchError`."""
        scheme = self.url.split(":", 1)[0].lower() if ":" in self.url else ""
        if scheme not in ("http", "https"):
            raise FetchError(
                f"unsupported URL scheme {scheme!r} in {self.url}", url=self.url, kind="url"
            )
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        headers.update(self.headers)
        request = urllib.request.Request(self.url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = int(getattr(response, "status", None) or response.getcode() or 0)
                data = response.read(self.max_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise FetchError(
                f"HTTP {exc.code} from {self.url}: {_error_body_head(exc)}",
                url=self.url,
                status=int(exc.code),
                kind="http",
            ) from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            kind = "timeout" if isinstance(reason, (socket.timeout, TimeoutError)) else "network"
            raise FetchError(
                f"{kind} error fetching {self.url}: {reason}", url=self.url, kind=kind
            ) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise FetchError(
                f"timeout after {self.timeout}s fetching {self.url}", url=self.url, kind="timeout"
            ) from exc
        except http.client.HTTPException as exc:
            raise FetchError(
                f"protocol error fetching {self.url}: {exc}", url=self.url, kind="protocol"
            ) from exc
        except OSError as exc:
            raise FetchError(
                f"network error fetching {self.url}: {exc}", url=self.url, kind="network"
            ) from exc
        if len(data) > self.max_bytes:
            raise FetchError(
                f"response from {self.url} exceeds {self.max_bytes} bytes",
                url=self.url,
                status=status,
                kind="too-large",
            )
        if not 200 <= status < 300:
            raise FetchError(
                f"HTTP {status} from {self.url}", url=self.url, status=status, kind="http"
            )
        return bytes(data)


# --------------------------------------------------------------------------- encoding


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON bytes: sorted keys, compact separators, ASCII only."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def sha256_hex(data: bytes) -> str:
    """Hex sha256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def signing_message(body: Mapping[str, Any]) -> bytes:
    """The exact bytes an owner signs: canonical JSON of ``body`` without signature members."""
    if not isinstance(body, Mapping):
        raise TypeError("body must be a mapping")
    return canonical_json({k: v for k, v in body.items() if k not in _SIGNATURE_MEMBERS})


def _decode_bytes(value: object, expected_len: int, what: str) -> bytes:
    """Decode ``value`` (raw bytes, hex or base64 text) into exactly ``expected_len`` bytes."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
    elif isinstance(value, str):
        text = value.strip()
        raw = None
        if len(text) == expected_len * 2 and _HEX_RE.match(text):
            raw = bytes.fromhex(text)
        else:
            padded = text + "=" * (-len(text) % 4)
            for candidate in (padded, padded.replace("-", "+").replace("_", "/")):
                try:
                    decoded = base64.b64decode(candidate, validate=True)
                except (binascii.Error, ValueError):
                    continue
                if len(decoded) == expected_len:
                    raw = decoded
                    break
        if raw is None:
            raise ValueError(f"{what} is not {expected_len} bytes in hex or base64")
    else:
        raise TypeError(f"{what} must be bytes or text, not {type(value).__name__}")
    if len(raw) != expected_len:
        raise ValueError(f"{what} must be {expected_len} bytes, got {len(raw)}")
    return raw


def _require_crypto() -> None:
    if Ed25519PublicKey is None:
        raise ListSignatureError(
            "the 'cryptography' package is required to verify revocation-list signatures"
        )


def load_public_key(value: object) -> Ed25519PublicKey:
    """Load an Ed25519 public key from a key object, 32 raw bytes, hex/base64 text or PEM."""
    _require_crypto()
    if isinstance(value, Ed25519PublicKey):
        return value
    pem = None
    if isinstance(value, str) and "-----BEGIN" in value:
        pem = value.encode("ascii")
    elif isinstance(value, (bytes, bytearray)) and bytes(value).lstrip().startswith(b"-----BEGIN"):
        pem = bytes(value)
    if pem is not None:
        key = serialization.load_pem_public_key(pem)
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("PEM public key is not Ed25519")
        return key
    return Ed25519PublicKey.from_public_bytes(_decode_bytes(value, 32, "public key"))


def load_private_key(value: object) -> Ed25519PrivateKey:
    """Load an Ed25519 private key from a key object, a 32-byte seed (raw/hex/base64) or PEM."""
    _require_crypto()
    if isinstance(value, Ed25519PrivateKey):
        return value
    pem = None
    if isinstance(value, str) and "-----BEGIN" in value:
        pem = value.encode("ascii")
    elif isinstance(value, (bytes, bytearray)) and bytes(value).lstrip().startswith(b"-----BEGIN"):
        pem = bytes(value)
    if pem is not None:
        key = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("PEM private key is not Ed25519")
        return key
    return Ed25519PrivateKey.from_private_bytes(_decode_bytes(value, 32, "private key seed"))


def parse_document(raw: bytes | bytearray | memoryview | str) -> dict[str, Any]:
    """Parse UTF-8 JSON into an object, rejecting duplicate keys and non-object roots."""
    if isinstance(raw, str):
        text = raw
    else:
        try:
            text = bytes(raw).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ListSchemaError(f"document is not UTF-8: {exc}") from exc
    if not text.strip():
        raise ListSchemaError("empty document")

    def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [k for k, _ in pairs]
        if len(keys) != len(set(keys)):
            raise ListSchemaError("duplicate keys in document")
        return dict(pairs)

    try:
        doc = json.loads(text, object_pairs_hook=_pairs)
    except json.JSONDecodeError as exc:
        raise ListSchemaError(f"malformed JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise ListSchemaError("document root must be a JSON object")
    return doc


def _signature_objects(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    single = doc.get("signature")
    if single is not None:
        if not isinstance(single, Mapping):
            raise ListSignatureError("'signature' must be an object")
        out.append(dict(single))
    many = doc.get("signatures")
    if many is not None:
        if not isinstance(many, list) or not all(isinstance(s, Mapping) for s in many):
            raise ListSignatureError("'signatures' must be a list of objects")
        out.extend(dict(s) for s in many)
    return out


def split_envelope(doc: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return ``(body, signatures)`` from an envelope or a flat signed body.

    Raises :class:`ListSignatureError` when no signature object is present and
    :class:`ListSchemaError` when the document is neither shape.
    """
    if not isinstance(doc, Mapping):
        raise ListSchemaError("document must be a JSON object")
    if isinstance(doc.get("body"), Mapping):
        schema = doc.get("schema")
        if schema is not None and schema != ENVELOPE_SCHEMA:
            raise ListSchemaError(f"unknown envelope schema {schema!r}")
        signatures = _signature_objects(doc)
        if not signatures:
            raise ListSignatureError("unsigned revocation list: envelope carries no signature")
        return dict(doc["body"]), signatures
    if doc.get("schema") == LIST_SCHEMA:
        signatures = _signature_objects(doc)
        if not signatures:
            raise ListSignatureError("unsigned revocation list")
        return {k: v for k, v in doc.items() if k not in _SIGNATURE_MEMBERS}, signatures
    raise ListSchemaError(
        "document is neither a signed envelope nor a marketplace.revocation-list/v1 body"
    )


def verify_owner_signatures(
    body: Mapping[str, Any],
    signatures: Sequence[Mapping[str, Any]],
    owner_public_keys: Mapping[str, Any],
) -> str:
    """Verify ``signatures`` over ``body`` and return the trusted key id that signed it.

    Every signature object is checked: an unsupported algorithm, a missing
    key id or a malformed signature rejects the document; a trusted key whose
    signature does not verify rejects it too (tamper evidence).  Signatures by
    keys outside ``owner_public_keys`` are ignored unless they are the only
    ones, in which case the document is rejected as untrusted.
    """
    _require_crypto()
    if not signatures:
        raise ListSignatureError("unsigned revocation list")
    message = signing_message(body)
    verified: list[str] = []
    untrusted: list[str] = []
    for sig in signatures:
        algorithm = str(sig.get("algorithm", ALG)).lower()
        if algorithm != ALG:
            raise ListSignatureError(f"unsupported signature algorithm {algorithm!r}")
        key_id = sig.get("key_id")
        if not isinstance(key_id, str) or not key_id:
            raise ListSignatureError("signature object without a key_id")
        try:
            sig_bytes = _decode_bytes(sig.get("signature"), 64, "signature")
        except (TypeError, ValueError) as exc:
            raise ListSignatureError(f"malformed signature for key {key_id!r}: {exc}") from exc
        if key_id not in owner_public_keys:
            untrusted.append(key_id)
            continue
        try:
            public_key = load_public_key(owner_public_keys[key_id])
        except (TypeError, ValueError) as exc:
            raise ListSignatureError(
                f"trusted key {key_id!r} has unusable key material: {exc}"
            ) from exc
        try:
            public_key.verify(sig_bytes, message)
        except InvalidSignature:
            raise ListSignatureError(
                f"signature by trusted owner key {key_id!r} does not verify"
            ) from None
        verified.append(key_id)
    if verified:
        return verified[0]
    raise ListSignatureError(
        f"no trusted owner signature; signed only by untrusted key(s) {sorted(set(untrusted))}"
    )


def sign_envelope(
    body: Mapping[str, Any],
    *,
    key_id: str,
    private_key: object,
    validate: bool = True,
) -> dict[str, Any]:
    """Owner action: wrap ``body`` in a signed envelope the client will accept.

    ``private_key`` is an ``Ed25519PrivateKey`` or its 32-byte seed
    (raw/hex/base64/PEM).  With ``validate`` the body must be a well-formed
    list (:class:`ListSchemaError` otherwise); pass ``validate=False`` only to
    build deliberately malformed test documents.  No key is ever generated.
    """
    if not isinstance(body, Mapping):
        raise TypeError("body must be a mapping")
    if not isinstance(key_id, str) or not key_id.strip():
        raise ValueError("key_id must be a non-empty string")
    if validate:
        RevocationList.from_body(body)
    signed_body = json.loads(signing_message(body).decode("ascii"))
    signature = load_private_key(private_key).sign(canonical_json(signed_body))
    return {
        "schema": ENVELOPE_SCHEMA,
        "body": signed_body,
        "signature": {"algorithm": ALG, "key_id": key_id, "signature": signature.hex()},
    }


# --------------------------------------------------------------------------- list model


def _require_str(entry: Mapping[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ListSchemaError(f"{where}: {key!r} must be a non-empty string")
    return value


def _optional_str(entry: Mapping[str, Any], key: str, where: str) -> str | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ListSchemaError(f"{where}: {key!r} must be a string when present")
    return value


def _timestamp(body: Mapping[str, Any], key: str) -> datetime:
    value = body.get(key)
    if not isinstance(value, str):
        raise ListSchemaError(f"{key!r} must be an ISO-8601 timestamp string")
    try:
        return parse_iso8601(value)
    except ValueError as exc:
        raise ListSchemaError(f"{key!r}: {exc}") from exc


@dataclass(frozen=True)
class RevocationList:
    """A validated ``marketplace.revocation-list/v1`` body with indexed lookups."""

    body: dict[str, Any]
    sequence: int
    issued_at: datetime
    expires_at: datetime
    revoked_keys: dict[str, dict[str, Any]]
    revoked_versions: dict[tuple[str, str], dict[str, Any]]
    digest: str
    verified_by: str | None = None

    @classmethod
    def from_body(cls, body: Mapping[str, Any]) -> RevocationList:
        """Validate ``body`` (schema, timestamps, sequence, entries) or raise :class:`ListSchemaError`."""
        if not isinstance(body, Mapping):
            raise ListSchemaError("list body must be a JSON object")
        if body.get("schema") != LIST_SCHEMA:
            raise ListSchemaError(f"schema must be {LIST_SCHEMA!r}, got {body.get('schema')!r}")
        sequence = body.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise ListSchemaError("'sequence' must be a non-negative integer")
        issued_at = _timestamp(body, "issued_at")
        expires_at = _timestamp(body, "expires_at")
        keys_raw = body.get("revoked_keys", [])
        versions_raw = body.get("revoked_versions", [])
        if not isinstance(keys_raw, list) or not all(isinstance(e, Mapping) for e in keys_raw):
            raise ListSchemaError("'revoked_keys' must be a list of objects")
        if not isinstance(versions_raw, list) or not all(
            isinstance(e, Mapping) for e in versions_raw
        ):
            raise ListSchemaError("'revoked_versions' must be a list of objects")
        revoked_keys: dict[str, dict[str, Any]] = {}
        for index, entry in enumerate(keys_raw):
            where = f"revoked_keys[{index}]"
            key_id = _require_str(entry, "key_id", where)
            _optional_str(entry, "reason", where)
            revoked_at = _optional_str(entry, "revoked_at", where)
            if revoked_at is not None:
                try:
                    parse_iso8601(revoked_at)
                except ValueError as exc:
                    raise ListSchemaError(f"{where}: revoked_at: {exc}") from exc
            revoked_keys.setdefault(key_id, dict(entry))
        revoked_versions: dict[tuple[str, str], dict[str, Any]] = {}
        for index, entry in enumerate(versions_raw):
            where = f"revoked_versions[{index}]"
            package_id = _require_str(entry, "package_id", where)
            version = _require_str(entry, "version", where)
            _optional_str(entry, "reason", where)
            revoked_versions.setdefault((package_id, version), dict(entry))
        clean = {k: v for k, v in body.items() if k not in _SIGNATURE_MEMBERS}
        return cls(
            body=json.loads(canonical_json(clean).decode("ascii")),
            sequence=sequence,
            issued_at=issued_at,
            expires_at=expires_at,
            revoked_keys=revoked_keys,
            revoked_versions=revoked_versions,
            digest=sha256_hex(canonical_json(clean)),
        )

    def is_expired(self, now: datetime) -> bool:
        """True once ``now`` reaches ``expires_at`` (the window is half-open)."""
        return now >= self.expires_at

    def find_version(self, package_id: str, version: str) -> dict[str, Any] | None:
        """The revocation entry for ``package_id@version``, or ``None``."""
        return self.revoked_versions.get((str(package_id), str(version)))

    def find_key(self, key_id: str | None) -> dict[str, Any] | None:
        """The revocation entry for publisher ``key_id``, or ``None``."""
        if key_id is None:
            return None
        return self.revoked_keys.get(str(key_id))

    def summary(self) -> dict[str, Any]:
        """Small JSON-friendly description for receipts and logs."""
        return {
            "sequence": self.sequence,
            "issued_at": iso_utc(self.issued_at),
            "expires_at": iso_utc(self.expires_at),
            "revoked_keys": len(self.revoked_keys),
            "revoked_versions": len(self.revoked_versions),
            "digest": self.digest,
            "verified_by": self.verified_by,
        }


# --------------------------------------------------------------------------- results


@dataclass(frozen=True)
class RefreshResult:
    """Outcome of one :meth:`RevocationClient.refresh`."""

    state: str
    source: str
    sequence: int | None
    warnings: list[str] = field(default_factory=list)
    reason: str = ""
    attempts: int = 0
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "source": self.source,
            "sequence": self.sequence,
            "warnings": list(self.warnings),
            "reason": self.reason,
            "attempts": self.attempts,
            "error": self.error,
        }


@dataclass(frozen=True)
class RevocationDecision:
    """What the install gate acts on: ``REFUSE`` or ``ALLOW`` plus the degrade context."""

    action: str
    reason: str
    list_state: str
    warnings: list[str]
    known_revoked: bool
    package_id: str
    version: str
    key_id: str | None = None
    sequence: int | None = None
    matched: dict[str, Any] | None = None

    @property
    def refused(self) -> bool:
        return self.action == REFUSE

    @property
    def allowed(self) -> bool:
        return self.action == ALLOW

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "list_state": self.list_state,
            "warnings": list(self.warnings),
            "known_revoked": self.known_revoked,
            "package_id": self.package_id,
            "version": self.version,
            "key_id": self.key_id,
            "sequence": self.sequence,
            "matched": dict(self.matched) if self.matched else None,
        }


# --------------------------------------------------------------------------- client


class RevocationClient:
    """Fetch, verify, cache and consult the owner's revocation list.

    Parameters
    ----------
    transport
        Object with ``fetch_bytes() -> bytes`` raising :class:`FetchError`
        (or any ``OSError``) when the list cannot be delivered.
    cache_path
        JSON file holding the last accepted list; written atomically.
    owner_public_keys
        ``{key_id: public key}`` of the marketplace owner(s) allowed to publish.
        Key material is validated eagerly.
    degrade
        The durable warning sink.  Defaults to ``degrade.json`` beside the cache
        so degraded decisions are never silent.
    clock
        Anything :func:`~tools.marketplace.revocation_list.degrade.clock_now`
        understands; ``None`` for the wall clock.
    attempts, backoff, sleep
        Bounded fetch retry: ``attempts`` tries, sleeping ``backoff[i]`` between
        them through ``sleep`` (tests inject zero delays and a no-op sleep).
    """

    def __init__(
        self,
        *,
        transport: Transport,
        cache_path: Path | str,
        owner_public_keys: Mapping[str, Any],
        degrade: DegradeSink | None = None,
        clock: object | None = None,
        attempts: int = DEFAULT_ATTEMPTS,
        backoff: Sequence[float] = DEFAULT_BACKOFF,
        sleep: Callable[[float], object] = time.sleep,
    ) -> None:
        if not callable(getattr(transport, "fetch_bytes", None)):
            raise TypeError("transport must provide a callable fetch_bytes()")
        if not isinstance(owner_public_keys, Mapping):
            raise TypeError("owner_public_keys must be a mapping of key_id -> public key")
        if int(attempts) < 1:
            raise ValueError("attempts must be >= 1")
        delays = tuple(float(d) for d in backoff)
        if any(d < 0 for d in delays):
            raise ValueError("backoff delays must be non-negative")
        if not callable(sleep):
            raise TypeError("sleep must be callable")
        self.transport = transport
        self.cache_path = Path(cache_path)
        self.owner_public_keys: dict[str, Ed25519PublicKey] = {}
        for key_id, material in owner_public_keys.items():
            if not isinstance(key_id, str) or not key_id:
                raise ValueError("owner key ids must be non-empty strings")
            try:
                self.owner_public_keys[key_id] = load_public_key(material)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"owner key {key_id!r}: {exc}") from exc
        self.degrade = degrade or DegradeSink(self.cache_path.parent / "degrade.json", clock=clock)
        self.clock = clock
        self.attempts = int(attempts)
        self.backoff = delays
        self.sleep = sleep
        self.last_refresh: RefreshResult | None = None
        self._current: RevocationList | None = None

    def __repr__(self) -> str:
        return (
            f"RevocationClient(cache_path={str(self.cache_path)!r}, "
            f"owners={sorted(self.owner_public_keys)}, attempts={self.attempts})"
        )

    # -- cache ----------------------------------------------------------------

    def cached_list(self) -> RevocationList | None:
        """The last accepted list as stored on disk (``None`` if absent or unusable)."""
        return self._load_cache()

    def _load_cache(self) -> RevocationList | None:
        if not self.cache_path.is_file():
            return None
        try:
            doc = parse_document(self.cache_path.read_bytes())
            if doc.get("schema") != CACHE_SCHEMA:
                raise ListSchemaError(f"cache schema is {doc.get('schema')!r}, not {CACHE_SCHEMA!r}")
            body = doc.get("body")
            if not isinstance(body, Mapping):
                raise ListSchemaError("cache has no list body")
            cached = RevocationList.from_body(body)
            recorded = doc.get("body_sha256")
            if isinstance(recorded, str) and recorded != cached.digest:
                raise ListSchemaError("cache body digest mismatch")
            verified_by = doc.get("verified_by")
            return replace(cached, verified_by=verified_by if isinstance(verified_by, str) else None)
        except (OSError, RevocationListError) as exc:
            self._warn("CACHE-CORRUPT", f"revocation cache unusable, treated as absent: {exc}")
            return None

    def _store_cache(self, accepted: RevocationList, now: datetime) -> None:
        doc = {
            "schema": CACHE_SCHEMA,
            "accepted_at": iso_utc(now),
            "verified_by": accepted.verified_by,
            "body_sha256": accepted.digest,
            "body": accepted.body,
        }
        payload = (json.dumps(doc, sort_keys=True, indent=1) + "\n").encode("utf-8")
        try:
            atomic_write_bytes(self.cache_path, payload)
        except OSError as exc:
            self._warn(
                "CACHE-WRITE-FAILED",
                f"accepted list sequence {accepted.sequence} could not be cached: {exc}",
            )

    # -- degrade --------------------------------------------------------------

    def _warn(self, code: str, reason: str, **detail: Any) -> None:
        self.degrade.warn(code, reason, **detail)

    # -- owner gate -----------------------------------------------------------

    def accept_owner_publication(self, raw: bytes | str) -> RevocationList:
        """Verify-only acceptance of a published document.

        Parses ``raw``, requires a valid signature by one of
        ``owner_public_keys`` over the canonical body and validates the body.
        Raises :class:`ListSignatureError` / :class:`ListSchemaError`; never
        touches the cache (sequence policy lives in :meth:`refresh`).
        """
        body, signatures = split_envelope(parse_document(raw))
        signer = verify_owner_signatures(body, signatures, self.owner_public_keys)
        return replace(RevocationList.from_body(body), verified_by=signer)

    # -- fetch ----------------------------------------------------------------

    def _delay(self, attempt: int) -> float:
        if not self.backoff:
            return 0.0
        return self.backoff[min(attempt - 1, len(self.backoff) - 1)]

    def _fetch(self) -> tuple[bytes | None, int, str | None]:
        error: str | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                data = self.transport.fetch_bytes()
            except (FetchError, OSError) as exc:
                error = f"{type(exc).__name__}: {exc}"
            else:
                if isinstance(data, (bytes, bytearray, memoryview)):
                    return bytes(data), attempt, None
                if isinstance(data, str):
                    return data.encode("utf-8"), attempt, None
                error = f"transport returned {type(data).__name__}, not bytes"
            if attempt < self.attempts:
                delay = self._delay(attempt)
                if delay > 0:
                    self.sleep(delay)
        return None, self.attempts, error

    # -- refresh --------------------------------------------------------------

    def refresh(self) -> RefreshResult:
        """Fetch, verify and (if acceptable) cache the live list; record degradation.

        Returns the list state used for subsequent decisions.  Rejected or
        unreachable lists leave the cache untouched, so a network block or a
        forged document can never un-revoke a known entry.
        """
        cached = self._load_cache()
        raw, attempts, fetch_error = self._fetch()
        now = clock_now(self.clock)
        cached_seq = cached.sequence if cached is not None else None
        source = "cache" if cached is not None else "none"

        if raw is None:
            self._current = cached
            reason = f"revocation list unreachable after {attempts} attempt(s): {fetch_error}"
            self._warn(STALE, reason, list_state=UNREACHABLE, cached_sequence=cached_seq)
            result = RefreshResult(UNREACHABLE, source, cached_seq, [STALE], reason, attempts, fetch_error)
            self.last_refresh = result
            return result

        try:
            fresh = self.accept_owner_publication(raw)
            if cached is not None:
                if fresh.sequence < cached.sequence:
                    raise ListSequenceError(
                        f"sequence rollback: live {fresh.sequence} < cached {cached.sequence}"
                    )
                if fresh.sequence == cached.sequence and fresh.digest != cached.digest:
                    raise ListSequenceError(
                        f"sequence {fresh.sequence} reused for a different list body"
                    )
        except RevocationListError as exc:
            self._current = cached
            reason = f"live revocation list rejected: {exc}"
            self._warn(REJECTED, reason, list_state=REJECTED, cached_sequence=cached_seq)
            self._warn(
                STALE,
                "serving the cached revocation list because the live list was rejected",
                list_state=REJECTED,
                cached_sequence=cached_seq,
            )
            result = RefreshResult(REJECTED, source, cached_seq, [REJECTED, STALE], reason, attempts, str(exc))
            self.last_refresh = result
            return result

        if cached is None or fresh.digest != cached.digest or cached.verified_by != fresh.verified_by:
            self._store_cache(fresh, now)
        self._current = fresh
        if fresh.is_expired(now):
            reason = (
                f"revocation list sequence {fresh.sequence} expired at "
                f"{iso_utc(fresh.expires_at)} (now {iso_utc(now)})"
            )
            self._warn(STALE, reason, list_state=STALE, sequence=fresh.sequence)
            result = RefreshResult(STALE, "live", fresh.sequence, [STALE], reason, attempts, None)
        else:
            result = RefreshResult(
                FRESH,
                "live",
                fresh.sequence,
                [],
                f"revocation list sequence {fresh.sequence} verified by owner key {fresh.verified_by!r}",
                attempts,
                None,
            )
        self.last_refresh = result
        return result

    # -- decisions ------------------------------------------------------------

    def effective_list(self) -> RevocationList | None:
        """The list decisions are currently based on (live or cached), if any."""
        if self._current is None:
            self._current = self._load_cache()
        return self._current

    def is_known_revoked(self, package_id: str, version: str, key_id: str | None = None) -> bool:
        """True when the effective list revokes the version or the publisher key (no fetch)."""
        current = self.effective_list()
        if current is None:
            return False
        return current.find_version(package_id, version) is not None or (
            current.find_key(key_id) is not None
        )

    def check(self, package_id: str, version: str, key_id: str | None = None) -> RevocationDecision:
        """Refresh the list and decide whether ``package_id@version`` (signed by ``key_id``) may install."""
        if not isinstance(package_id, str) or not package_id:
            raise ValueError("package_id must be a non-empty string")
        if not isinstance(version, str) or not version:
            raise ValueError("version must be a non-empty string")
        if key_id is not None and not isinstance(key_id, str):
            raise TypeError("key_id must be a string or None")
        status = self.refresh()
        current = self.effective_list()
        sequence = current.sequence if current is not None else None
        matched: dict[str, Any] | None = None
        reason = ""
        if current is not None:
            entry = current.find_version(package_id, version)
            if entry is not None:
                matched = entry
                reason = f"{package_id}@{version} is revoked"
                if entry.get("reason"):
                    reason += f": {entry['reason']}"
            else:
                key_entry = current.find_key(key_id)
                if key_entry is not None:
                    matched = key_entry
                    reason = f"publisher key {key_id} is revoked"
                    if key_entry.get("reason"):
                        reason += f": {key_entry['reason']}"
        if matched is not None:
            action = REFUSE
        else:
            action = ALLOW
            if current is None:
                reason = f"no revocation list available ({status.state}); allowed with {STALE} warning"
            else:
                reason = (
                    f"{package_id}@{version} not on revocation list sequence {sequence} "
                    f"({status.state})"
                )
        return RevocationDecision(
            action=action,
            reason=reason,
            list_state=status.state,
            warnings=list(status.warnings),
            known_revoked=matched is not None,
            package_id=package_id,
            version=version,
            key_id=key_id,
            sequence=sequence,
            matched=dict(matched) if matched is not None else None,
        )

    evaluate = check
