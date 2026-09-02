#!/usr/bin/env python3
"""Probe 2: mutation control — in-place write must expose PARTIAL reads.

Independent of probe 1: re-runs the campaign and requires the detector to
go red when atomic replace is swapped for a direct truncate-write.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

ART = REPO / H.OUT_REL
SENTINEL = "SUCCESS:TST-0156"


def main() -> int:
    live = H.run_campaign()
    direct = live["direct"]
    atomic = live["atomic"]
    print(
        json.dumps(
            {
                "probe": "probe2-mutation-direct-write",
                "unit_id": H.UNIT,
                "pass": live["pass"],
                "mutation_ok": live["mutation_ok"],
                "direct_after_partial": direct["after_partial"],
                "atomic_after_partial": atomic["after_partial"],
                "cancel_n": live["cancel_n"],
            },
            sort_keys=True,
        )
    )
    if direct["after_partial"] != live["cancel_n"]:
        print(
            "FAILED:TST-0156-probe2 mutation did not produce partial reads "
            f"got={direct['after_partial']} want={live['cancel_n']}"
        )
        return 1
    if atomic["after_partial"] != 0:
        print("FAILED:TST-0156-probe2 atomic path grew partials; detector confused")
        return 1
    if not live["mutation_ok"]:
        print("FAILED:TST-0156-probe2 mutation_ok false")
        return 1
    if not ART.is_file():
        print("FAILED:TST-0156-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0156-probe2 receipt self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0156-probe2 sentinel absent")
        return 1
    rec_direct = ((doc.get("campaign") or {}).get("direct") or {})
    rec_atomic = ((doc.get("campaign") or {}).get("atomic") or {})
    rec_d = rec_direct.get("after_partial")
    rec_a = rec_atomic.get("after_partial")
    if rec_d is None or int(rec_d) != live["cancel_n"]:
        print("FAILED:TST-0156-probe2 receipt mutation count drift")
        return 1
    if rec_a is None or int(rec_a) != 0:
        print("FAILED:TST-0156-probe2 receipt atomic partial drift")
        return 1
    tests = {t["id"]: t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "uncancelled-publish",
        "cancel-atomic-200",
        "mutation-direct-write",
        "orphan-tmp-scan",
    ):
        if (tests.get(tid) or {}).get("result") != "PASS":
            print(f"FAILED:TST-0156-probe2 test {tid} not PASS")
            return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        print("FAILED:TST-0156-probe2 reviewer not independent PASS")
        return 1
    print(
        f"mutation_partials={direct['after_partial']}/{live['cancel_n']} "
        f"atomic_partials={atomic['after_partial']}"
    )
    print("SUCCESS:TST-0156-probe2 mutation control fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
