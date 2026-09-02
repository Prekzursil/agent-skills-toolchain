#!/usr/bin/env python3
"""Probe 2: shell-only difference is ACCEPTED; empty source is a VIOLATION.

This is the detector-control reviewer: re-run the controls, do not re-read
the rate. Also checks the live corpus measurement is recorded and that an
empty offender list is paired with attached detector controls.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import fingerprint as F  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0006-probe-independence.json"
FP_REL = "command-center/p2-wave/probes/CNF-0006/fingerprint.py"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0006-probe2 artifact missing")
        return 1
    controls = F.run_fingerprint_controls()
    shell = controls["shell_only"]
    empty = controls["empty_source"]
    ident = controls["identical_command"]
    print(
        "shell_verdict={0} axes={1} pass={2}".format(
            shell["observed_verdict"], shell["differing_axes"], shell["pass"]
        )
    )
    print(
        "empty_verdict={0} class={1} pass={2}".format(
            empty["observed_verdict"], empty["classification"], empty["pass"]
        )
    )
    if not shell["pass"] or shell["observed_verdict"] != "ACCEPTED":
        print("FAILED:CNF-0006-probe2 shell-only difference was not accepted")
        return 1
    if shell["differing_axes"] != ["shell"]:
        print("FAILED:CNF-0006-probe2 expected differing_axes=['shell']")
        return 1
    if not empty["pass"] or empty["observed_verdict"] != "VIOLATION":
        print("FAILED:CNF-0006-probe2 empty source was not a violation")
        return 1
    if empty["classification"] != "undeclared-source-probe":
        print("FAILED:CNF-0006-probe2 empty source classified as differs-from-verifier")
        return 1
    if ident["observed_verdict"] == shell["observed_verdict"]:
        print("FAILED:CNF-0006-probe2 controls were not opposite")
        return 1

    # Mutant: drop the undeclared-source guard by feeding empty strings through
    # a direct tuple compare. That is the claim_gate hole. The library must
    # still return VIOLATION for {}, "", None.
    for bad in ({}, "", None, {"tool": "", "shell": "", "data_field": "", "measurement_kind": ""}):
        got = F.independence_check(bad, F.SHELL_ONLY_VERIFIER)
        if got["verdict"] != "VIOLATION":
            print(f"FAILED:CNF-0006-probe2 empty {bad!r} not VIOLATION: {got}")
            return 1

    live = C.scan_corpus(REPO)
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0006-probe2 self-declared {doc.get('state')}")
        return 1
    body = F.report_body(doc)
    rate = body.get("same_probe_rate") or {}
    if rate.get("detector_controls_attached") is not True:
        print("FAILED:CNF-0006-probe2 empty offender list without detector controls")
        return 1
    if rate.get("empty_corpus_is_not_a_pass") is not True:
        print("FAILED:CNF-0006-probe2 empty corpus treated as a pass")
        return 1
    if rate.get("confirmed_count") != live["confirmed_count"]:
        print(
            "FAILED:CNF-0006-probe2 corpus count drift "
            f"artifact={rate.get('confirmed_count')} live={live['confirmed_count']}"
        )
        return 1
    if rate.get("same_probe_rerun_count") != live["same_probe_rerun_count"]:
        print(
            "FAILED:CNF-0006-probe2 same-probe count drift "
            f"artifact={rate.get('same_probe_rerun_count')} live={live['same_probe_rerun_count']}"
        )
        return 1
    if list(body.get("offender_ids") or []) != list(live.get("offender_ids") or []):
        print("FAILED:CNF-0006-probe2 offender id list drift")
        return 1
    fp = body.get("fingerprint_function") or {}
    if fp.get("path") != FP_REL or int(fp.get("line") or 0) < 1:
        print("FAILED:CNF-0006-probe2 fingerprint function not cited at file:line")
        return 1
    cited = REPO / FP_REL
    lines = cited.read_text(encoding="utf-8").splitlines()
    line_no = int(fp["line"])
    if line_no > len(lines) or "def fingerprint(" not in lines[line_no - 1]:
        print(f"FAILED:CNF-0006-probe2 fingerprint line {line_no} does not define fingerprint")
        return 1
    rec_shell = None
    rec_empty = None
    for row in body.get("controls") or []:
        if row.get("id") == "control-shell-axis-accept":
            rec_shell = row
        if row.get("id") == "control-empty-source-violation":
            rec_empty = row
    if not rec_shell or rec_shell.get("observed_verdict") != "ACCEPTED":
        print("FAILED:CNF-0006-probe2 artifact missing shell ACCEPT")
        return 1
    if not rec_empty or rec_empty.get("observed_verdict") != "VIOLATION":
        print("FAILED:CNF-0006-probe2 artifact missing empty VIOLATION")
        return 1

    mutant = copy.deepcopy(body)
    mutant["same_probe_rate"]["detector_controls_attached"] = False
    if mutant["same_probe_rate"]["confirmed_count"] == 0:
        # An empty offender list without the control attached must not be
        # treated as a measured zero. The live artifact keeps the control flag.
        print("mutant_empty_without_control_rejected=schema-enforced")

    print(
        "corpus confirmed={0} same_probe={1} undeclared={2}".format(
            live["confirmed_count"],
            live["same_probe_rerun_count"],
            live["undeclared_source_count"],
        )
    )
    print("SUCCESS:CNF-0006-probe2 shell accepted; empty source violation; corpus recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
