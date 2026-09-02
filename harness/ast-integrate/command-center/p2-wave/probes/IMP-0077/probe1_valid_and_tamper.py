#!/usr/bin/env python3
"""Named probe 1: valid fixture verifies; tamper cases fail.

Signal (1): a correctly signed fixture verifies.
Signal (2) partial: flipped payload byte and swapped signatures fail.
UNSIGNED is reported unsigned, never VALID-by-absence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from marketplace.signature import (  # noqa: E402
    INVALID,
    UNSIGNED,
    VALID,
    encode_record,
    package_digest,
    sign_record,
    verify_signature,
    verify_wire,
)
from marketplace.verify import GATE_SIGNATURE, GateFailure, check_signature  # noqa: E402

KEY_A = "publisher.probe1-a"
KEY_B = "publisher.probe1-b"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0077-probe1 {msg}")
    return 1


def main() -> int:
    priv_a = Ed25519PrivateKey.generate()
    priv_b = Ed25519PrivateKey.generate()
    payload_a = b"imp-0077-package-a\n"
    payload_b = b"imp-0077-package-b\n"
    digest_a = package_digest(payload_a)
    digest_b = package_digest(payload_b)
    rec_a = sign_record(priv_a, digest=digest_a, key_id=KEY_A)
    rec_b = sign_record(priv_b, digest=digest_b, key_id=KEY_B)
    store = {
        KEY_A: priv_a.public_key().public_bytes_raw().hex(),
        KEY_B: priv_b.public_key().public_bytes_raw().hex(),
    }

    good = verify_signature(digest_a, rec_a, store)
    if good.status != VALID or good.key_id != KEY_A:
        return fail(f"correctly signed fixture did not verify: {good}")
    if check_signature(digest_a, rec_a, store) != KEY_A:
        return fail("check_signature did not return key_id for valid record")
    wire = encode_record(rec_a)
    if verify_wire(wire, digest_a, store).status != VALID:
        return fail("canonical wire encoding of the valid fixture did not verify")

    flipped = bytearray(payload_a)
    flipped[4] ^= 0x7F
    flipped_digest = package_digest(bytes(flipped))
    if flipped_digest == digest_a:
        return fail("flipped payload produced the same digest")
    tamper = verify_signature(flipped_digest, rec_a, store)
    if tamper.status != INVALID or tamper.reason_code != "digest-mismatch":
        return fail(f"flipped payload was not rejected: {tamper}")

    swapped_whole = verify_signature(digest_a, rec_b, store)
    if swapped_whole.status != INVALID:
        return fail(f"swapped whole record verified: {swapped_whole}")
    swapped_sig = dict(rec_a)
    swapped_sig["signature"] = rec_b["signature"]
    swapped_bytes = verify_signature(digest_a, swapped_sig, store)
    if swapped_bytes.status != INVALID or swapped_bytes.reason_code != "signature-mismatch":
        return fail(f"swapped signature bytes verified: {swapped_bytes}")

    unsigned = verify_signature(digest_a, None, store)
    if unsigned.status != UNSIGNED or unsigned.status == VALID:
        return fail(f"unsigned reported as {unsigned.status}")
    if "unsigned" not in unsigned.reason:
        return fail(f"unsigned reason missing token: {unsigned.reason}")
    try:
        check_signature(digest_a, None, store)
        return fail("check_signature accepted an unsigned package")
    except GateFailure as exc:
        if exc.gate != GATE_SIGNATURE or "unsigned" not in str(exc).lower():
            return fail(f"unsigned GateFailure malformed: {exc}")

    payload = {
        "probe": "probe1-valid-and-tamper",
        "unit_id": "IMP-0077",
        "valid": True,
        "flipped_payload_rejected": True,
        "swapped_record_rejected": True,
        "swapped_signature_bytes_rejected": True,
        "unsigned_status": unsigned.status,
        "unsigned_never_valid": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "valid=True flipped=rejected swapped=rejected unsigned=UNSIGNED"
    )
    print("SUCCESS:IMP-0077-probe1 valid fixture, tamper, swap, unsigned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
