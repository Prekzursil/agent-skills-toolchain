#!/usr/bin/env python3
"""Probe 1: extract each crafted archive through the program's own import path.

Enumerates every file created, including outside the intended root. A benign
archive must extract completely. stdlib tarfile.extractall is the red control.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.tests.test_archive_extract import (  # noqa: E402
    ExtractMatrixTests,
    NormalizeTests,
)

from matrix import run_matrix  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0027-archive-extraction-traversal-attacks.json"
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0027 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0027 <reason>."
)


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0027-probe1 {msg}")
    return 1


def main() -> int:
    live = run_matrix()
    printable = {
        "probe": "probe1-extract-matrix",
        "unit_id": "ADV-0027",
        "pass": live["pass"],
        "platform": live["platform"],
        "targets": live["targets"],
        "tests": live["tests"],
        "negative_controls": live["negative_controls"],
        "ratio_observed": live["ratio_observed"],
        "naive_tar_extractall_landed_outside": live["naive_tar_extractall_landed_outside"],
        "computed_not_asserted": True,
    }
    print(json.dumps(printable, sort_keys=True, default=str))
    if not live["pass"]:
        return fail("live matrix did not pass")
    if live["ratio_observed"] <= 10000.0:
        return fail(f"ratio fixture {live['ratio_observed']} not 10000:1")
    if not live["naive_tar_extractall_landed_outside"]:
        return fail("naive extractall did not land outside (detector inert)")
    for row in live["targets"]:
        if row["verdict"] != "REFUTED":
            return fail(f"{row['id']} verdict {row['verdict']}")
        if row.get("escaped"):
            return fail(f"{row['id']} escaped {row.get('outside_new')}")
    benign = live["benign"]
    if not benign["ok"] or benign["inside"] != ["pkg/manifest.json", "pkg/payload.txt"]:
        return fail(f"benign control {benign}")

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(NormalizeTests))
    suite.addTests(loader.loadTestsFromTestCase(ExtractMatrixTests))
    result = unittest.TextTestRunner(verbosity=1, stream=sys.stderr).run(suite)
    if not result.wasSuccessful():
        return fail(f"unittest failures={len(result.failures)} errors={len(result.errors)}")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            return fail(f"artifact unparseable {exc}")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        if CATALOG_SENTINEL not in text:
            return fail("catalog sentinel-absent")
        if doc.get("unit_id") != "ADV-0027":
            return fail(f"unit_id {doc.get('unit_id')}")
        live_ids = {t["id"]: t["verdict"] for t in live["targets"]}
        art_ids = {
            t["id"]: t["verdict"]
            for t in (doc.get("targets") or [])
            if isinstance(t, dict)
        }
        for tid, verdict in live_ids.items():
            if art_ids.get(tid) != verdict:
                return fail(f"artifact target {tid} {art_ids.get(tid)} != live {verdict}")

    print(
        f"benign_ok=True naive_red=True ratio={live['ratio_observed']:.1f}:1 "
        f"targets_refuted={len(live['targets'])} platform={live['platform']['system']}"
    )
    print("SUCCESS:ADV-0027-probe1 import-path matrix: hostile members rejected, benign extracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
