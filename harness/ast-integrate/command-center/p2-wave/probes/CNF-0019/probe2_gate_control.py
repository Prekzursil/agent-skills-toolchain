#!/usr/bin/env python3
"""Probe 2: DETECTOR CONTROL — gates go RED on the known-broken fixture."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402

ART = M.REPO / "command-center/confirmation/CNF-0019-byte-route-audit.json"
CHECKLIST = M.REPO / "command-center/RELEASE-CHECKLIST.md"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0019-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errs = M.validate_report(doc)
    if errs:
        print("FAILED:CNF-0019-probe2 schema", errs[:5])
        return 1
    if not M.schema_rejects_garbage():
        print("FAILED:CNF-0019-probe2 schema accepted garbage")
        return 1
    mutant = copy.deepcopy(doc)
    mutant.pop("byte_table", None)
    mutant.pop("answers", None)
    rpt = mutant.get("report")
    if isinstance(rpt, dict):
        rpt.pop("byte_table", None)
        rpt.pop("answers", None)
    if not M.validate_report(mutant):
        print("FAILED:CNF-0019-probe2 schema accepted byte_table-stripped mutant")
        return 1

    live = M.measure_once()
    broken = live["misformatted"]
    print(
        "misformatted all_red",
        broken["all_red"],
        "gates",
        {g: broken["gates"][g]["verdict"] for g in M.GATES},
    )
    if not broken["all_red"]:
        print("FAILED:CNF-0019-probe2 misformatted control was not all RED")
        return 1
    body = M.payload(doc)
    art_broken = body.get("misformatted_control") or {}
    if not art_broken.get("all_red"):
        print("FAILED:CNF-0019-probe2 artifact misformatted_control.all_red false")
        return 1

    per = live["gate_verdicts_by_route"]
    blob_gates = per["git cat-file"]
    if (
        blob_gates["format"]["verdict"] != "GREEN"
        or blob_gates["lint"]["verdict"] != "GREEN"
    ):
        print("FAILED:CNF-0019-probe2 well-formed blob was not GREEN on format/lint")
        return 1
    if blob_gates["hash"]["verdict"] != "GREEN":
        print("FAILED:CNF-0019-probe2 hash gate missed the blob")
        return 1
    arch_gates = per["git archive"]
    if (
        arch_gates["format"]["verdict"] != "RED"
        or arch_gates["hash"]["verdict"] != "RED"
    ):
        print("FAILED:CNF-0019-probe2 archive CRLF did not trip format/hash")
        return 1
    if arch_gates["lint"]["verdict"] != "GREEN":
        print("FAILED:CNF-0019-probe2 lint was not EOL-insensitive on archive")
        return 1

    if live["route_dependent_gates"] != ["format", "hash"]:
        print(
            "FAILED:CNF-0019-probe2 route-dependent gates",
            live["route_dependent_gates"],
        )
        return 1

    chk = live["checklist"]
    if not chk["pre_fix_hits"]:
        print("FAILED:CNF-0019-probe2 pre-fix detector silent")
        return 1
    if chk["mention_hits"]:
        print("FAILED:CNF-0019-probe2 documentary mention fired")
        return 1
    if not CHECKLIST.is_file():
        print("FAILED:CNF-0019-probe2 corrected checklist missing")
        return 1
    if chk["live_hits"]:
        print("FAILED:CNF-0019-probe2 live checklist still prescribes archive")
        return 1
    if "git cat-file -p" not in CHECKLIST.read_text(encoding="utf-8"):
        print("FAILED:CNF-0019-probe2 live checklist lacks cat-file recipe")
        return 1
    answers = body.get("answers") or {}
    if answers.get("live_checklist_prescribes_crlf_route") is not False:
        print("FAILED:CNF-0019-probe2 answers.live_checklist_prescribes_crlf_route")
        return 1
    if answers.get("pre_fix_checklist_prescribed_crlf_route") is not True:
        print("FAILED:CNF-0019-probe2 answers.pre_fix flag")
        return 1
    if int(answers.get("route_dependent_gate_count") or -1) != 2:
        print("FAILED:CNF-0019-probe2 route_dependent_gate_count")
        return 1

    print("detector pre-fix FIRED mention SILENT live SILENT")
    print("SUCCESS:CNF-0019-probe2 gate+checklist detector control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
