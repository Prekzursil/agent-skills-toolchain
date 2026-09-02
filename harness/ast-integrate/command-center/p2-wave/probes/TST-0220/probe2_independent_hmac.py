#!/usr/bin/env python3
"""Probe 2: independent OpenSSL HMAC/digest check (does not call verify_package).

Same four fixtures as probe 1. Trust is a key-id set membership check computed
with hashlib, not marketplace.sign.key_id_of. MAC and digest are OpenSSL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import (  # noqa: E402
    build_fixtures,
    independent_key_id,
    openssl_hmac_hex,
    openssl_sha256_hex,
    public_meta,
    stdlib_hmac_hex,
)


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAILED:TST-0220-probe2 {msg}")


def main() -> int:
    fx = build_fixtures()
    meta = public_meta(fx)
    trusted = fx["trusted_key"]
    untrusted = fx["untrusted_key"]
    trust_ids = {independent_key_id(trusted)}
    _need(independent_key_id(trusted) == meta["trusted_id"], "independent key id drifted")
    _need(independent_key_id(untrusted) == meta["untrusted_id"], "untrusted key id drifted")
    _need(meta["trusted_id"] not in {independent_key_id(untrusted)}, "key ids collided")

    valid = fx["cases"]["valid_twin"]
    unsigned = fx["cases"]["unsigned"]
    untrusted_case = fx["cases"]["untrusted_key"]
    tampered = fx["cases"]["content_tampered"]

    # Valid twin: OpenSSL MAC and digest match the record; key id is trusted.
    ossl_mac = openssl_hmac_hex(valid["payload"], trusted)
    ossl_dig = openssl_sha256_hex(valid["payload"])
    rec = valid["record"]
    _need(ossl_mac == rec["mac"], "openssl hmac != record mac on valid twin")
    _need(ossl_dig == rec["digest"], "openssl sha256 != record digest on valid twin")
    _need(rec["key_id"] in trust_ids, "valid twin key id not in independent trust set")
    _need(stdlib_hmac_hex(valid["payload"], trusted) == ossl_mac, "stdlib hmac != openssl")
    valid_independent = {
        "accepted": True,
        "reason": "ok",
        "openssl_mac_match": True,
        "openssl_digest_match": True,
        "trusted": True,
    }

    # Unsigned: no record. Independent check must not treat absence as ok.
    _need(unsigned["record"] is None, "unsigned fixture grew a record")
    unsigned_independent = {
        "accepted": False,
        "reason": "unsigned",
        "has_record": False,
    }

    # Untrusted: OpenSSL MAC verifies under the untrusted key (signature is
    # real) but the independent trust set does not contain that key id.
    urec = untrusted_case["record"]
    ossl_untrusted_mac = openssl_hmac_hex(untrusted_case["payload"], untrusted)
    _need(ossl_untrusted_mac == urec["mac"], "untrusted signature is not a live hmac")
    _need(urec["key_id"] not in trust_ids, "untrusted key id leaked into trust set")
    _need(
        openssl_hmac_hex(untrusted_case["payload"], trusted) != urec["mac"],
        "untrusted mac unexpectedly verified under the trusted key",
    )
    untrusted_independent = {
        "accepted": False,
        "reason": "untrusted-key",
        "openssl_mac_valid_under_signer": True,
        "trusted": False,
        "signer_key_id": urec["key_id"],
    }

    # Tampered: flip one byte after signing. OpenSSL digest and MAC diverge.
    trec = tampered["record"]
    ossl_t_dig = openssl_sha256_hex(tampered["payload"])
    ossl_t_mac = openssl_hmac_hex(tampered["payload"], trusted)
    _need(ossl_t_dig != trec["digest"], "openssl digest still matches after flip")
    _need(ossl_t_mac != trec["mac"], "openssl hmac still matches after flip")
    _need(trec["key_id"] in trust_ids, "tampered case dropped the trusted key id")
    tampered_independent = {
        "accepted": False,
        "reason": "content-tampered",
        "openssl_digest_match": False,
        "openssl_mac_match": False,
        "trusted": True,
        "record_digest": trec["digest"],
        "live_digest": ossl_t_dig,
    }

    rows = {
        "valid_twin": valid_independent,
        "unsigned": unsigned_independent,
        "untrusted_key": untrusted_independent,
        "content_tampered": tampered_independent,
    }
    for name, row in rows.items():
        want_accept = name == "valid_twin"
        _need(row["accepted"] is want_accept, f"{name} independent accepted={row['accepted']}")

    doc = {
        "probe": "probe2-independent-hmac",
        "unit_id": "TST-0220",
        "pass": True,
        "implementation": "openssl dgst -sha256 -mac HMAC + independent key-id set",
        "does_not_call": "marketplace.sign.verify_package",
        "meta": {
            "trusted_id": meta["trusted_id"],
            "untrusted_id": meta["untrusted_id"],
            "payload_sha256": meta["payload_sha256"],
            "tampered_sha256": meta["tampered_sha256"],
        },
        "independent": rows,
    }
    print(json.dumps(doc, sort_keys=True))
    print(
        "SUCCESS:TST-0220-probe2 openssl hmac/digest agrees: valid twin ok; "
        "unsigned/untrusted/tampered rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
