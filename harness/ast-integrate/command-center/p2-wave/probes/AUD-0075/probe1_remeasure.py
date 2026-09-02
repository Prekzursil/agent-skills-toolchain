#!/usr/bin/env python3
"""Probe 1: re-measure each pinned fact with a mechanically different verifier.

Also runs the required same-fingerprint rejection control, the distinct-
fingerprint acceptance control, the undeclared-source zero-signal control,
and the ready-count mutation control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

SIDECAR = HERE / "probe1-remeasurements.json"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0075-probe1 {msg}")
    return 1


def main() -> int:
    report = E.sweep()
    headline = report["headline"]
    controls = report["controls"]
    SIDECAR.write_text(E.dump({"probe": "probe1-remeasure", "report": report}), encoding="utf-8")
    print(f"facts={headline['facts']}")
    print(f"SUPPORTED={headline['SUPPORTED']}")
    print(f"CONTRADICTED={headline['CONTRADICTED']}")
    print(
        "CONTRADICTED-CURRENT-ENVIRONMENT="
        f"{headline['CONTRADICTED-CURRENT-ENVIRONMENT']}"
    )
    print(f"NOT-CHECKED={headline['NOT-CHECKED']}")
    print(f"undeclared_source_probes={headline['undeclared_source_probes']}")
    print(
        "independently_certified="
        f"{headline['independently_certified_confirmed_or_refuted']}"
    )
    print(f"same_fingerprint_rejected={controls['same_fingerprint_rejected']}")
    print(f"distinct_fingerprint_accepted={controls['distinct_fingerprint_accepted']}")
    print(f"missing_source_zero_signals={controls['missing_source_is_rejected']}")
    print(f"ready_mutation_fires={controls['ready_comparator_fires_on_bad']}")
    print(f"controls_pass={report['controls_pass']}")
    print(f"wrote={SIDECAR.relative_to(E.REPO).as_posix()}")

    if headline["facts"] != 12:
        return fail(f"expected 12 facts, got {headline['facts']}")
    if not report["controls_pass"]:
        return fail("fingerprint/ready controls did not all pass")
    if headline["undeclared_source_probes"] != 12:
        return fail(
            "pinned block must report 12 undeclared sources as zero signals, "
            f"got {headline['undeclared_source_probes']}"
        )
    if headline["independently_certified_confirmed_or_refuted"] != 0:
        return fail("undeclared sources must not mint independent pairs")
    if headline["source_signals"] != 0:
        return fail(f"source_signals={headline['source_signals']} want 0")

    art = E.REPO / E.OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text, doc = E.load_artifact()
    bad = E.artifact_ok(text, doc)
    if bad:
        return fail(bad)
    live = (doc.get("headline") or {})
    for key in (
        "facts",
        "SUPPORTED",
        "CONTRADICTED",
        "CONTRADICTED-CURRENT-ENVIRONMENT",
        "NOT-CHECKED",
        "undeclared_source_probes",
        "independently_certified_confirmed_or_refuted",
        "source_signals",
    ):
        if live.get(key) != headline.get(key):
            return fail(f"headline drift {key} artifact={live.get(key)} live={headline.get(key)}")
    if not (doc.get("controls") or {}).get("same_fingerprint_rejected"):
        return fail("artifact missing same-fingerprint rejection")
    print("SUCCESS:AUD-0075-probe1 remeasure + fingerprint controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
