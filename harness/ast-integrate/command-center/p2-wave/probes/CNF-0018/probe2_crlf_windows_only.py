#!/usr/bin/env python3
"""Probe 2: CRLF hypothesis + schema + sentinel + overclaim control.

Independent of emit.py's prose: re-read the artifact, validate the schema,
require the catalog sentinel, require three Windows-only CRLF PASSes in the
container, and reject a mutant that drops known_failure_reproduced.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import container as C  # noqa: E402
import fields as F  # noqa: E402
import schema_check as SC  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0018-linux-container-repro.json"
SENTINEL = (
    "SUCCESS:CNF-0018 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the container reproduced "
    "at least one known failure, establishing it is not silently green for "
    "setup reasons. Any other terminal state is FAILED:CNF-0018 "
    "<classification> with the diagnostic tail attached."
)


def test_passed(row: dict) -> bool:
    if row.get("passed") is True:
        return True
    return row.get("result") == "PASS"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0018-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    errs = SC.errors_for(doc)
    if errs:
        print("FAILED:CNF-0018-probe2 schema")
        for e in errs[:20]:
            print(" ", e)
        return 1

    if SENTINEL not in text:
        print("FAILED:CNF-0018-probe2 catalog sentinel absent")
        return 1
    if doc.get("state") != "SUCCESS":
        print("FAILED:CNF-0018-probe2 state", doc.get("state"))
        return 1
    if F.known_failure_of(doc) is not True:
        print("FAILED:CNF-0018-probe2 known_failure_reproduced is not true")
        return 1

    failures = F.failures_of(doc)
    crlf = [f for f in failures if str(f.get("id") or "").startswith("F-CRLF-")]
    xp = [f for f in failures if str(f.get("id") or "").startswith("F-XP-")]
    if len(crlf) != 3:
        print(f"FAILED:CNF-0018-probe2 crlf_rows={len(crlf)} want=3")
        return 1
    if len(xp) != 1:
        print(f"FAILED:CNF-0018-probe2 xp_rows={len(xp)} want=1")
        return 1
    for f in crlf:
        if f.get("classification") != "Windows-only":
            print("FAILED:CNF-0018-probe2 CRLF classification", f.get("id"), f.get("classification"))
            return 1
        if (f.get("linux_container") or {}).get("outcome") != "PASS":
            print("FAILED:CNF-0018-probe2 CRLF did not PASS in container", f.get("id"))
            return 1
        if (f.get("windows_simulated") or {}).get("outcome") != "FAIL":
            print("FAILED:CNF-0018-probe2 CRLF Windows sim did not FAIL", f.get("id"))
            return 1
    if (xp[0].get("linux_container") or {}).get("outcome") != "FAIL":
        print("FAILED:CNF-0018-probe2 XP did not FAIL in container")
        return 1
    if xp[0].get("classification") != "cross-platform":
        print("FAILED:CNF-0018-probe2 XP classification", xp[0].get("classification"))
        return 1

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in ("T-CRLF-PASS-IN-CONTAINER", "T-KNOWN-FAILURE-NOT-SILENT-GREEN"):
        row = tests.get(tid)
        if not row or not test_passed(row):
            print("FAILED:CNF-0018-probe2 test missing or not passed", tid)
            return 1

    mutant = copy.deepcopy(doc)
    report = mutant.get("report") if isinstance(mutant.get("report"), dict) else {}
    mutant["report"] = report
    report["known_failure_reproduced"] = False
    mutant["known_failure_reproduced"] = False
    if F.known_failure_of(mutant) is True:
        print("FAILED:CNF-0018-probe2 mutant did not flip")
        return 1
    if F.known_failure_of(doc) is not True:
        print("FAILED:CNF-0018-probe2 original control lost")
        return 1

    packed = C.run_container()
    live_crlf = [
        f
        for f in packed["measure"]["failures"]
        if f["id"].startswith("F-CRLF-")
    ]
    live_pass = all(f["linux_container"]["outcome"] == "PASS" for f in live_crlf)
    print(
        json.dumps(
            {
                "probe": "probe2-crlf-windows-only",
                "schema_ok": True,
                "sentinel_ok": True,
                "crlf_windows_only": True,
                "live_crlf_pass": live_pass,
                "image_digest": packed["container"]["image_digest"],
                "mutant_control_flipped": F.known_failure_of(mutant) is False,
            },
            sort_keys=True,
        )
    )
    if not live_pass:
        print("FAILED:CNF-0018-probe2 live re-run CRLF did not PASS")
        return 1
    print("SUCCESS:CNF-0018-probe2 CRLF Windows-only and schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
