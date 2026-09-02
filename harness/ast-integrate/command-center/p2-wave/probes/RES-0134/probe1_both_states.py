#!/usr/bin/env python3
"""Probe 1: both-states control — recipe-off digests differ; recipe-on matches.

Proves equality is caused by the recipe, not an insensitive comparator:
archive bytes are hashed with sha256; two distinct blobs must differ.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import (  # noqa: E402
    AXES,
    CANON,
    JUNK,
    definition_sha256,
    measure,
    sha256_bytes,
)
from recipe import pack_stored, pack_zipfile  # noqa: E402

REPO = HERE.parents[3]
ART = (
    REPO
    / "command-center"
    / "research"
    / "supply-chain"
    / "RES-0134-reproducible-build-for-asset-packages.json"
)
SENTINEL = "SUCCESS:RES-0134"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0134-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if doc.get("unit_id") != "RES-0134":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    recorded = doc.get("definition") or {}
    live_hash = definition_sha256()
    if recorded.get("sha256") != live_hash:
        return fail("artifact definition.sha256 does not match DEFINITION.json")
    if recorded.get("frozen_before_count") is not True and recorded.get(
        "frozen_before_count"
    ) is not True:
        return fail("definition not marked frozen_before_count")
    if recorded.get("same_rule_all_vendors") is not True and recorded.get(
        "same_rule_all_vendors"
    ) is not True:
        return fail("same_rule_all_vendors is not true")
    if doc.get("definition_locked_hash_before_enumerate") is not True and doc.get(
        "definition_locked_hash_before_enumerate"
    ) is not True:
        return fail("hash was not locked before enumeration")

    live = measure()
    tp = live["two_platform"]
    if not tp["recipe_off_digests_differ"]:
        return fail("recipe-off Linux-sim vs Windows-sim digests did not differ")
    if not tp["recipe_on_zipfile_equal"]:
        return fail("recipe-on zipfile Linux-sim vs Windows-sim digests differ")
    if not tp["recipe_on_stored_equal"]:
        return fail("recipe-on stored Linux-sim vs Windows-sim digests differ")
    if not live["hygiene_excludes_git_and_pyc"]:
        return fail("normalized members still include .git or __pycache__")

    art_tp = doc.get("two_platform") or {}
    for key in (
        "linux_recipe_off_sha256",
        "windows_recipe_off_sha256",
        "linux_recipe_on_sha256",
        "windows_recipe_on_sha256",
    ):
        if art_tp.get(key) != tp.get(key):
            return fail(f"artifact two_platform.{key} drifted from live re-pack")

    members = dict(CANON)
    members.update(JUNK)
    off_a = pack_zipfile(
        list(members.items()),
        date_time=(2026, 1, 15, 8, 30, 0),
        create_system=3,
        normalize=False,
    )
    win_items: list[tuple[str, bytes]] = []
    for name, body in members.items():
        win_items.append((name.replace("/", "\\"), body.replace(b"\n", b"\r\n")))
    win_items.reverse()
    off_b = pack_zipfile(
        win_items,
        date_time=(2024, 8, 24, 12, 0, 0),
        create_system=0,
        external_attr=0,
        normalize=False,
    )
    on_a = pack_zipfile(list(members.items()), normalize=True)
    on_b = pack_zipfile(win_items, normalize=True)
    ha, hb = sha256_bytes(off_a), sha256_bytes(off_b)
    oa, ob = sha256_bytes(on_a), sha256_bytes(on_b)
    if ha == hb:
        return fail("independent recipe-off pair collided (insensitive comparator?)")
    if oa != ob:
        return fail("independent recipe-on pair diverged")
    if hashlib.sha256(off_a).hexdigest() != ha:
        return fail("sha256 comparator is not hashing archive bytes")
    stored_a = pack_stored(list(members.items()), normalize=True)
    stored_b = pack_stored(win_items, normalize=True)
    if sha256_bytes(stored_a) != sha256_bytes(stored_b):
        return fail("independent stored recipe-on pair diverged")

    broke = {row["vendor_id"]: row["broke_identity"] for row in live["axes"]}
    for axis in AXES:
        if not broke.get(axis):
            return fail(f"expected {axis} to break identity")

    payload = {
        "probe": "probe1-both-states",
        "unit_id": "RES-0134",
        "definition_sha256": live_hash,
        "frozen_before_count": True,
        "recipe_off_differ": True,
        "recipe_on_equal": True,
        "linux_off": ha[:16],
        "windows_off": hb[:16],
        "recipe_on": oa[:16],
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:RES-0134-probe1 both-states: recipe-off digests differ; "
        "recipe-on matches; comparator hashes archive bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
