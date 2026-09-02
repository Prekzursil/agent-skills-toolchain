#!/usr/bin/env python3
"""Named probe 2: mutation controls that must turn the gate red.

Reviewer job: re-run the mutations; do not merely re-read the stored verdict.

1. Detector: pin lodash@4.17.20 -> CVE-2021-23337 must appear; qs CVE must not.
2. Tooling: scanner exit 127 classifies NOT-CHECKED, never PASS (measured defect).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import controls  # noqa: E402
import scanner  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/REL-0014.json"


def fail(msg: str) -> int:
    print(f"FAILED:REL-0014-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:REL-0014" not in json.dumps(doc):
        return fail("sentinel-absent")

    det = controls.detector_known_advisory()
    tool = controls.tooling_exit_not_checked()
    print(json.dumps({"detector": det, "tooling": tool}, sort_keys=True, default=str))

    if not det["pass"]:
        return fail("known-advisory detector did not fire")
    ids = [f["id"] for f in det["vulnerable_findings"]]
    if S.KNOWN_ADVISORY not in ids:
        return fail(f"CVE-2021-23337 absent from findings {ids}")
    if S.UNRELATED_ADVISORY in ids:
        return fail("unrelated qs advisory fired on a lodash pin")
    if det["clean_verdict"] != "PASS":
        return fail("patched lodash@4.17.21 was not clean")

    if not tool["pass"]:
        return fail("exit 127 was not classified NOT-CHECKED")
    if scanner.classify_exit(127) != "NOT-CHECKED":
        return fail("honest classifier drifted")
    if scanner.classify_exit_buggy_127_as_clean(127) != "PASS":
        return fail("negative control (buggy 127-as-clean) no longer reproduces")
    if tool["verdict"] != "NOT-CHECKED" or tool["exit_code"] != 127:
        return fail("missing-tool promotion was not NOT-CHECKED")

    rec_det = (doc.get("tests") or {}).get("detector_known_advisory") or {}
    rec_tool = (doc.get("tests") or {}).get("tooling_exit_not_checked") or {}
    if rec_det.get("pass") is not True:
        return fail("receipt detector control not pass")
    if rec_tool.get("pass") is not True:
        return fail("receipt tooling control not pass")
    rec_ids = [f.get("id") for f in (rec_det.get("vulnerable_findings") or [])]
    if S.KNOWN_ADVISORY not in rec_ids:
        return fail("receipt omitted CVE-2021-23337")
    if rec_tool.get("honest_classification") != "NOT-CHECKED":
        return fail("receipt omitted honest 127 classification")
    if rec_tool.get("buggy_classification") != "PASS":
        return fail("receipt omitted buggy 127-as-clean contrast")

    exercised = set(doc.get("failure_classes_exercised") or [])
    need = {"stale-green", "tool-error-as-pass", "detector-failure"}
    if not need <= exercised:
        return fail(f"failure classes {exercised}")

    print(
        f"detector={S.KNOWN_ADVISORY} findings={ids} "
        f"exit127={tool['honest_classification']} buggy={tool['buggy_classification']}"
    )
    print("SUCCESS:REL-0014-probe2 detector control and exit-127 NOT-CHECKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
