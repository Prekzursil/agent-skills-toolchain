#!/usr/bin/env python3
"""Probe 1 / Signal A: per-candidate existence + rationale re-read.

Also the no-delete canary. Does not treat a preservation claim as a receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import engine as E  # noqa: E402
import locate as L  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0071-retire-readjudication.json"


def main() -> int:
    located = L.locate_registry()
    live = C.live_cohort(located)
    controls = C.control_corpus()
    canary = C.canary_ok()

    live_rows = [E.adjudicate(c) for c in live]
    ctrl_rows = [E.adjudicate(c) for c in controls]
    live_completed = [r for r in live_rows if r["completed_retirement"]]
    live_p1 = [r for r in live_rows if r["p1"]]
    identity_p1 = [
        r for r in live_rows if r["verdict"] == "P1-IDENTITY-UNRECOVERABLE"
    ]

    exist_present = sum(1 for r in live_rows if r["existence"]["present"])
    exist_absent = len(live_rows) - exist_present

    print(
        json.dumps(
            {
                "probe": "probe1-existence-and-rationale",
                "registry_hits": len(located["hits"]),
                "registry_rejected": len(located.get("rejected") or []),
                "registry_chosen": (located.get("chosen") or {}).get("path"),
                "live_n": len(live_rows),
                "live_existence_present": exist_present,
                "live_existence_absent": exist_absent,
                "live_completed_retirement": len(live_completed),
                "live_p1": len(live_p1),
                "live_identity_unrecoverable": len(identity_p1),
                "control_n": len(ctrl_rows),
                "control_verdicts": {r["id"]: r["verdict"] for r in ctrl_rows},
                "canary_unchanged": canary["unchanged"],
                "files_deleted_by_this_unit": canary["files_deleted_by_this_unit"],
                "git": located["git"],
            },
            sort_keys=True,
        )
    )

    if len(live_rows) != 24:
        print(f"FAILED:WFA-0071-probe1 live cohort n={len(live_rows)} want 24")
        return 1
    if located["hits"] and located["retire_n"] != 24:
        print(
            f"FAILED:WFA-0071-probe1 registry retire_n={located['retire_n']} "
            "disagrees with catalog n=24"
        )
        return 1
    for hit in located["hits"]:
        name = str(hit.get("path") or "").replace("\\", "/").rsplit("/", 1)[-1]
        if name == "_wfa2_entries.json":
            print(
                "FAILED:WFA-0071-probe1 markdown inventory treated as "
                "classified 284-row registry"
            )
            return 1
    if not located["hits"] and len(identity_p1) != 24:
        print(
            "FAILED:WFA-0071-probe1 registry absent but identity-unrecoverable "
            f"n={len(identity_p1)} want 24"
        )
        return 1
    if live_completed:
        print(
            "FAILED:WFA-0071-probe1 live completed_retirement "
            f"{[r['id'] for r in live_completed]} — terminal RETIRE without "
            "named identity+preservation is forbidden"
        )
        return 1
    if not canary["unchanged"]:
        print("FAILED:WFA-0071-probe1 no-delete canary mutated or missing")
        return 1
    if canary["files_deleted_by_this_unit"]:
        print("FAILED:WFA-0071-probe1 unit deleted files")
        return 1

    still = next(r for r in ctrl_rows if r["id"] == "ctrl-still-live")
    unpres = next(r for r in ctrl_rows if r["id"] == "ctrl-unpreserved")
    if still["existence"]["present"] is not True:
        print("FAILED:WFA-0071-probe1 still-live control not present")
        return 1
    if still["verdict"] != "REOPEN":
        print(f"FAILED:WFA-0071-probe1 still-live verdict={still['verdict']}")
        return 1
    if unpres["existence"]["present"] is not False:
        print("FAILED:WFA-0071-probe1 unpreserved control is present")
        return 1
    if unpres["completed_retirement"] or unpres["verdict"] != "P1-UNPRESERVED":
        print(
            "FAILED:WFA-0071-probe1 unpreserved was treated as completed "
            f"retirement verdict={unpres['verdict']}"
        )
        return 1

    if not ART.is_file():
        print("FAILED:WFA-0071-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0071" not in ART.read_text(encoding="utf-8"):
        print("FAILED:WFA-0071-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:WFA-0071-probe1 self-declared {doc.get('state')}")
        return 1
    if doc.get("files_deleted_by_this_unit") != []:
        print("FAILED:WFA-0071-probe1 artifact claims deletions")
        return 1
    if len(doc.get("candidates") or []) != 24:
        print("FAILED:WFA-0071-probe1 artifact candidates != 24")
        return 1
    art_completed = [
        c
        for c in doc["candidates"]
        if isinstance(c, dict) and c.get("completed_retirement") is True
    ]
    if art_completed and not located["hits"]:
        print("FAILED:WFA-0071-probe1 artifact terminal RETIRE with unnamed registry")
        return 1

    print(
        "NEGATIVE CONTROL verbatim: on ctrl-unpreserved (deleted, no copy) "
        "existence=absent and verdict=P1-UNPRESERVED with "
        "completed_retirement=false; it is not a completed retirement. "
        "On ctrl-still-live, DELETE-ALL rationale is re-read against a live "
        "file and verdict=REOPEN."
    )
    print(
        "BOTH-STATES: FIRED P1 on unpreserved; SILENT-on-delete "
        f"(canary_unchanged={canary['unchanged']}); still-live REOPEN; "
        f"live identity-unrecoverable={len(identity_p1)} completed=0"
    )
    print("SUCCESS:WFA-0071-probe1 existence rationale no-delete both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
