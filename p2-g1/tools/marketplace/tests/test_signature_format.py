from __future__ import annotations

import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from marketplace.signature import VALID, encode_record, package_digest, sign_record, verify_signature, verify_wire
from marketplace.verify import check_signature


class SignatureFormatTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        priv = Ed25519PrivateKey.generate()
        digest = package_digest(b"imp-0077-test\n")
        rec = sign_record(priv, digest=digest, key_id="k1")
        store = {"k1": priv.public_key().public_bytes_raw().hex()}
        self.assertEqual(verify_signature(digest, rec, store).status, VALID)
        self.assertEqual(check_signature(digest, rec, store), "k1")
        self.assertEqual(verify_wire(encode_record(rec), digest, store).status, VALID)


if __name__ == "__main__":
    unittest.main()
