#!/usr/bin/env python3
"""TST-0219 probe 1: origin pinning both-states + confusion refusal + missing-pin.

Good state  : the legitimate private origin serves acme-internal-sdk@1.0.0 and
              the install succeeds with a recorded tree hash.
Bad state A : the same name offered from the public mirror is REFUSED with
              DEPENDENCY_CONFUSION naming package, pinned origin, offered
              origin and integrity - and the destination tree stays empty.
Bad state B : a lockfile without an origin pin fails closed with
              ORIGIN_PIN_MISSING and writes nothing.
Detector    : the public payload is live and distinct (different bytes than the
              private payload), so the refusal is not vacuous.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from resolver import ResolutionRefused, dest_tree_hash, install  # noqa: E402

FIXTURES = HERE / "fixtures"
PRIVATE = "https://registry.private.example"
PUBLIC = "https://registry.public.example"


def build_registries() -> dict[str, Path]:
    if FIXTURES.exists():
        shutil.rmtree(FIXTURES)
    priv = FIXTURES / "private"
    pub = FIXTURES / "public"
    private_payload = b"acme-internal-sdk 1.0.0 PRIVATE payload - internal only\n"
    public_payload = b"acme-internal-sdk 1.0.0 PUBLIC imitation payload\n"
    public_hi = b"acme-internal-sdk 9.9.9 PUBLIC highest-version payload\n"
    for root, version, payload in (
        (priv, "1.0.0", private_payload),
        (pub, "1.0.0", public_payload),
        (pub, "9.9.9", public_hi),
    ):
        d = root / "acme-internal-sdk" / version
        d.mkdir(parents=True, exist_ok=True)
        (d / "payload.txt").write_bytes(payload)
    return {PRIVATE: priv, PUBLIC: pub}


def main() -> int:
    registries = build_registries()
    private_payload = (registries[PRIVATE] / "acme-internal-sdk" / "1.0.0" / "payload.txt").read_bytes()
    integrity = hashlib.sha256(private_payload).hexdigest()
    lockfile = {
        "name": "acme-internal-sdk",
        "version": "1.0.0",
        "origin": PRIVATE,
        "integrity": integrity,
    }

    dest_good = FIXTURES / "dest-good"
    good = install(lockfile, dest_good, registries)

    # Bad state A: pin the private origin for a version the private registry
    # does NOT have, while the public mirror offers the same name.
    lock_confusion = {
        "name": "acme-internal-sdk",
        "version": "2.0.0",
        "origin": PRIVATE,
        "integrity": "0" * 64,
    }
    dest_confused = FIXTURES / "dest-confused"
    refused = None
    try:
        install(lock_confusion, dest_confused, registries)
    except ResolutionRefused as exc:
        refused = exc

    # Bad state B: integrity-only lockfile (no origin pin)
    lock_unpinned = {"name": "acme-internal-sdk", "version": "1.0.0", "integrity": integrity}
    dest_unpinned = FIXTURES / "dest-unpinned"
    unpinned = None
    try:
        install(lock_unpinned, dest_unpinned, registries)
    except ResolutionRefused as exc:
        unpinned = exc

    public_payload = (registries[PUBLIC] / "acme-internal-sdk" / "1.0.0" / "payload.txt").read_bytes()
    empty_sha = hashlib.sha256(b"").hexdigest()

    detail = refused.detail if refused is not None else {}
    detail_unpinned = unpinned.detail if unpinned is not None else {}
    confusion_dest_empty = dest_tree_hash(dest_confused) == empty_sha
    unpinned_dest_empty = dest_tree_hash(dest_unpinned) == empty_sha

    checks = {
        "both_states_private_origin_resolves": good["outcome"] == "SUCCESS"
        and good["installed"]["origin"] == PRIVATE
        and good["tree_sha256"] != empty_sha,
        "integrity_verified_on_install": good["installed"]["integrity"] == integrity,
        "public_mirror_same_name_fails": refused is not None and refused.code == "DEPENDENCY_CONFUSION",
        "refusal_names_package_origin_integrity": (
            detail.get("name") == "acme-internal-sdk"
            and detail.get("pinned_origin") == PRIVATE
            and bool(detail.get("offered_origin"))
            and "integrity" in detail
            and "dependency confusion" in str(detail.get("message", "")).lower()
        ),
        "confused_dest_stays_empty": confusion_dest_empty,
        "negative_unpinned_origin_fails_closed": unpinned is not None and unpinned.code == "ORIGIN_PIN_MISSING",
        "unpinned_dest_stays_empty": unpinned_dest_empty,
        "public_payload_live_and_distinct": public_payload != private_payload,
    }
    out = {
        "probe": "probe1_origin_refusal",
        "unit": "TST-0219",
        "good_install": {"tree_sha256": good["tree_sha256"], "installed": good["installed"]},
        "confusion_refusal": {"code": refused.code if refused else None, "detail": detail},
        "unpinned_refusal": {"code": unpinned.code if unpinned else None, "detail": detail_unpinned},
        "empty_tree_sha256": empty_sha,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe1_origin_refusal.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    shutil.rmtree(FIXTURES, ignore_errors=True)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
