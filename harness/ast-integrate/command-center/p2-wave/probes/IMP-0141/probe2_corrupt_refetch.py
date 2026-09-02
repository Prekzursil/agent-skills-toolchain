#!/usr/bin/env python3
"""Probe 2: corrupted cache entry is detected and refetched, never served.

Both-states:
  good  — clean envelope is a cache-hit of the original bytes
  bad   — bit-flipped / zero-byte / truncated / wrong-schema never return
          planted bytes; get() refetches
  mutant skip-digest — WOULD serve planted bytes (proves the guard is live)
  mutant omit-hashes — broken and fixed packages collide (stale-mask class)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.cachekey import (  # noqa: E402
    SCHEMA,
    ArtifactCache,
    derive_cache_key,
    diagnose_bytes,
    mutant_key_omit_artifact_hashes,
    mutant_serve_without_digest_check,
    mutate_payload_hex_in_place,
)
from agentspec.canonical import dumpb as dumps  # noqa: E402
from inputs import BROKEN_PKG, FIXED_PKG, base_inputs, sha, seven_mutations  # noqa: E402


def main() -> int:
    failures: list[str] = []
    base = base_inputs()
    fixed_inputs = seven_mutations(base)["input_artifact_hashes"]
    fetch_log: list[str] = []

    def fetch_fixed(_inputs) -> bytes:
        fetch_log.append("fixed")
        return FIXED_PKG

    observations: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="imp0141-p2-") as td:
        root = Path(td)
        cache = ArtifactCache(root / "store", fetch=fetch_fixed)

        key = cache.put(base, BROKEN_PKG)
        if key != derive_cache_key(base):
            failures.append("put returned a key other than derive_cache_key")

        clean = cache.get(base)
        if clean.action != "cache-hit" or clean.payload != BROKEN_PKG:
            failures.append(
                f"clean get action={clean.action!r} payload={clean.payload!r}"
            )
        if clean.fetch_invoked or fetch_log:
            failures.append("clean get invoked fetch")
        observations.append(
            {
                "case": "clean-hit",
                "action": clean.action,
                "reason": clean.reason,
                "payload_is_original": clean.payload == BROKEN_PKG,
                "fetch_invoked": clean.fetch_invoked,
            }
        )

        # --- bit-flip: same key, corrupt body, must refetch FIXED, never planted
        planted = b"PLANTED-corrupt-body-must-not-be-served"
        mutate_payload_hex_in_place(cache.path_for(base))
        # After hex flip the stored bytes are neither BROKEN nor planted; plant
        # by rewriting payload_hex to PLANTED while leaving the old digest.
        path = cache.path_for(base)
        doc = {
            "schema": SCHEMA,
            "key": key,
            "payload_digest": __import__("hashlib").sha256(BROKEN_PKG).hexdigest(),
            "payload_hex": planted.hex(),
        }
        path.write_bytes(dumps(doc))

        before_fetch = list(fetch_log)
        flipped = cache.get(base)
        if flipped.action != "refetch":
            failures.append(f"bit-flip action={flipped.action!r} want=refetch")
        if flipped.reason != "payload-digest-mismatch":
            failures.append(f"bit-flip reason={flipped.reason!r}")
        if flipped.payload == planted or flipped.payload == BROKEN_PKG:
            failures.append("bit-flip served planted or stale bytes")
        if flipped.payload != FIXED_PKG:
            failures.append(f"bit-flip did not refetch FIXED got={flipped.payload!r}")
        if not flipped.fetch_invoked or len(fetch_log) != len(before_fetch) + 1:
            failures.append("bit-flip did not invoke fetch")
        if flipped.served_corrupt:
            failures.append("bit-flip marked served_corrupt")
        observations.append(
            {
                "case": "bit-flip",
                "action": flipped.action,
                "reason": flipped.reason,
                "served_planted": flipped.payload == planted,
                "served_fixed": flipped.payload == FIXED_PKG,
                "fetch_invoked": flipped.fetch_invoked,
            }
        )

        # Re-plant without going through put, then the skip-digest mutant.
        path.write_bytes(dumps(doc))
        mutant_payload = mutant_serve_without_digest_check(path)
        mutant_would_serve_planted = mutant_payload == planted
        honest_after_replant = diagnose_bytes(path.read_bytes(), key)
        if honest_after_replant.ok or honest_after_replant.payload is not None:
            failures.append("honest diagnose served planted bytes")
        if not mutant_would_serve_planted:
            failures.append("skip-digest mutant did not serve planted (control inert)")
        observations.append(
            {
                "case": "skip-digest-mutant",
                "mutant_served_planted": mutant_would_serve_planted,
                "honest_ok": honest_after_replant.ok,
                "honest_reason": honest_after_replant.reason,
                "honest_payload_is_none": honest_after_replant.payload is None,
            }
        )

        # zero-byte
        path.write_bytes(b"")
        z = diagnose_bytes(path.read_bytes(), key)
        if z.reason != "zero-byte" or z.payload is not None:
            failures.append(f"zero-byte diagnose={z}")
        cache.fetch = fetch_fixed
        z_get = cache.get(base)
        if z_get.action != "refetch" or z_get.payload != FIXED_PKG:
            failures.append(f"zero-byte get={z_get}")
        observations.append(
            {
                "case": "zero-byte",
                "reason": z.reason,
                "action": z_get.action,
                "served_fixed": z_get.payload == FIXED_PKG,
            }
        )

        # truncated
        path.write_bytes(dumps(doc)[:40])
        t = diagnose_bytes(path.read_bytes(), key)
        if t.reason not in {"truncated", "unparseable"} or t.payload is not None:
            failures.append(f"truncated diagnose={t}")
        t_get = cache.get(base)
        if t_get.action != "refetch" or t_get.payload == planted:
            failures.append(f"truncated get={t_get}")
        observations.append(
            {
                "case": "truncated",
                "reason": t.reason,
                "action": t_get.action,
                "served_planted": t_get.payload == planted,
            }
        )

        # wrong-schema with planted payload and matching digest of planted
        import hashlib as _h

        wrong = {
            "schema": "not-the-cache-schema/v0",
            "key": key,
            "payload_digest": _h.sha256(planted).hexdigest(),
            "payload_hex": planted.hex(),
        }
        path.write_bytes(dumps(wrong))
        w = diagnose_bytes(path.read_bytes(), key)
        if w.reason != "wrong-schema" or w.payload is not None:
            failures.append(f"wrong-schema diagnose={w}")
        w_get = cache.get(base)
        if w_get.action != "refetch" or w_get.payload == planted:
            failures.append(f"wrong-schema served planted action={w_get.action}")
        observations.append(
            {
                "case": "wrong-schema",
                "reason": w.reason,
                "action": w_get.action,
                "served_planted": w_get.payload == planted,
            }
        )

        # stale-mask: honest keys differ when the package hash changes
        broken_key = derive_cache_key(base)
        fixed_key = derive_cache_key(fixed_inputs)
        if broken_key == fixed_key:
            failures.append("honest key ignored input_artifact_hashes")
        omit_broken = mutant_key_omit_artifact_hashes(base)
        omit_fixed = mutant_key_omit_artifact_hashes(fixed_inputs)
        if omit_broken != omit_fixed:
            failures.append("omit-hashes mutant did not collide (control inert)")
        observations.append(
            {
                "case": "stale-mask",
                "honest_keys_differ": broken_key != fixed_key,
                "omit_hashes_collides": omit_broken == omit_fixed,
                "broken_sha": sha(BROKEN_PKG),
                "fixed_sha": sha(FIXED_PKG),
            }
        )

        # After a fix, lookup under the new key must not return BROKEN
        other = ArtifactCache(root / "stale", fetch=lambda _i: FIXED_PKG)
        other.put(base, BROKEN_PKG)
        after_fix = other.get(fixed_inputs)
        if after_fix.payload == BROKEN_PKG:
            failures.append("fixed lookup served the broken payload")
        if after_fix.action != "refetch" or after_fix.payload != FIXED_PKG:
            failures.append(f"fixed lookup {after_fix}")
        observations.append(
            {
                "case": "fixed-package-observed",
                "action": after_fix.action,
                "served_broken": after_fix.payload == BROKEN_PKG,
                "served_fixed": after_fix.payload == FIXED_PKG,
            }
        )

    report = {
        "probe": "probe2-corrupt-refetch",
        "unit_id": "IMP-0141",
        "observations": observations,
        "pass": not failures,
        "failures": failures,
        "clean_is_hit": observations[0]["action"] == "cache-hit" if observations else False,
        "corrupt_never_served": all(
            not o.get("served_planted")
            for o in observations
            if o["case"] in {"bit-flip", "truncated", "wrong-schema"}
        ),
        "skip_digest_mutant_goes_red": any(
            o.get("mutant_served_planted") for o in observations
        ),
        "stale_mask_mutant_collides": any(
            o.get("omit_hashes_collides") for o in observations
        ),
    }
    print(json.dumps(report, sort_keys=True))
    if failures:
        print("FAILED:IMP-0141-probe2 " + "; ".join(failures))
        return 1
    print(
        "SUCCESS:IMP-0141-probe2 corrupt entry refetched never served; "
        "skip-digest mutant would serve planted; hash-omit mutant collides"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
