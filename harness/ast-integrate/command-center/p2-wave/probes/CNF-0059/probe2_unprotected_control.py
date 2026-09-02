#!/usr/bin/env python3
"""Probe 2: consumer with no smoke must be unprotected, never passing.

Both-states: honest classification is silent; mutating unprotected -> ok fires.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import downstream as D  # noqa: E402

REPO = D.REPO
ART = REPO / "command-center/confirmation/CNF-0059-downstream-consumers.json"


def main() -> int:
    live = D.measure()
    ctrl = live["control_unprotected"]
    fired = bool(ctrl.get("fired_on_bad_state"))
    silent = bool(ctrl.get("silent_on_good_state"))
    unprotected = live["unprotected_ids"]
    if "cnf0059-unprotected" not in unprotected:
        print("FAILED:CNF-0059-probe2 fixture unprotected missing", unprotected)
        return 1
    if "cnf0059-unprotected" in live["ok_ids"]:
        print("FAILED:CNF-0059-probe2 unprotected classified as passing")
        return 1
    if not fired or not silent:
        print(f"FAILED:CNF-0059-probe2 control did not discriminate fired={fired} silent={silent}")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        answer, art_consumers = D.artifact_payload(doc)
        art_unprot = set(answer.get("unprotected_consumers") or [])
        if "cnf0059-unprotected" not in art_unprot:
            print("FAILED:CNF-0059-probe2 artifact omitted unprotected fixture")
            return 1
        for c in art_consumers:
            if c.get("id") == "cnf0059-unprotected" and c.get("finding") != "unprotected":
                print("FAILED:CNF-0059-probe2 artifact finding", c.get("finding"))
                return 1

    print(
        f"unprotected={unprotected} fired_on_bad={fired} silent_on_good={silent} "
        f"misclassified_on_good={ctrl.get('misclassified_on_good')}"
    )
    print("SUCCESS:CNF-0059-probe2 unprotected consumers are not reported as passing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
