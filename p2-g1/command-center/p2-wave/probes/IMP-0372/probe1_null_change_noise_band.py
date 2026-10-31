#!/usr/bin/env python3
"""IMP-0372 probe1: null-change control establishes the MEASURED noise band.

The band is measured from repeated identical runs on the same harness, is
labelled measured (assumed=False), and is compared-against measured-band
rather than zero. The band is then handed to probe2 via its own measurement.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from selfimprove.measure import Harness, measure_null_change  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0372.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0372-probe1 {msg}")
    return 1


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    with tempfile.TemporaryDirectory() as td:
        origin = Path(td)
        (origin / "score.base").write_text("100\n", encoding="utf-8")
        first = measure_null_change(origin, harness=Harness(), parent=origin,
                                    label="probe1-null-run-1")
        second = measure_null_change(origin, harness=Harness(), parent=origin,
                                     label="probe1-null-run-2")
        band = first["noise_band"]
        if band["assumed"] is not False:
            return fail("band-assumed")
        if band["source"] != "measured-null-change":
            return fail("band-source")
        if band["n"] < 6 or len(band["samples"]) != band["n"]:
            return fail(f"band-n:{band['n']}")
        if band["compared_against_zero"] is not False:
            return fail("band-compared-vs-zero")
        if first["compared_against"] != "measured-band":
            return fail("compared-against-field")
        # Determinism: identical harness twice -> identical samples.
        if band["samples"] != second["noise_band"]["samples"]:
            return fail("band-not-deterministic")
        if first["isolation"]["origin_unchanged"] is not True:
            return fail("origin-changed")

    print(json.dumps({
        "probe": "probe1-null-change-noise-band", "unit_id": "IMP-0372",
        "pass": True,
        "band": {"n": band["n"], "width": band["width"],
                 "samples": band["samples"],
                 "assumed": False, "source": "measured-null-change"},
        "compared_against": "measured-band",
        "deterministic": True,
    }, sort_keys=True))
    print("SUCCESS:IMP-0372-probe1 null-change band measured, assumed=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
