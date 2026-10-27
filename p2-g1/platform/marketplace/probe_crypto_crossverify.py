"""Cross-verify the pure-Python Ed25519 in mkt.crypto against the `cryptography` library.

This is a DELIVERABLE probe, not scratch: it is the independent instrument that makes
"signatures verify" a two-signal claim rather than one implementation agreeing with
itself. Run it directly:

    python platform/marketplace/probe_crypto_crossverify.py

It prints a JSON verdict and exits non-zero on any disagreement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mkt import crypto  # noqa: E402


def main() -> int:
    out: dict[str, object] = {
        "pure_python_self_consistent": None,
        "cross_vendor": "NOT-CHECKED",
    }

    seed = bytes(range(32))
    secret_hex, public = crypto.generate_keypair(seed)
    msg = b"mkt.manifest.v1|{}"
    sig = crypto.raw_sign(bytes.fromhex(secret_hex), msg)
    ok_good = crypto.raw_verify(bytes.fromhex(public.split(":")[1]), msg, sig)
    ok_tampered = crypto.raw_verify(
        bytes.fromhex(public.split(":")[1]), msg + b"x", sig
    )
    out["pure_python_self_consistent"] = bool(ok_good and not ok_tampered)
    out["control_valid_signature_accepted"] = bool(ok_good)
    out["control_tampered_message_rejected"] = bool(not ok_tampered)

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        out["cross_vendor"] = "NOT-CHECKED (cryptography not importable)"
        print(json.dumps(out, indent=2))
        return 0 if out["pure_python_self_consistent"] else 1

    # direction 1: our key + our signature, verified by cryptography
    ref_pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public.split(":")[1]))
    try:
        ref_pub.verify(sig, msg)
        d1 = True
    except InvalidSignature:
        d1 = False

    # direction 2: cryptography's key + signature, verified by us
    ref_priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(secret_hex))
    ref_sig = ref_priv.sign(msg)
    d2 = crypto.raw_verify(bytes.fromhex(public.split(":")[1]), msg, ref_sig)

    # and the byte-for-byte agreement Ed25519 determinism demands
    d3 = ref_sig == sig

    out["cross_vendor"] = {
        "ours_verified_by_cryptography": bool(d1),
        "cryptography_verified_by_ours": bool(d2),
        "signature_bytes_identical": bool(d3),
    }
    ok = bool(out["pure_python_self_consistent"]) and d1 and d2 and d3
    print(json.dumps(out, indent=2))
    print("SUCCESS:crypto-crossverify" if ok else "FAILED:crypto-crossverify")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
