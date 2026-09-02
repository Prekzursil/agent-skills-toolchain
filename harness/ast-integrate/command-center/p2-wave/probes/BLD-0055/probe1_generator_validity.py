#!/usr/bin/env python3
"""Probe 1: synthetic corpus must pass the live validator; mutants must fail.

A synthetic corpus the gate rejects measures nothing. Both-states: a well-formed
n=128/1024 chain catalog is silent; a dangling dependency and a two-cycle fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "tools" / "command-center"))

from generator import make_catalog  # noqa: E402
from measure import validate_catalog  # noqa: E402

RAW = HERE / "probe1-generator.raw.json"


def _fail(msg: str) -> int:
    print(f"FAILED:BLD-0055-probe1 {msg}")
    return 1


def main() -> int:
    results: dict = {"pass": False, "sizes": {}}
    for n in (128, 1024):
        catalog, text = make_catalog(n, shape="chain", plant_near_dup=True)
        gate = validate_catalog(catalog, text)
        results["sizes"][str(n)] = {
            "ok": gate["ok"],
            "n_violations": gate["n_violations"],
            "stats": gate["stats"],
        }
        if not gate["ok"]:
            RAW.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
            return _fail(f"n={n} rejected by live validator {gate['violations']}")

    catalog, text = make_catalog(32, shape="chain", plant_near_dup=False)
    catalog["items"][10]["dependencies"] = ["T-DOES-NOT-EXIST"]
    dang = validate_catalog(catalog, text)
    if dang["ok"]:
        RAW.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
        return _fail("dangling-dependency mutant was accepted")

    catalog, text = make_catalog(32, shape="chain", plant_near_dup=False)
    catalog["items"][4]["dependencies"] = ["T-6"]
    catalog["items"][5]["dependencies"] = ["T-5"]
    cyc = validate_catalog(catalog, text)
    if cyc["ok"]:
        RAW.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
        return _fail("cycle mutant was accepted")

    results.update(
        {
            "pass": True,
            "good_n128": True,
            "good_n1024": True,
            "dangling_rejected": True,
            "cycle_rejected": True,
            "dangling_violations": dang["violations"],
            "cycle_violations": cyc["violations"],
        }
    )
    RAW.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "n128_ok=True n1024_ok=True dangling_rejected=True cycle_rejected=True "
        f"items_128={results['sizes']['128']['stats'].get('items')} "
        f"items_1024={results['sizes']['1024']['stats'].get('items')}"
    )
    print("SUCCESS:BLD-0055-probe1 generator passes live validator; mutants fail")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
