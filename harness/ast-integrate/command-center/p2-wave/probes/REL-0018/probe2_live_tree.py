#!/usr/bin/env python3
"""Probe 2: today's tree is NO-GO; condition 13 reads REL-0003, never hardcodes canary."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from evaluator import evaluate, fingerprint  # noqa: E402
from fixtures import write_canary_decoy, write_green_tree  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:REL-0018-probe2 {msg}")
    return 1


def main() -> int:
    live = evaluate(REPO)
    if live["decision"] == "GO":
        return _fail("live tree GO — evaluator is not reading real evidence")
    if len(live["conditions"]) != 21:
        return _fail(f"row count {len(live['conditions'])}")
    ids = [r["id"] for r in live["conditions"]]
    if ids != list(range(1, 22)):
        return _fail(f"ids={ids}")
    for row in live["conditions"]:
        if row["verdict"] not in ("TRUE", "FALSE", "NOT-CHECKED"):
            return _fail(f"bad verdict id={row['id']} {row['verdict']}")
        if row["evaluation_kind"] != "file-read":
            return _fail(f"inference folded id={row['id']}")
    c13 = next(r for r in live["conditions"] if r["id"] == 13)
    if c13["hardcoded_canary"] is not False:
        return _fail("condition 13 hardcoded canary")
    if "REL-0003" not in c13["anchor"] and "REL-0003" not in c13["ruling_source"]:
        return _fail(f"condition 13 did not point at REL-0003: {c13['anchor']}")
    if live["condition_13"]["hardcoded_canary"] is not False:
        return _fail("report hardcoded_canary")
    if live["condition_13"]["ruling_source"] != "command-center/receipts/REL-0003.json":
        return _fail("ruling_source mismatch")

    live2 = evaluate(REPO)
    if fingerprint(live) != fingerprint(live2):
        return _fail("live re-run fingerprint mismatch")

    tmp = Path(tempfile.mkdtemp(prefix="rel0018-p2-"))
    try:
        green = tmp / "green"
        write_green_tree(green)
        g = evaluate(green)
        g13 = next(r for r in g["conditions"] if r["id"] == 13)
        if g13["verdict"] != "TRUE":
            return _fail(f"ruling+receipts should make 13 TRUE, got {g13['verdict']} {g13['reason']}")
        if g["decision"] != "GO":
            return _fail("full green fixture not GO")

        decoy = tmp / "decoy"
        decoy.mkdir()
        write_canary_decoy(decoy)
        d = evaluate(decoy)
        d13 = next(r for r in d["conditions"] if r["id"] == 13)
        if d13["verdict"] != "NOT-CHECKED":
            return _fail(
                f"canary decoy without REL-0003 yielded {d13['verdict']} — hardcoded?"
            )
        if d["decision"] != "NO-GO":
            return _fail("decoy tree GO")
        if d13["ruling_present"] is not False:
            return _fail("decoy claimed REL-0003 present")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(
        f"live_decision={live['decision']} "
        f"TRUE={live['counts']['TRUE']} "
        f"FALSE={live['counts']['FALSE']} "
        f"NOT-CHECKED={live['counts']['NOT-CHECKED']} "
        f"c13={c13['verdict']} c13_hardcoded=False "
        "ruling_read=True decoy_ignored=True reproducible=True"
    )
    print("SUCCESS:REL-0018-probe2 live-NO-GO condition-13-reads-REL-0003")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
