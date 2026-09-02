#!/usr/bin/env python3
"""Probe 1: mention corpus zero fires AND use corpus fire on every entry.

A library that passes only one of the two corpora is not a fix. Naive
payload-text matching must still fire on the mention corpus (detector
control: the test can see the false-positive class).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "hooks" / "_shared"))

import corpus as C  # noqa: E402
import use_vs_mention as uvm  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0470.json"
SENTINEL = "SENTINEL:IMP-0470:ROLE-BASED-DETECTION"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    live = C.both_corpora_pass()
    mention = live["mention"]
    use = live["use"]
    print(
        json.dumps(
            {
                "probe": "probe1-both-corpora",
                "mention_n": mention["n"],
                "use_n": use["n"],
                "mention_role_fires": mention["role_fires_ids"],
                "use_role_silent": use["role_silent_ids"],
                "mention_naive_fires": len(mention["naive_fires_ids"]),
                "mention_ok": mention["ok"],
                "use_ok": use["ok"],
                "both_ok": live["ok"],
            },
            sort_keys=True,
        )
    )
    if mention["n"] < 8 or use["n"] < 8:
        print("FAILED:IMP-0470-probe1 corpora too small")
        return 1
    if mention["role_fires_ids"]:
        print(f"FAILED:IMP-0470-probe1 mention corpus fired {mention['role_fires_ids']}")
        return 1
    if use["role_silent_ids"]:
        print(f"FAILED:IMP-0470-probe1 use corpus silent {use['role_silent_ids']}")
        return 1
    if len(mention["naive_fires_ids"]) != mention["n"]:
        print("FAILED:IMP-0470-probe1 naive matcher did not fire on every mention (inert control)")
        return 1
    if not mention["ok"] or not use["ok"] or not live["ok"]:
        print("FAILED:IMP-0470-probe1 one corpus only is not a fix")
        return 1
    chk = uvm.self_check()
    if not chk["ok"]:
        print("FAILED:IMP-0470-probe1 library self-check")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0470-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:IMP-0470-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0470-probe1 sentinel-absent")
        return 1
    meas = doc.get("measurement") or {}
    art_m = int((meas.get("mention") or {}).get("n") or -1)
    art_u = int((meas.get("use") or {}).get("n") or -1)
    if art_m != mention["n"] or art_u != use["n"]:
        print(
            f"FAILED:IMP-0470-probe1 receipt corpus n mismatch "
            f"art=({art_m},{art_u}) live=({mention['n']},{use['n']})"
        )
        return 1
    if (meas.get("mention") or {}).get("role_fires") != 0:
        print("FAILED:IMP-0470-probe1 receipt mention role_fires != 0")
        return 1
    if (meas.get("use") or {}).get("role_silent") != 0:
        print("FAILED:IMP-0470-probe1 receipt use role_silent != 0")
        return 1
    if meas.get("both_corpora_pass") is not True:
        print("FAILED:IMP-0470-probe1 receipt both_corpora_pass not true")
        return 1
    lib = REPO / "hooks/_shared/use_vs_mention.py"
    if not lib.is_file() or lib.stat().st_size < 1024:
        print("FAILED:IMP-0470-probe1 shared library missing")
        return 1
    print(
        f"mention_n={mention['n']} use_n={use['n']} "
        f"mention_fires=0 use_silent=0 naive_mention={len(mention['naive_fires_ids'])}"
    )
    print("SUCCESS:IMP-0470-probe1 mention-zero and use-every-entry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
