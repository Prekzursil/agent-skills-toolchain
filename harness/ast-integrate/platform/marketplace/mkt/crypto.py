"""Ed25519 publisher signatures, with no runtime dependency.

WHY A PURE-PYTHON ED25519
    Signing is spec-required (10851). ``cryptography`` happens to be installed on this box
    but the marketplace must be verifiable in an offline, air-gapped import where nothing
    is pip-installable, so the implementation here is the RFC 8032 reference construction
    over edwards25519 in pure Python -- no imports beyond ``hashlib``.

    That choice buys a second, better thing: an INDEPENDENT INSTRUMENT. ``cryptography``
    ships a completely different Ed25519 (Rust/OpenSSL). ``test_crypto.py`` cross-verifies
    the two in both directions -- keys generated here verify there and vice versa -- so
    "the signature check works" is not a claim resting on the same code that produces the
    signature. If ``cryptography`` is absent the cross-check is SKIPPED and says so; it is
    never silently treated as a pass.

DOMAIN SEPARATION
    The signed byte string is ``<domain>|<canonical document bytes>``. Without the domain
    tag a registry-index signature could be replayed as a manifest signature over the same
    bytes. The tag set is closed in ``signature.schema.json``.

SECURITY NOTE
    :func:`generate_keypair` creates a *test/publisher* key for this marketplace. It never
    reads, writes, prints or rotates any credential belonging to the estate; secret keys
    live only where the caller puts them and the CLI writes them under the caller's chosen
    keystore path with a warning in the file itself.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

from .canon import canonical_bytes, digest_bytes, strip_signature

# --------------------------------------------------------------------------- #
# edwards25519 field / group constants (RFC 8032 section 5.1)
# --------------------------------------------------------------------------- #

Q_FIELD = 2**255 - 19
L_ORDER = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, Q_FIELD - 2, Q_FIELD) % Q_FIELD
_SQRT_M1 = pow(2, (Q_FIELD - 1) // 4, Q_FIELD)

KEY_ID_RE = re.compile(r"^key:[0-9a-f]{16}$")
PUBKEY_RE = re.compile(r"^ed25519:[0-9a-f]{64}$")

VALID_DOMAINS = frozenset(
    {
        "mkt.manifest.v1",
        "mkt.index.v1",
        "mkt.revocation.v1",
        "mkt.advisory.v1",
        "mkt.bundle.v1",
        "mkt.lockfile.v1",
    }
)


class CryptoError(ValueError):
    """A key, signature or domain is malformed. Never raised for a mere bad signature."""


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _inv(x: int) -> int:
    return pow(x, Q_FIELD - 2, Q_FIELD)


def _point_add(
    p: tuple[int, int, int, int], q: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % Q_FIELD
    b = (y1 + x1) * (y2 + x2) % Q_FIELD
    c = 2 * t1 * t2 * _D % Q_FIELD
    d = 2 * z1 * z2 % Q_FIELD
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % Q_FIELD, g * h % Q_FIELD, f * g % Q_FIELD, e * h % Q_FIELD)


def _point_mul(
    scalar: int, point: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    result = (0, 1, 1, 0)
    while scalar > 0:
        if scalar & 1:
            result = _point_add(result, point)
        point = _point_add(point, point)
        scalar >>= 1
    return result


def _point_equal(p: tuple[int, int, int, int], q: tuple[int, int, int, int]) -> bool:
    if (p[0] * q[2] - q[0] * p[2]) % Q_FIELD != 0:
        return False
    return (p[1] * q[2] - q[1] * p[2]) % Q_FIELD == 0


def _recover_x(y: int, sign: int) -> int | None:
    if y >= Q_FIELD:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1) % Q_FIELD
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (Q_FIELD + 3) // 8, Q_FIELD)
    if (x * x - x2) % Q_FIELD != 0:
        x = x * _SQRT_M1 % Q_FIELD
    if (x * x - x2) % Q_FIELD != 0:
        return None
    if (x & 1) != sign:
        x = Q_FIELD - x
    return x


_G_Y = 4 * _inv(5) % Q_FIELD
_G_X = _recover_x(_G_Y, 0)
assert _G_X is not None  # noqa: S101 - a build-time constant, not a runtime check
BASE_POINT = (_G_X, _G_Y, 1, _G_X * _G_Y % Q_FIELD)


def _compress(point: tuple[int, int, int, int]) -> bytes:
    zinv = _inv(point[2])
    x = point[0] * zinv % Q_FIELD
    y = point[1] * zinv % Q_FIELD
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(data: bytes) -> tuple[int, int, int, int] | None:
    if len(data) != 32:
        return None
    value = int.from_bytes(data, "little")
    sign = value >> 255
    y = value & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % Q_FIELD)


def _secret_expand(secret: bytes) -> tuple[int, bytes]:
    if len(secret) != 32:
        raise CryptoError(f"ed25519 secret key must be 32 bytes, got {len(secret)}")
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


# --------------------------------------------------------------------------- #
# raw primitives
# --------------------------------------------------------------------------- #


def public_from_secret(secret: bytes) -> bytes:
    a, _ = _secret_expand(secret)
    return _compress(_point_mul(a, BASE_POINT))


def raw_sign(secret: bytes, message: bytes) -> bytes:
    a, prefix = _secret_expand(secret)
    pub = _compress(_point_mul(a, BASE_POINT))
    r = int.from_bytes(_sha512(prefix + message), "little") % L_ORDER
    r_point = _compress(_point_mul(r, BASE_POINT))
    k = int.from_bytes(_sha512(r_point + pub + message), "little") % L_ORDER
    s = (r + k * a) % L_ORDER
    return r_point + int.to_bytes(s, 32, "little")


def raw_verify(public: bytes, message: bytes, signature: bytes) -> bool:
    if len(public) != 32 or len(signature) != 64:
        return False
    r_bytes = signature[:32]
    s = int.from_bytes(signature[32:], "little")
    if s >= L_ORDER:
        return False
    a_point = _decompress(public)
    r_point = _decompress(r_bytes)
    if a_point is None or r_point is None:
        return False
    k = int.from_bytes(_sha512(r_bytes + public + message), "little") % L_ORDER
    return _point_equal(
        _point_mul(s, BASE_POINT), _point_add(r_point, _point_mul(k, a_point))
    )


# --------------------------------------------------------------------------- #
# marketplace-level API
# --------------------------------------------------------------------------- #


def generate_keypair(seed: bytes | None = None) -> tuple[str, str]:
    """Return ``(secret_hex, public_key)`` where public_key is ``ed25519:<64 hex>``.

    ``seed`` exists so tests are deterministic; production callers pass ``None`` and get
    ``os.urandom(32)``.
    """
    secret = os.urandom(32) if seed is None else seed
    if len(secret) != 32:
        raise CryptoError("seed must be exactly 32 bytes")
    return secret.hex(), "ed25519:" + public_from_secret(secret).hex()


def key_id(public_key: str) -> str:
    """Stable short id: ``key:`` + first 16 hex chars of sha256 over the public key text."""
    if not PUBKEY_RE.match(public_key):
        raise CryptoError(f"malformed ed25519 public key: {public_key!r}")
    return "key:" + hashlib.sha256(public_key.encode("utf-8")).hexdigest()[:16]


def signing_bytes(domain: str, doc: dict[str, Any]) -> bytes:
    """The exact bytes a signature covers: ``<domain>|<canonical doc without signature>``."""
    if domain not in VALID_DOMAINS:
        raise CryptoError(
            f"unknown signing domain {domain!r}; the set is closed: {sorted(VALID_DOMAINS)}"
        )
    return domain.encode("ascii") + b"|" + canonical_bytes(strip_signature(doc))


def sign_document(
    doc: dict[str, Any], domain: str, secret_hex: str, *, signed_at: str | None = None
) -> dict[str, Any]:
    """Return the ``signature`` block for ``doc`` (does not mutate ``doc``)."""
    secret = bytes.fromhex(secret_hex)
    public = "ed25519:" + public_from_secret(secret).hex()
    message = signing_bytes(domain, doc)
    block = {
        "algorithm": "ed25519",
        "domain": domain,
        "key_id": key_id(public),
        "public_key": public,
        "signed_digest": digest_bytes(message),
        "signature": raw_sign(secret, message).hex(),
    }
    if signed_at is not None:
        block["signed_at"] = signed_at
    return block


def verify_document(
    doc: dict[str, Any], domain: str, *, expected_public_key: str | None = None
) -> tuple[bool, str]:
    """Verify ``doc['signature']``. Returns ``(ok, reason)``; ``reason`` is '' when ok.

    The failure reasons are DISTINCT on purpose. "digest mismatch" means the document was
    edited after signing; "signature mismatch" means the bytes are intact but the key or
    signature is wrong; "key not trusted" means both were fine and policy refused. One
    opaque ``False`` would make those three indistinguishable in an incident.
    """
    block = doc.get("signature")
    if not isinstance(block, dict):
        return False, "no signature block"
    if block.get("algorithm") != "ed25519":
        return False, f"unsupported algorithm {block.get('algorithm')!r}"
    if block.get("domain") != domain:
        return (
            False,
            f"domain mismatch: signed for {block.get('domain')!r}, verifying as {domain!r}",
        )
    public = block.get("public_key", "")
    if not isinstance(public, str) or not PUBKEY_RE.match(public):
        return False, "malformed public key"
    if expected_public_key is not None and public != expected_public_key:
        return False, "key not trusted for this document"
    if block.get("key_id") != key_id(public):
        return False, "key_id does not match public_key"
    try:
        message = signing_bytes(domain, doc)
    except CryptoError as exc:
        return False, str(exc)
    if block.get("signed_digest") != digest_bytes(message):
        return False, "digest mismatch: the document changed after it was signed"
    sig_hex = block.get("signature", "")
    if not isinstance(sig_hex, str) or len(sig_hex) != 128:
        return False, "malformed signature"
    try:
        signature = bytes.fromhex(sig_hex)
    except ValueError:
        return False, "signature is not hex"
    if not raw_verify(bytes.fromhex(public.split(":", 1)[1]), message, signature):
        return False, "signature mismatch"
    return True, ""
