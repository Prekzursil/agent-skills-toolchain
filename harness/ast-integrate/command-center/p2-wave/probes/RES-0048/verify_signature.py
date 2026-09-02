#!/usr/bin/env python3
"""End-to-end verification of one real Sigstore/PyPI keyless attestation.

Verifies frozen captures of sampleproject 4.0.0:
  1. wheel bytes hash to the in-toto subject digest
  2. DSSE PAE ECDSA-SHA256 over the statement using the Fulcio leaf public key
  3. OIDC identity + issuer extracted from the leaf certificate
  4. Rekor dsse payloadHash equals sha256(statement)
  5. live-captured Rekor GET for logIndex 147137144 still carries that payloadHash

Does not re-walk the Sigstore TUF Fulcio chain. That residual is named in the
research record; this module still performs a cryptographic signature check
against the artifact bytes rather than describing the process.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ec import ECDSA
from cryptography.x509.oid import ExtensionOID, ObjectIdentifier

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"
WHEEL = CAPTURES / "sampleproject-4.0.0-py3-none-any.whl"
PROVENANCE = CAPTURES / "sampleproject-4.0.0-py3-none-any.whl.provenance.json"
REKOR_ENTRY = CAPTURES / "rekor-entry-147137144.json"

PAYLOAD_TYPE = "application/vnd.in-toto+json"
EXPECTED_IDENTITY = (
    "https://github.com/pypa/sampleproject/.github/workflows/"
    "release.yml@refs/heads/main"
)
EXPECTED_ISSUER = "https://token.actions.githubusercontent.com"
EXPECTED_WHEEL_SHA256 = (
    "c23e447ea90d796d1e645c35c4b2de125040add12a845825546f91c93f391b6b"
)
EXPECTED_LOG_INDEX = 147137144
OID_ISSUER = "1.3.6.1.4.1.57264.1.1"
OID_ISSUER_V2 = "1.3.6.1.4.1.57264.1.8"
OID_BUILD_SIGNER_URI = "1.3.6.1.4.1.57264.1.9"
OID_SOURCE_REPO = "1.3.6.1.4.1.57264.1.12"
OID_RUN_INVOCATION = "1.3.6.1.4.1.57264.1.21"


def b64d(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.b64decode(s + pad)


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    # DSSE protocol.md: PAE = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
    type_b = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(type_b), type_b, len(payload), payload)


def _der_utf8(raw: bytes) -> str:
    if not raw:
        return ""
    if raw[0] == 0x0C:  # UTF8String
        length = raw[1]
        start = 2
        if length & 0x80:
            n = length & 0x7F
            length = int.from_bytes(raw[2 : 2 + n], "big")
            start = 2 + n
        return raw[start : start + length].decode("utf-8")
    return raw.decode("utf-8")


def ext_str(cert: x509.Certificate, oid: str) -> str | None:
    try:
        ext = cert.extensions.get_extension_for_oid(ObjectIdentifier(oid))
    except x509.ExtensionNotFound:
        return None
    raw = getattr(ext.value, "value", None)
    if raw is None:
        return str(ext.value)
    if isinstance(raw, bytes):
        return _der_utf8(raw)
    return str(raw)


def san_uris(cert: x509.Certificate) -> list[str]:
    try:
        san = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        ).value
    except x509.ExtensionNotFound:
        return []
    out: list[str] = []
    for name in san:
        val = getattr(name, "value", None)
        if isinstance(val, str):
            out.append(val)
    return out


def load_attestation() -> tuple[dict[str, Any], dict[str, Any]]:
    prov = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    att = prov["attestation_bundles"][0]["attestations"][0]
    publisher = prov["attestation_bundles"][0]["publisher"]
    return att, publisher


def verify_transcript() -> dict[str, Any]:
    att, publisher = load_attestation()
    envelope = att["envelope"]
    statement_raw = b64d(envelope["statement"])
    signature = b64d(envelope["signature"])
    cert = x509.load_der_x509_certificate(b64d(att["verification_material"]["certificate"]))
    statement = json.loads(statement_raw.decode("utf-8"))
    wheel_bytes = WHEEL.read_bytes()
    wheel_sha = hashlib.sha256(wheel_bytes).hexdigest()
    subjects = statement.get("subject") or []
    subject_sha = ((subjects[0] or {}).get("digest") or {}).get("sha256")
    subject_name = (subjects[0] or {}).get("name")
    pae = dsse_pae(PAYLOAD_TYPE, statement_raw)
    dsse_ok = False
    dsse_error = None
    try:
        cert.public_key().verify(signature, pae, ECDSA(hashes.SHA256()))
        dsse_ok = True
    except Exception as exc:  # noqa: BLE001 - recorded in transcript
        dsse_error = f"{type(exc).__name__}: {exc}"

    identity = san_uris(cert)[0] if san_uris(cert) else None
    issuer = ext_str(cert, OID_ISSUER) or ext_str(cert, OID_ISSUER_V2)
    tlog = (att["verification_material"].get("transparency_entries") or [None])[0] or {}
    body = json.loads(base64.b64decode(tlog["canonicalizedBody"]))
    rekor_payload = ((body.get("spec") or {}).get("payloadHash") or {}).get("value")
    statement_sha = hashlib.sha256(statement_raw).hexdigest()

    live_rekor = json.loads(REKOR_ENTRY.read_text(encoding="utf-8"))
    live_uuid, live_row = next(iter(live_rekor.items()))
    live_body = json.loads(base64.b64decode(live_row["body"]))
    live_payload = ((live_body.get("spec") or {}).get("payloadHash") or {}).get("value")
    live_index = live_row.get("logIndex")

    identity_pin_ok = identity == EXPECTED_IDENTITY and issuer == EXPECTED_ISSUER
    naive_sig_exists_ok = dsse_ok  # identity ignored
    digest_bound = wheel_sha == subject_sha == EXPECTED_WHEEL_SHA256
    rekor_bound = rekor_payload == statement_sha == live_payload
    e2e_ok = bool(
        dsse_ok
        and digest_bound
        and identity_pin_ok
        and rekor_bound
        and live_index == EXPECTED_LOG_INDEX
        and statement.get("predicate") is None
    )
    return {
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "e2e_ok": e2e_ok,
        "artifact": {
            "path": WHEEL.relative_to(HERE.parents[3]).as_posix()
            if HERE.parents[3] in WHEEL.parents
            else str(WHEEL),
            "filename": WHEEL.name,
            "bytes": len(wheel_bytes),
            "sha256": wheel_sha,
        },
        "statement": {
            "type": statement.get("_type"),
            "predicate_type": statement.get("predicateType"),
            "predicate": statement.get("predicate"),
            "subject_name": subject_name,
            "subject_sha256": subject_sha,
            "sha256": statement_sha,
        },
        "dsse": {
            "payload_type": PAYLOAD_TYPE,
            "pae_sha256": hashlib.sha256(pae).hexdigest(),
            "signature_der_hex": signature.hex(),
            "verified": dsse_ok,
            "error": dsse_error,
        },
        "certificate": {
            "issuer_cn": cert.issuer.rfc4514_string(),
            "not_valid_before": cert.not_valid_before.replace(
                tzinfo=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "not_valid_after": cert.not_valid_after.replace(
                tzinfo=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "san_uri": identity,
            "oidc_issuer": issuer,
            "build_signer_uri": ext_str(cert, OID_BUILD_SIGNER_URI),
            "source_repository_uri": ext_str(cert, OID_SOURCE_REPO),
            "run_invocation_uri": ext_str(cert, OID_RUN_INVOCATION),
        },
        "publisher_from_pypi": publisher,
        "rekor": {
            "kind": body.get("kind"),
            "log_index": int(tlog.get("logIndex")),
            "integrated_time": int(tlog.get("integratedTime")),
            "payload_hash": rekor_payload,
            "live_get_uuid": live_uuid,
            "live_get_log_index": live_index,
            "live_get_payload_hash": live_payload,
            "live_get_permalink": (
                "https://rekor.sigstore.dev/api/v1/log/entries?logIndex=147137144"
            ),
        },
        "checks": {
            "wheel_digest_matches_subject": digest_bound,
            "dsse_ecdsa_sha256_pae": dsse_ok,
            "identity_pinned": identity_pin_ok,
            "naive_signature_exists_policy": naive_sig_exists_ok,
            "rekor_payload_hash_matches_statement": rekor_bound,
            "predicate_is_null_publish_v1": statement.get("predicate") is None,
        },
        "expected": {
            "identity": EXPECTED_IDENTITY,
            "issuer": EXPECTED_ISSUER,
            "wheel_sha256": EXPECTED_WHEEL_SHA256,
            "log_index": EXPECTED_LOG_INDEX,
        },
        "does_not_cover": [
            "Fulcio chain validation against the Sigstore TUF trust root",
            "Rekor Merkle inclusion-proof recomputation against the Signed Tree Head",
            "Semantic inspection of wheel / markdown / script contents",
        ],
    }


def pinned_accepts(transcript: dict[str, Any], identity: str, issuer: str) -> bool:
    cert = transcript.get("certificate") or {}
    return bool(
        transcript.get("dsse", {}).get("verified")
        and cert.get("san_uri") == identity
        and cert.get("oidc_issuer") == issuer
        and transcript.get("checks", {}).get("wheel_digest_matches_subject")
    )


def naive_accepts(transcript: dict[str, Any]) -> bool:
    return bool(transcript.get("dsse", {}).get("verified"))


def main() -> int:
    t = verify_transcript()
    print(json.dumps({k: t[k] for k in ("e2e_ok", "checks", "certificate", "rekor")}, indent=2))
    if not t["e2e_ok"]:
        print("FAILED:RES-0048 signature transcript not e2e_ok")
        return 1
    print("SUCCESS:RES-0048-verify e2e signature")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
