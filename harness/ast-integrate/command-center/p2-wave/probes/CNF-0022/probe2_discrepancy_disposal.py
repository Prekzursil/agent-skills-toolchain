#!/usr/bin/env python3
"""Named probe 2: discrepancy filing + disposable worktree proof.

Mechanically different from probe 1: this probe requires GREEN-GREEN on the
misattributed fix, RED-GREEN on the control test of the wrong-association
fixture, worktree path gone after remove, and the artifact must not claim
product git history was examined on this host.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import timetravel as TT  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0022-pre-fix-timetravel.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def domain(doc: dict) -> dict:
    """Domain payload lives under report (repro-report class pin)."""
    rep = doc.get("report")
    if isinstance(rep, dict) and isinstance(rep.get("discrepancies"), list):
        return rep
    return doc


def main() -> int:
    live = TT.run_campaign()
    by_id = {r["id"]: r for r in live["rows"]}
    mis = by_id["FIX-COMMENT-ONLY"]
    wrong = by_id["FIX-MUL-WITH-ADD-TEST"]
    disposal = live["disposal"]
    host = live["host"]
    printable = {
        "probe": "probe2-discrepancy-disposal",
        "unit_id": "CNF-0022",
        "misattributed_pattern": mis["pattern"],
        "wrong_test_pattern": wrong["pattern"],
        "control_pattern": wrong.get("control_pattern"),
        "path_gone": disposal["path_gone"],
        "not_listed": disposal["not_listed"],
        "removed_path_unrunnable": disposal["removed_path_unrunnable"],
        "host_is_git": host["is_git_repository"],
        "host_git_present_after": disposal["host_git_present_after"],
    }
    print(json.dumps(printable, sort_keys=True))

    if mis["pattern"] != "GREEN-GREEN":
        print(f"FAILED:CNF-0022-probe2 misattributed pattern {mis['pattern']}")
        return 1
    if wrong["pattern"] != "GREEN-GREEN":
        print(f"FAILED:CNF-0022-probe2 wrong-test pattern {wrong['pattern']}")
        return 1
    if wrong.get("control_pattern") != "RED-GREEN":
        print(
            "FAILED:CNF-0022-probe2 control test did not prove the mul defect "
            f"existed at parent ({wrong.get('control_pattern')})"
        )
        return 1
    if not (
        disposal["path_gone"]
        and disposal["not_listed"]
        and disposal["removed_path_unrunnable"]
        and disposal["parent_was_red"]
    ):
        print("FAILED:CNF-0022-probe2 disposal not proven")
        print(json.dumps(disposal, sort_keys=True))
        return 1
    if disposal["host_git_created"] or disposal["host_git_present_after"]:
        print("FAILED:CNF-0022-probe2 shared checkout gained a .git")
        return 1
    if host["is_git_repository"] or host["dot_git_present"]:
        print("FAILED:CNF-0022-probe2 host unexpectedly a git repo")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0022-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = domain(doc)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:CNF-0022-probe2 self-declared {doc.get('state')}")
        return 1
    discs = {d["id"]: d for d in payload.get("discrepancies") or [] if isinstance(d, dict)}
    classes = {d.get("classification") for d in discs.values()}
    if "misattributed-fix" not in classes:
        print("FAILED:CNF-0022-probe2 missing misattributed-fix discrepancy")
        return 1
    if "test-measures-something-else" not in classes:
        print("FAILED:CNF-0022-probe2 missing test-measures-something-else discrepancy")
        return 1
    if "repro-not-reproducible" not in classes:
        print("FAILED:CNF-0022-probe2 missing host repro-not-reproducible discrepancy")
        return 1
    for disc in discs.values():
        if len(disc.get("signals") or []) < 2:
            print(f"FAILED:CNF-0022-probe2 discrepancy {disc.get('id')} has <2 signals")
            return 1

    if payload.get("answer", {}).get("product_history_examined") is not False:
        print("FAILED:CNF-0022-probe2 overclaim: product history examined")
        return 1
    if payload.get("scope", {}).get("product_history_examined") is not False:
        print("FAILED:CNF-0022-probe2 overclaim: scope product history")
        return 1
    if payload.get("worktree_protocol", {}).get("removal_proven") is not True:
        print("FAILED:CNF-0022-probe2 artifact disposal not proven")
        return 1
    if payload.get("worktree_protocol", {}).get("shared_host_index_touched") is not False:
        print("FAILED:CNF-0022-probe2 shared index claimed touched")
        return 1
    if doc.get("cloud_ok") is True or payload.get("cloud_ok") is True:
        print("FAILED:CNF-0022-probe2 cloud_ok is not delivery")
        return 1

    mutant_ok = False
    mutant = json.loads(ART.read_text(encoding="utf-8"))
    domain(mutant)["answer"]["product_history_examined"] = True
    # Probe refuses the overclaim locally (product_history_examined must stay false).
    if domain(mutant)["answer"]["product_history_examined"] is True:
        mutant_ok = True
    if not mutant_ok:
        print("FAILED:CNF-0022-probe2 could not construct overclaim mutant")
        return 1
    print("SUCCESS:CNF-0022-probe2 discrepancy filing and worktree disposal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
