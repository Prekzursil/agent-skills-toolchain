#!/usr/bin/env python3
"""Probe 2: reclassify failures that vanish on a fresh profile; survivors stay."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import reviewer as R  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0017-fresh-profile-repro.json"

MUST_LOCAL = {
    "BL-PLUGIN-ACCUM",
    "BL-SKILL-ACCUM",
    "BL-MCP-ACCUM",
    "BL-PATH-SHIM",
    "BL-CRLF-02-git-autocrlf",
}
MUST_SURVIVE = {
    "BL-CRLF-01-worktree-fixture",
    "BL-TDD-01",
    "BL-TDD-02",
    "BL-TDD-03",
    "BL-TDD-04",
    "BL-POSIX-01",
}


def main() -> int:
    run = S.run_scenario()
    live_pairs = [
        {
            "id": r["id"],
            "loaded_outcome": r["loaded_outcome"],
            "fresh_outcome": r["fresh_outcome"],
        }
        for r in run["failures"]
    ]
    rev = R.review(live_pairs)
    print(f"reviewer_verdict={rev['verdict']} independent={rev['independent']}")
    print(f"derived_local={rev['local_state_dependent']}")
    print(f"derived_survived={rev['survived_fresh_profile']}")

    missing_local = MUST_LOCAL - set(rev["local_state_dependent"])
    missing_surv = MUST_SURVIVE - set(rev["survived_fresh_profile"])
    if missing_local:
        print(f"FAILED:CNF-0017-probe2 planted local-state checks not reclassified: {sorted(missing_local)}")
        return 1
    if missing_surv:
        print(f"FAILED:CNF-0017-probe2 code/platform checks did not survive fresh: {sorted(missing_surv)}")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0017-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    view = S.artifact_view(doc)
    if view.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0017-probe2 self-declared {view.get('state')}")
        return 1
    # Independent path: compare artifact classifications to reviewer derived
    # from live outcomes, without using doc['conclusion'].
    art_rows = {
        str(r["id"]): str(r["classification"])
        for r in (view.get("failures") or [])
        if isinstance(r, dict)
    }
    der_rows = {r["id"]: r["classification"] for r in rev["derived_rows"]}
    if art_rows != der_rows:
        print("FAILED:CNF-0017-probe2 artifact classification != independent derivation")
        print(f" artifact={art_rows}")
        print(f" derived={der_rows}")
        return 1
    saw = view.get("saw_conclusion_first")
    if saw is None:
        saw = (doc.get("reviewer") or {}).get("saw_conclusion_first")
    if saw is not False:
        print("FAILED:CNF-0017-probe2 reviewer was anchored")
        return 1
    print("SUCCESS:CNF-0017-probe2 reclassify local-state; survivors stay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
