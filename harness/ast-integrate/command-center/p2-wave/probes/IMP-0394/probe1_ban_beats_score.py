#!/usr/bin/env python3
"""Probe 1: owner ban beats score 0.99; precedence is printed, not implied.

Negative control: an unbanned capability scoring 0.99 is admitted and stays
on the router.score path. A name with no override (cap.plain) must not enter
ban/pin classification.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0394-probe1 {msg}")
    return 1


def main() -> int:
    S.require_receipt()
    m = S.measure_ban_beats_score()
    print(json.dumps({**m, "probe": "probe1-ban-beats-score", "unit_id": "IMP-0394"}, sort_keys=True))
    if not m["pass"]:
        return fail("ban-beats-score measurement did not pass")
    if m["banned_admitted"]:
        return fail("banned capability scoring 0.99 was admitted")
    if m["banned_layer"] != "owner.ban":
        return fail(f"banned layer {m['banned_layer']}")
    if not m["unbanned_admitted"]:
        return fail("negative control unbanned 0.99 was not admitted")
    if m["unbanned_layer"] != "router.score":
        return fail("unbanned 0.99 left the score path")
    if m["plain_layer"] != "router.score":
        return fail("cap.plain entered an override layer")
    if not m["decision_echoes_printed_table"]:
        return fail("apply_overrides omitted the printed precedence table")
    print(
        "ban_beats_0.99=True unbanned_admitted=True plain_stays_on_score=True "
        "precedence_printed=True"
    )
    print("SUCCESS:IMP-0394-probe1 ban beats score 0.99; precedence printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
