#!/usr/bin/env python3
"""Named probe 2: (b) recorded entry type (negative vs positive) and ttl.

Independent of probe 1's network-call counter. Reads on-disk type+ttl,
runs the genuine-404 full-ttl both-states control, the EMPTY-cache-OK
regression detector, and the permanent-transient mutant (must go red).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from fetch_cache import (  # noqa: E402
    ABSENCE_TTL_S,
    TRANSIENT_TTL_S,
    TYPE_NEGATIVE_ABSENCE,
    TYPE_NEGATIVE_TRANSIENT,
    TYPE_POSITIVE,
)

UID = "TST-0176"
ART = REPO / "command-center" / "receipts" / "TST-0176.json"
SENTINEL = "SUCCESS:TST-0176"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0176-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")

    types = S.measure_entry_type_and_ttl()
    genuine = S.measure_genuine_404()
    empty = S.measure_empty_not_ok()
    mutant = S.measure_permanent_transient_mutant()
    if not types.get("pass"):
        print(json.dumps(types, indent=2, default=str)[:4000])
        return fail("live type/ttl distinction failed")
    if types["types"]["transient"] != TYPE_NEGATIVE_TRANSIENT:
        return fail("transient not recorded as negative_transient")
    if types["types"]["absence"] != TYPE_NEGATIVE_ABSENCE:
        return fail("404 not recorded as negative_absence")
    if types["types"]["positive"] != TYPE_POSITIVE:
        return fail("200 not recorded as positive")
    if types["ttls"]["transient"] != TRANSIENT_TTL_S:
        return fail("transient ttl mismatch")
    if types["ttls"]["absence"] != ABSENCE_TTL_S:
        return fail("absence ttl mismatch")
    if not genuine.get("pass"):
        print(json.dumps(genuine, indent=2, default=str)[:4000])
        return fail("genuine 404 did not stay cached for full ttl")
    if genuine.get("stayed_cached_past_transient_ttl") is not True:
        return fail("404 escaped the cache before its full ttl")
    if not empty.get("pass"):
        print(json.dumps(empty, indent=2, default=str)[:4000])
        return fail("empty-cache OK detector failed")
    if empty.get("detector_fires_on_mutant") is not True:
        return fail("empty-OK mutant did not go red")
    if empty.get("detector_silent_on_good") is not True:
        return fail("empty-OK detector fired on the honest empty status")
    if not mutant.get("pass"):
        print(json.dumps(mutant, indent=2, default=str)[:4000])
        return fail("permanent-transient mutant did not go red")
    if mutant.get("fired_on_mutant") is not True:
        return fail("mutant still issued a post-ttl retry")
    if mutant.get("silent_on_good") is not True:
        return fail("good cache failed to retry after short ttl")

    tests = doc.get("tests") or {}
    if (tests.get("entry_type_and_ttl") or {}).get("pass") is not True:
        return fail("artifact entry_type_and_ttl.pass is not true")
    if (tests.get("genuine_404_full_ttl") or {}).get("pass") is not True:
        return fail("artifact genuine_404_full_ttl.pass is not true")
    if (tests.get("empty_cache_not_ok") or {}).get("pass") is not True:
        return fail("artifact empty_cache_not_ok.pass is not true")
    if (tests.get("permanent_transient_mutant") or {}).get("pass") is not True:
        return fail("artifact permanent_transient_mutant.pass is not true")

    rec_types = (tests.get("entry_type_and_ttl") or {}).get("types") or {}
    if rec_types.get("transient") != TYPE_NEGATIVE_TRANSIENT:
        return fail("artifact type drift vs live")
    rec_ttls = (tests.get("entry_type_and_ttl") or {}).get("ttls") or {}
    if rec_ttls.get("absence") != ABSENCE_TTL_S:
        return fail("artifact absence ttl drift vs live")

    evidence = doc.get("evidence") or []
    signals = {e.get("id") or e.get("signal") for e in evidence if isinstance(e, dict)}
    if "b" not in signals and "recorded-type-and-ttl" not in signals:
        return fail("artifact missing evidence signal (b)")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        return fail("reviewer verdict is not PASS")

    out = {
        "probe": "probe2-entry-type-ttl",
        "unit_id": UID,
        "pass": True,
        "types": types["types"],
        "ttls": types["ttls"],
        "genuine_404_full_ttl": True,
        "empty_detector_fires_on_mutant": True,
        "permanent_transient_fired": True,
        "reviewer_independent": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"types={types['types']} ttls={types['ttls']} "
        f"404_full_ttl=True empty_ok_mutant_red=True "
        f"permanent_transient_red=True"
    )
    print("SUCCESS:TST-0176-probe2 recorded type/ttl, 404 full-ttl, empty-OK and mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
