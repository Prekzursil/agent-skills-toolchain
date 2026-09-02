#!/usr/bin/env python3
"""Named probe 1: dual-rail hashes, HTTP statuses, sentinel, anti-adoption verdict.

Signal 1 is sha256 of stored capture bytes vs the artifact's recorded sha256.
Signal 2 is HTTP 2xx + api/prose kind pair. A claim with one rail is E3 and
fails. Does not score quote presence (that is probe 2's partition).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checker as C  # noqa: E402


def main() -> int:
    art = C.REPO / C.ART_REL
    if not art.is_file() or art.stat().st_size < 1024:
        print("FAILED:RES-0067-probe1 artifact missing or thin")
        return 1
    doc = C.load_artifact()
    ok, why = C.check_structure(doc)
    print(f"structure_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0067-probe1 structure")
        return 1
    ok, why = C.check_rails(doc)
    print(f"rails_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0067-probe1 rails")
        return 1
    ok, why = C.check_anti_adoption(doc)
    print(f"anti_adoption_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0067-probe1 anti-adoption")
        return 1

    mutant = copy.deepcopy(doc)
    rails = mutant["claims"][0]["rails"]
    dropped = rails.pop()
    mok, mwhy = C.check_rails(mutant)
    print(f"single_rail_mutant_ok={mok} {mwhy} dropped_kind={dropped.get('kind')}")
    if mok:
        print("FAILED:RES-0067-probe1 single-rail mutant was accepted")
        return 1

    mutant2 = copy.deepcopy(doc)
    mutant2["claims"][0]["rails"][0]["sha256"] = "0" * 64
    mok, mwhy = C.check_rails(mutant2)
    print(f"sha_mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0067-probe1 sha mutant was accepted")
        return 1

    text = art.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        print("FAILED:RES-0067-probe1 sentinel absent from file bytes")
        return 1
    print(
        "SUCCESS:RES-0067-probe1 dual-rail hashes HTTP sentinel "
        f"claims={len(doc.get('claims') or [])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
