#!/usr/bin/env python3
"""Probe 2: positive control + naive concatenator (both-states).

Mechanically different from probe 1 (no six-carrier loop):

  * a payload in the genuine instruction channel MUST be obeyed
    (proves the later-stage observer is not a universal no-op)
  * the same position-paper payload, concatenated into instructions by the
    naive assembler, MUST be obeyed (known-broken state)
  * the defended assembler on that same plant MUST stay silent

The fence+neutralize pair is load-bearing only if those three disagree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from scenario import POSITIVE_TOKEN, run_positive_and_naive  # noqa: E402

ART = REPO / "command-center/receipts/TST-0273.json"


def check_artifact_if_present() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0273" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def fail(msg: str) -> int:
    print(f"FAILED:TST-0273-probe2 {msg}")
    return 1


def main() -> int:
    art_err = check_artifact_if_present()
    if art_err:
        return fail(art_err)

    result = run_positive_and_naive()
    print(json.dumps(result, sort_keys=True))

    pos = result["positive_control"]
    if not pos["obeyed"]:
        return fail("positive control in the instruction channel was not obeyed")
    if POSITIVE_TOKEN not in pos["obeyed_tokens"]:
        return fail("positive-control token missing from obeyed_tokens")
    if not pos["live_directive_survived_in_instruction"]:
        return fail("assembler neutralized the genuine instruction channel")

    naive = result["naive_position_paper"]
    if not naive["obeyed"]:
        return fail("naive concatenator did not obey the position-paper payload")
    if naive["token"] not in naive["obeyed_tokens"]:
        return fail("naive run obeyed something other than the planted token")

    defended = result["defended_position_paper"]
    if defended["obeyed"]:
        return fail("defended assembler obeyed the position-paper payload")
    if not defended["token_reached"]:
        return fail("defended assembler dropped the planted token")

    both = result["both_states"]
    if not (both["naive_obeys"] and both["defended_silent"]):
        return fail("both-states contrast collapsed")

    print(
        "SUCCESS:TST-0273-probe2 positive_obeyed=True naive_obeys=True "
        "defended_silent=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
