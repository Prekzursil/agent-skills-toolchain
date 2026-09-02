#!/usr/bin/env python3
"""Probe 2: negative controls. Mutants must fail the same contract.

Mechanically different from probe 1: does not re-measure Tor binaries.
It plants broken copies of the live artifact and requires evaluate() to
return errors for each. A checker silent on mutants is inverted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
from policy import OUTPUT_REL, UNIT_ID  # noqa: E402

ART = REPO / OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0119-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact-absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    live_errors = C.evaluate(doc, REPO)
    if live_errors:
        return fail("live-artifact-fails-contract:" + ",".join(live_errors[:8]))

    planted = C.mutants(doc)
    if len(planted) < 6:
        return fail(f"too-few-mutants:{len(planted)}")

    rows = []
    silent = []
    for name, mutant in planted:
        errs = C.evaluate(mutant, REPO)
        rows.append({"name": name, "error_count": len(errs), "errors": errs[:6]})
        if not errs:
            silent.append(name)
    if silent:
        print(json.dumps(rows, indent=2))
        return fail("silent-on-mutants:" + ",".join(silent))

    empty_errors = C.evaluate({}, REPO)
    if not empty_errors:
        return fail("silent-on-empty-object")

    print(
        json.dumps(
            {
                "probe": "probe2-negative-control",
                "unit_id": UNIT_ID,
                "live_pass": True,
                "mutants": len(planted),
                "mutants_rejected": len(planted) - len(silent),
                "empty_object_errors": empty_errors[:8],
                "rows": rows,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:RES-0119-probe2 mutants rejected live-pass="
        f"True rejected={len(planted)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
