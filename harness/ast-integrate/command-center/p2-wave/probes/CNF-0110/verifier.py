#!/usr/bin/env python3
"""Signed-package + provenance verifier for CNF-0110.

Checks, in order, so each tamper class fails on a different named check:
  1. Ed25519 envelope signature is valid under the publisher public key
  2. Envelope package_id matches the local package id
  3. Envelope content_sha256 matches sha256(payload)
  4. Provenance attestation file is present
  5. Provenance Ed25519 signature is valid under the builder public key
  6. Provenance subject digest matches sha256(payload)

Private keys are never read. Trust is public-hex only.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

EXIT_OK = 0
EXIT_CONTENT_DIGEST_MISMATCH = 21
EXIT_SIGNATURE_IDENTITY_MISMATCH = 22
EXIT_PROVENANCE_MISSING = 23
EXIT_PROVENANCE_SUBJECT_MISMATCH = 24
EXIT_SIGNATURE_INVALID = 25
EXIT_PACKAGE_UNREADABLE = 26
EXIT_TRUST_UNREADABLE = 27
EXIT_PROVENANCE_INVALID = 28

ERROR_CONTENT = "CONTENT_DIGEST_MISMATCH"
ERROR_IDENTITY = "SIGNATURE_IDENTITY_MISMATCH"
ERROR_PROVENANCE_MISSING = "PROVENANCE_MISSING"
ERROR_PROVENANCE_SUBJECT = "PROVENANCE_SUBJECT_MISMATCH"
ERROR_SIGNATURE_INVALID = "SIGNATURE_INVALID"
ERROR_PROVENANCE_INVALID = "PROVENANCE_SIGNATURE_INVALID"

VARIANT_ERROR_CODES = (ERROR_CONTENT, ERROR_IDENTITY, ERROR_PROVENANCE_MISSING)


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def public_key_from_hex(hex_key: str) -> Ed25519PublicKey:
    raw = bytes.fromhex(hex_key.strip())
    if len(raw) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(raw)}")
    return Ed25519PublicKey.from_public_bytes(raw)


def verify_ed25519(pub: Ed25519PublicKey, payload: bytes, signature_b64: str) -> bool:
    try:
        pub.verify(base64.b64decode(signature_b64), payload)
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def fail(code: int, error: str, detail: str) -> int:
    sys.stderr.write(f"CNF-0110-VERIFY FAIL {error}: {detail}\n")
    return code


def verify_package(package_dir: Path, trust: dict[str, str]) -> int:
    try:
        publisher = public_key_from_hex(trust["publisher_public_hex"])
        builder = public_key_from_hex(trust["builder_public_hex"])
    except (KeyError, ValueError) as exc:
        return fail(EXIT_TRUST_UNREADABLE, "TRUST_UNREADABLE", str(exc))

    payload_path = package_dir / "payload.bin"
    package_path = package_dir / "package.json"
    signature_path = package_dir / "signature.json"
    provenance_path = package_dir / "provenance.json"
    try:
        payload = payload_path.read_bytes()
        package_meta = load_json(package_path)
        envelope = load_json(signature_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        return fail(EXIT_PACKAGE_UNREADABLE, "PACKAGE_UNREADABLE", str(exc))

    package_id = str(package_meta.get("id") or "")
    content_digest = sha256_hex(payload)
    env_payload = envelope.get("payload")
    if not isinstance(env_payload, dict):
        return fail(
            EXIT_SIGNATURE_INVALID,
            ERROR_SIGNATURE_INVALID,
            "signature envelope payload is not an object",
        )
    sig_b64 = str(envelope.get("signature_b64") or "")
    if not verify_ed25519(publisher, canonical(env_payload), sig_b64):
        return fail(
            EXIT_SIGNATURE_INVALID,
            ERROR_SIGNATURE_INVALID,
            "publisher Ed25519 signature does not verify over the envelope payload",
        )

    bound_id = str(env_payload.get("package_id") or "")
    if bound_id != package_id:
        return fail(
            EXIT_SIGNATURE_IDENTITY_MISMATCH,
            ERROR_IDENTITY,
            f"envelope binds package_id={bound_id!r} but local package id={package_id!r}",
        )

    bound_digest = str(env_payload.get("content_sha256") or "")
    if bound_digest != content_digest:
        return fail(
            EXIT_CONTENT_DIGEST_MISMATCH,
            ERROR_CONTENT,
            f"payload sha256={content_digest} envelope sha256={bound_digest}",
        )

    if not provenance_path.is_file() or provenance_path.stat().st_size <= 0:
        return fail(
            EXIT_PROVENANCE_MISSING,
            ERROR_PROVENANCE_MISSING,
            "provenance.json is absent or empty; attestation was stripped or never attached",
        )
    try:
        provenance = load_json(provenance_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return fail(EXIT_PACKAGE_UNREADABLE, "PACKAGE_UNREADABLE", f"provenance: {exc}")

    prov_payload = provenance.get("payload")
    if not isinstance(prov_payload, dict):
        return fail(
            EXIT_PROVENANCE_INVALID,
            ERROR_PROVENANCE_INVALID,
            "provenance payload is not an object",
        )
    prov_sig = str(provenance.get("signature_b64") or "")
    if not verify_ed25519(builder, canonical(prov_payload), prov_sig):
        return fail(
            EXIT_PROVENANCE_INVALID,
            ERROR_PROVENANCE_INVALID,
            "builder Ed25519 signature does not verify over the provenance payload",
        )

    subjects = prov_payload.get("subject")
    if not isinstance(subjects, list) or not subjects:
        return fail(
            EXIT_PROVENANCE_SUBJECT_MISMATCH,
            ERROR_PROVENANCE_SUBJECT,
            "provenance subject list is empty",
        )
    first = subjects[0] if isinstance(subjects[0], dict) else {}
    digest_obj = first.get("digest") if isinstance(first.get("digest"), dict) else {}
    subject_digest = str(digest_obj.get("sha256") or "")
    subject_name = str(first.get("name") or "")
    if subject_name != package_id or subject_digest != content_digest:
        return fail(
            EXIT_PROVENANCE_SUBJECT_MISMATCH,
            ERROR_PROVENANCE_SUBJECT,
            f"provenance subject name={subject_name!r} sha256={subject_digest} "
            f"local id={package_id!r} sha256={content_digest}",
        )

    sys.stdout.write(
        f"CNF-0110-VERIFY OK package_id={package_id} content_sha256={content_digest}\n"
    )
    return EXIT_OK


def load_trust(path: Path) -> dict[str, str]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("trust file is not an object")
    return {
        "publisher_public_hex": str(data["publisher_public_hex"]),
        "builder_public_hex": str(data["builder_public_hex"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNF-0110 signed-package verifier")
    parser.add_argument("--package", required=True, help="package directory")
    parser.add_argument("--trust", required=True, help="trust.json with public keys only")
    args = parser.parse_args(argv)
    package_dir = Path(args.package)
    trust_path = Path(args.trust)
    if not package_dir.is_dir():
        return fail(EXIT_PACKAGE_UNREADABLE, "PACKAGE_UNREADABLE", f"not a directory: {package_dir}")
    try:
        trust = load_trust(trust_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        return fail(EXIT_TRUST_UNREADABLE, "TRUST_UNREADABLE", str(exc))
    return verify_package(package_dir, trust)


if __name__ == "__main__":
    raise SystemExit(main())
