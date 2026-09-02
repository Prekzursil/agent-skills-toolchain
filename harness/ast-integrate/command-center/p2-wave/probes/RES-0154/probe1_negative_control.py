#!/usr/bin/env python3
"""Probe 1: negative control — known-correct artifacts yield zero surviving refutations."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import experiment as E  # noqa: E402
from util import OUT_REL, SENTINEL  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0154-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 1024:
        return fail("artifact missing or too small")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    live = E.run_experiment()
    nc = live["negative_control"]
    art_nc = doc.get("negative_control") or {}
    print(f"known_correct_ids={nc['known_correct_ids']}")
    print(
        f"honest_emitted_on_known_correct={nc['honest_emitted_on_known_correct']} "
        f"honest_surviving={nc['honest_surviving']}"
    )
    print(
        f"noisy_emitted_on_known_correct={nc['noisy_emitted_on_known_correct']} "
        f"noisy_surviving={nc['noisy_surviving']}"
    )
    if nc["honest_surviving"] != 0:
        return fail("honest refuter produced surviving findings on known-correct")
    if nc["honest_emitted_on_known_correct"] != 0:
        return fail("honest refuter emitted on known-correct (nonzero floor)")
    if nc["noisy_surviving"] != 0:
        return fail("noisy nits survived on known-correct")
    if nc["noisy_emitted_on_known_correct"] <= 0:
        return fail("noisy refuter did not emit a floor on known-correct")
    if not nc["pass"]:
        return fail("negative_control.pass is false")
    if int(art_nc.get("honest_surviving", -1)) != 0:
        return fail("artifact honest_surviving drifted")
    if int(art_nc.get("noisy_emitted_on_known_correct", -1)) != int(
        nc["noisy_emitted_on_known_correct"]
    ):
        return fail("artifact noisy floor drifted")

    hon = live["ranking_honest"]
    vol = live["ranking_volume"]
    print(f"ranking_honest={hon}")
    print(f"ranking_volume={vol}")
    if hon[0] != "honest_refuter":
        return fail("honest score did not rank honest_refuter first")
    if vol[0] == "honest_refuter":
        return fail("volume score unexpectedly ranked honest_refuter first")
    if not live["volume_ranking_differs"]:
        return fail("volume ranking did not differ from honest ranking")
    if doc.get("volume_ranking_differs") is not True:
        return fail("artifact volume_ranking_differs drifted")

    print("NEGATIVE CONTROL: known-correct schemas -> 0 surviving refutations")
    print("noisy floor emits on known-correct but does not survive the third agent")
    print("volume scoring would rank finder/noisy above the honest refuter")
    print("SUCCESS:RES-0154-probe1 negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
