#!/usr/bin/env python3
"""Named probe 2: independent canonicalisation-confusion review.

Reviewer-designed bypass (not a copy of probe 1's pretty-print case):
a duplicate-key JSON object whose first key_id is trusted and whose
second is attacker-controlled. A last-key-wins parser would verify
against the trusted id while a first-key-wins consumer would bind a
different identity. Strict parse rejects duplicates; we never
re-canonicalise the confused encoding.

Also: Unicode-escape of the algorithm string (semantically equal,
non-canonical), unsupported algorithm fail-closed, unknown key id,
and a negative control that the same record in canonical form verifies.
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
    VALID,
    encode_record,
    package_digest,
    sign_record,
    verify_signature,
    verify_wire,
)

KEY_TRUSTED = "publisher.probe2-trusted"
KEY_ATTACKER = "publisher.probe2-attacker"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0077-probe2 {msg}")
    return 1


def main() -> int:
    private = Ed25519PrivateKey.generate()
    payload = b"imp-0077-review-package\n"
    digest = package_digest(payload)
    record = sign_record(private, digest=digest, key_id=KEY_TRUSTED)
    store = {KEY_TRUSTED: private.public_key().public_bytes_raw().hex()}

    control = verify_wire(encode_record(record), digest, store)
    if control.status != VALID:
        return fail(f"canonical control did not verify: {control}")

    # Own-design bypass: duplicate key_id. Last-key-wins would keep the
    # trusted id (and the matching signature) while a first-key reader
    # would see the attacker id. We must not accept this encoding.
    body = encode_record(record).decode("ascii")
    needle = f'"key_id":"{KEY_TRUSTED}"'
    if needle not in body:
        return fail("canonical record missing expected key_id encoding")
    confused = body.replace(
        needle,
        f'"key_id":"{KEY_ATTACKER}","key_id":"{KEY_TRUSTED}"',
        1,
    ).encode("ascii")
    if json.loads(confused)["key_id"] != KEY_TRUSTED:
        return fail("python json.loads did not last-key-win; fixture setup wrong")
    dup = verify_wire(confused, digest, store)
    if dup.status == VALID:
        return fail("duplicate-key canonicalisation confusion verified")
    if dup.status != INVALID:
        return fail(f"duplicate-key not fail-closed: {dup}")

    escaped = encode_record(record).replace(b'"ed25519"', b'"\\u0065d25519"', 1)
    if json.loads(escaped)["algorithm"] != "ed25519":
        return fail("unicode-escape fixture is not semantically equal")
    esc = verify_wire(escaped, digest, store)
    if esc.status != INVALID or esc.reason_code not in {"non-canonical", "malformed"}:
        return fail(f"unicode-escape encoding accepted: {esc}")

    unknown = verify_signature(digest, record, {KEY_ATTACKER: store[KEY_TRUSTED]})
    if unknown.status != INVALID or unknown.reason_code != "unknown-key-id":
        return fail(f"unknown key id not rejected: {unknown}")

    none_alg = dict(record)
    none_alg["algorithm"] = "none"
    none_result = verify_signature(digest, none_alg, store)
    if none_result.status != INVALID or none_result.reason_code != "unsupported-algorithm":
        return fail(f"algorithm none not fail-closed: {none_result}")

    payload_out = {
        "probe": "probe2-canonicalisation-review",
        "unit_id": "IMP-0077",
        "reviewer_id": "IMP-0077-probe2-canonicalisation-review",
        "independent": True,
        "bypass": "duplicate-key-id last-wins vs first-wins",
        "duplicate_key_rejected": True,
        "unicode_escape_rejected": True,
        "unknown_key_id_rejected": True,
        "unsupported_algorithm_fail_closed": True,
        "canonical_control_valid": True,
        "pass": True,
    }
    print(json.dumps(payload_out, sort_keys=True))
    print(
        "dup_key=rejected unicode_escape=rejected unknown_key=rejected "
        "alg_none=fail_closed control=VALID"
    )
    print("SUCCESS:IMP-0077-probe2 independent canonicalisation-confusion review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
