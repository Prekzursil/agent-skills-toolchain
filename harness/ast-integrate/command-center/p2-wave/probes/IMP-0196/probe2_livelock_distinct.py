#!/usr/bin/env python3
"""Probe 2: bounded livelock is a distinct verdict from deadlock.

Both-states on the loop: a no-write body is LIVELOCK; the converging twin
(writes the convergence key) is CLEAN. A Loop whose body is a mutual-wait
is DEADLOCK, not LIVELOCK — deadlock takes precedence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

OUT = HERE / "probe2-livelock-distinct.raw.json"


def main() -> int:
    reports = {r["fixture"]: r for r in C.corpus_reports()}
    live = reports["bounded_livelock.json"]
    conv = reports["converging_loop.json"]
    body_dl = reports["loop_body_deadlock.json"]
    mw = reports["mutual_wait.json"]

    errors: list[str] = []
    for r in (live, conv, body_dl, mw):
        if not r.get("methods_agree"):
            errors.append(f"{r['fixture']} cycle methods disagree")

    if live.get("verdict") != "LIVELOCK":
        errors.append(f"bounded livelock verdict={live.get('verdict')}")
    if not live.get("livelock_loops"):
        errors.append("bounded livelock listed no loop ids")
    if conv.get("verdict") != "CLEAN":
        errors.append(f"converging twin verdict={conv.get('verdict')}")
    if conv.get("livelock_loops"):
        errors.append("converging twin incorrectly listed as livelock")
    if body_dl.get("verdict") != "DEADLOCK":
        errors.append(f"loop-body mutual-wait verdict={body_dl.get('verdict')} (want DEADLOCK)")
    if mw.get("verdict") != "DEADLOCK":
        errors.append(f"top-level mutual-wait verdict={mw.get('verdict')}")
    if live.get("verdict") == mw.get("verdict"):
        errors.append("livelock collapsed into deadlock")
    if live.get("verdict") == body_dl.get("verdict"):
        errors.append("livelock collapsed into body-deadlock")

    distinct = len({live.get("verdict"), mw.get("verdict"), conv.get("verdict")}) == 3
    if not distinct:
        errors.append(
            f"expected three distinct verdicts, got "
            f"livelock={live.get('verdict')} deadlock={mw.get('verdict')} "
            f"converging={conv.get('verdict')}"
        )

    doc = {
        "probe": "probe2-livelock-distinct",
        "unit_id": "IMP-0196",
        "bounded_livelock": live.get("verdict"),
        "converging_loop": conv.get("verdict"),
        "loop_body_deadlock": body_dl.get("verdict"),
        "mutual_wait": mw.get("verdict"),
        "livelock_loop_ids": live.get("livelock_loops"),
        "verdicts_are_distinct": live.get("verdict") != mw.get("verdict"),
        "three_way_distinct": distinct,
        "pass": not errors,
        "errors": errors,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"livelock={live.get('verdict')} deadlock={mw.get('verdict')} "
        f"converging={conv.get('verdict')} body_deadlock={body_dl.get('verdict')} "
        f"distinct={live.get('verdict') != mw.get('verdict')}"
    )
    if errors:
        print("FAILED:IMP-0196-probe2 " + "; ".join(errors))
        return 1
    print("SUCCESS:IMP-0196-probe2 livelock distinct from deadlock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
