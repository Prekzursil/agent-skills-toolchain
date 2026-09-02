#!/usr/bin/env python3
"""Named probe 2: per-field gold scores, numeric fan-out, round-trip reader.

Mechanically independent of probe 1: this probe scores extraction against
the frozen 20-record gold, requires fan_out_degree to be int or JSON null,
and requires a reader who sees only rendered prose to recover the source
from two decoys.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extractor import extract  # noqa: E402
from score import (  # noqa: E402
    FIELDS,
    fan_out_is_numeric_or_null,
    load_corpus,
    round_trip,
    score_gold,
)

ART = REPO / "command-center/wfa/WFA-0036-extract-stages.json"
UNIT = "WFA-0036"
FLOOR = 0.9
ROUND_TRIP_FLOOR = 0.9


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:WFA-0036" not in blob:
        return fail("sentinel absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live = score_gold()
    per_field = live["per_field"]
    for field in FIELDS:
        acc = per_field[field]["accuracy"]
        if acc < FLOOR:
            return fail(f"gold field {field} below floor", per_field)
        if per_field[field]["n"] < 1:
            return fail(f"gold field {field} has n=0")

    art_scores = (doc.get("gold_scores") or {}).get("per_field") or {}
    for field in FIELDS:
        live_acc = round(per_field[field]["accuracy"], 6)
        art_acc = round(float((art_scores.get(field) or {}).get("accuracy") or -1), 6)
        if live_acc != art_acc:
            return fail(
                "artifact gold accuracy drifted from live score",
                {"field": field, "live": live_acc, "artifact": art_acc},
            )

    for rec in load_corpus():
        got = extract(rec["native"])
        if not fan_out_is_numeric_or_null(got):
            return fail("fan_out_degree not int-or-null", {"id": rec["id"], "got": got})

    rt = round_trip()
    if rt["accuracy"] < ROUND_TRIP_FLOOR:
        return fail("round-trip reader below floor", {"accuracy": rt["accuracy"]})
    art_rt = (doc.get("round_trip") or {}).get("accuracy")
    if art_rt is None or abs(float(art_rt) - rt["accuracy"]) > 1e-9:
        return fail("artifact round-trip accuracy drifted", {"live": rt["accuracy"], "artifact": art_rt})

    payload = {
        "pass": True,
        "probe": "probe2-gold-roundtrip",
        "unit_id": UNIT,
        "per_field": {k: v["accuracy"] for k, v in per_field.items()},
        "round_trip_accuracy": rt["accuracy"],
        "fan_out_numeric_or_null": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"SUCCESS:{UNIT}-probe2 per-field gold >= {FLOOR}; "
        f"round-trip={rt['accuracy']:.2f}; fan_out numeric-or-null"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
