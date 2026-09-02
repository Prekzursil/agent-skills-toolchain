#!/usr/bin/env python3
"""Probe 1: catalog validator controls (both states).

A finding with no disposition, a residual risk with no settling experiment,
and an acceptance with no owner attribution (including agent-signed) must
make the validator exit non-zero. A well-formed fixture ledger must pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate as V  # noqa: E402

SCRATCH = HERE / "fixtures" / "_probe1-scratch"


def main() -> int:
    if SCRATCH.exists():
        import shutil

        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    results = V.run_catalog_controls(SCRATCH)
    required = (
        "good-fixture-accepted",
        "no-disposition",
        "no-settling-experiment",
        "no-owner-attribution",
        "agent-signed-acceptance",
        "recount-drop-one",
    )
    print(json.dumps({k: results.get(k) for k in required}, default=str))
    missing = [k for k in required if k not in results]
    if missing:
        print("FAILED:BLD-0064-probe1 missing controls", missing)
        return 1
    bad = [k for k in required if not results[k].get("ok")]
    if bad:
        print("FAILED:BLD-0064-probe1 controls not both-states", bad)
        for k in bad:
            print(" ", k, results[k].get("errors"))
        return 1
    if results["good-fixture-accepted"].get("rejected"):
        print("FAILED:BLD-0064-probe1 known-good fixture was rejected")
        return 1
    if not results["no-disposition"].get("rejected"):
        print("FAILED:BLD-0064-probe1 no-disposition mutant was accepted")
        return 1
    print("good_accepted=True")
    print("no_disposition_rejected=True")
    print("no_settling_experiment_rejected=True")
    print("no_owner_attribution_rejected=True")
    print("agent_signed_rejected=True")
    print("recount_drop_one_rejected=True")
    print("SUCCESS:BLD-0064-probe1 validator controls both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
