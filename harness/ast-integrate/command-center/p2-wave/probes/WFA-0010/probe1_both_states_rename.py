#!/usr/bin/env python3
"""Probe 1: both-states rename control.

Without the migration map, renaming 10 bound ids must leave dangling graph
refs. With the map, the identical 10 renames must leave zero dangling refs.
A single green run is not evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0010-id-stability-and-migration-map.json"
SENTINEL = "SUCCESS:WFA-0010"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0010-probe1 {msg}")
    return 1


def main() -> int:
    data = C.build_corpus()
    mutation = data["mutation"]
    without = int(mutation["without_dangling"])
    with_map = int(mutation["with_dangling"])
    print(
        f"rename_count={mutation['rename_count']} "
        f"without_map_dangling={without} with_map_dangling={with_map} "
        f"stale_identity_dangling={mutation['without_map_identity_still_dangling']}"
    )
    if mutation["rename_count"] != 10:
        return fail(f"expected 10 renames, got {mutation['rename_count']}")
    if without <= 0:
        return fail("without-map dangling count is not greater than zero")
    if with_map != 0:
        return fail(f"with-map dangling count is {with_map}, expected 0")
    if not mutation["pair_ok"]:
        return fail("pair_ok is false")
    if int(mutation["without_map_identity_still_dangling"]) <= 0:
        return fail("stale identity freeze did not dangle")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    ev = doc.get("evidence") or {}
    a = ev.get("A") or {}
    b = ev.get("B") or {}
    a_dangle = a.get("dangling_count")
    b_dangle = b.get("dangling_count")
    if not isinstance(a_dangle, int) or a_dangle <= 0:
        return fail("artifact evidence A is not > 0")
    if b_dangle != 0:
        return fail("artifact evidence B is not 0")
    if set((a.get("renames") or {}).keys()) != set(mutation["renamed_ids"].keys()):
        return fail("artifact rename set drifted from live mutation")
    print("SUCCESS:WFA-0010-probe1 both-states rename control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
