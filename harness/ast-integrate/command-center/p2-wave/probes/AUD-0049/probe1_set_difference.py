#!/usr/bin/env python3
"""Named probe 1: set difference between promised platforms and runs-on values.

Signal: OS classification of every measured runs-on label, then promised minus
exercised. The catalog control must flag Windows as promised-but-underexercised
on an Ubuntu-only fixture that carries the three recorded CRLF failures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from comparator import WINDOWS_CRLF_DEFECTS, measure, windows_crlf_control  # noqa: E402

ART = REPO / "command-center/audit/AUD-0049-runner-matrix-vs-support.json"
UNIT = "AUD-0049"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    ctl = windows_crlf_control()
    if not ctl["pass"]:
        return fail("windows-crlf control does not discriminate", ctl)
    if ctl["bad"]["full_coverage"]:
        return fail("ubuntu-only fixture reported full coverage; comparator is not reading the matrix")
    if not ctl["bad"]["windows_underexercised"]:
        return fail("ubuntu-only fixture did not flag Windows")
    if len(WINDOWS_CRLF_DEFECTS) != 3:
        return fail("expected three recorded Windows-only CRLF failures")

    live = measure()
    drift = live["drift"]
    if drift["full_coverage"]:
        return fail("live matrix reported full coverage", drift)
    if not drift["windows_underexercised"]:
        return fail("live matrix did not flag Windows as promised-but-underexercised", drift)
    if "windows" not in drift["promised_minus_exercised"]:
        return fail("windows missing from promised_minus_exercised", drift)
    if "linux" not in drift["exercised_os"]:
        return fail("linux not in exercised_os", drift)
    if "windows" in drift["exercised_os"] or "macos" in drift["exercised_os"]:
        return fail("windows/macos unexpectedly exercised", drift)
    labels = {str(x).lower() for x in live["raw_labels"]}
    if any("windows" in x or "macos" in x for x in labels):
        return fail("a runs-on label names windows/macos", sorted(labels))
    if not labels or labels == {"<missing>"}:
        return fail("no runs-on labels measured", live["raw_labels"])

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    art_drift = doc.get("drift") or {}
    if art_drift.get("promised_minus_exercised") != drift["promised_minus_exercised"]:
        return fail("artifact set difference != live re-run", {"live": drift, "art": art_drift})
    if art_drift.get("windows_underexercised") is not True:
        return fail("artifact did not flag Windows")
    if art_drift.get("full_coverage") is not False:
        return fail("artifact claimed full coverage")
    if sorted(art_drift.get("exercised_os") or []) != drift["exercised_os"]:
        return fail("artifact exercised_os != live")

    out = {
        "probe": "probe1-set-difference",
        "unit_id": UNIT,
        "pass": True,
        "promised_os": drift["promised_os"],
        "exercised_os": drift["exercised_os"],
        "promised_minus_exercised": drift["promised_minus_exercised"],
        "windows_underexercised": True,
        "full_coverage": False,
        "matrix_source": live["matrix_source"],
        "raw_labels": live["raw_labels"],
        "control": {
            "fired_on_ubuntu_only": True,
            "silent_when_windows_in_matrix": True,
            "full_coverage_rejected_on_bad_fixture": True,
        },
        "artifact_matches_live": True,
    }
    (HERE / "probe1-set-difference.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:AUD-0049-probe1 promised-minus-runs-on set difference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
