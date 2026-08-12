"""Verify a self-describing receipt's ELIDED digest, and PROVE the elision is
necessary rather than an excuse.

A receipt cannot contain its own sha256: that would be a hash fixed point. The
family convention (see ADV-0024 extensions.self_digest_recipe) is to publish the
digest of the file with artifacts[0].sha256 blanked to 64 zeros.

This tool checks BOTH states, so its silence means something:
  GOOD state  - recompute the elided digest; it must EQUAL the declared value.
  BAD  state  - mutate one byte of the receipt; the elided digest must CHANGE.
A checker that passed in both states would be measuring nothing.

usage: python verify_elided_digest.py <receipt.json> [...]

ROUND-2 FIX (defect D2, confirmed by the adversarial audit of build round 1). This tool
previously FAILED OPEN on empty input: `python verify_elided_digest.py` with no arguments
printed nothing and exited 0, so a zero-input invocation was indistinguishable from two
passing verifications -- in a tool whose entire purpose is anti-fabrication. That is the
ci-hygiene "empty walk must fail closed" shape. It now refuses, non-zero, with a marker.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys

FAIL = 0

PATHS = sys.argv[1:]
if not PATHS:
    print(
        "FAILED:elided-digest no inputs -- an empty walk is a detector failure, not a pass. "
        "usage: python verify_elided_digest.py <receipt.json> [...]"
    )
    raise SystemExit(2)


def elide(text: str, declared: str) -> str:
    """Replace the declared digest with 64 zeros exactly once, in the artifacts[0] slot."""
    return re.sub(re.escape(declared), "0" * 64, text, count=1)


for path in PATHS:
    raw = io.open(path, encoding="utf-8", newline="").read()
    doc = json.loads(raw)
    declared = doc["artifacts"][0]["sha256"]
    declared_bytes = doc["artifacts"][0]["bytes"]
    on_disk_bytes = len(raw.encode("utf-8"))
    naive = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    good = hashlib.sha256(elide(raw, declared).encode("utf-8")).hexdigest()
    # BAD state: flip a character in a value far from the digest, then re-elide.
    bad_raw = raw.replace('"schema_version": 1', '"schema_version": 2', 1)
    assert bad_raw != raw, "mutation did not apply - the control is inert"
    bad = hashlib.sha256(elide(bad_raw, declared).encode("utf-8")).hexdigest()

    ok_good = good == declared
    ok_bad = bad != declared
    ok_bytes = declared_bytes == on_disk_bytes
    ok = ok_good and ok_bad and ok_bytes
    FAIL |= 0 if ok else 1

    print(f"=== {path}")
    print(f"  declared sha256      : {declared}")
    print(f"  recomputed (elided)  : {good}   MATCH={ok_good}")
    print(f"  naive whole-file sha : {naive}")
    print(
        "    ^ this is what a plain re-hash sees; it CANNOT equal the declared value,"
    )
    print(
        "      because the file would then have to contain its own digest (a fixed point)."
    )
    print(
        f"  mutated-state digest : {bad}   CHANGED={ok_bad}  (control: detector is live)"
    )
    print(
        f"  declared bytes       : {declared_bytes}  on-disk {on_disk_bytes}  MATCH={ok_bytes}"
    )
    print(f"  VERDICT: {'SUCCESS' if ok else 'FAILED'}:elided-digest {path}")

sys.exit(FAIL)
