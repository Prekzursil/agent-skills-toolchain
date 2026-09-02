#!/usr/bin/env python3
"""Probe 2: vote-count, overclaim-with-fine-code, wording-retention controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from check import (  # noqa: E402
    check_artifact,
    majority_vote_fails,
    wording_deleted_fails,
)
from router import close  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0119-disagreement-adjudication.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0119-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = check_artifact(doc)
    print(f"artifact_ok={ok} {why}")
    if not ok:
        print("FAILED:CNF-0119-probe2 artifact check failed")
        return 1

    if not wording_deleted_fails(doc):
        print("FAILED:CNF-0119-probe2 deleting original_wording still passed")
        return 1
    print("wording_deleted_control=True")

    if not majority_vote_fails(doc):
        print("FAILED:CNF-0119-probe2 following majority vote still passed")
        return 1
    print("majority_vote_control=True")

    overclaims = [c for c in doc["cases"] if c["classification"] == "overclaim"]
    if not overclaims:
        print("FAILED:CNF-0119-probe2 no overclaim rows")
        return 1
    for row in overclaims:
        if row.get("code_was_fine") is not True:
            print(f"FAILED:CNF-0119-probe2 {row['id']} overclaim but code not fine")
            return 1
        if row.get("winning_side") != "confirmer":
            print(f"FAILED:CNF-0119-probe2 {row['id']} overclaim not REFUTED via confirmer win")
            return 1
        if row["correctly_scoped_statement"] == row["original_wording"]:
            print(f"FAILED:CNF-0119-probe2 {row['id']} scoped equals original")
            return 1
        if row["original_wording"] not in json.dumps(row):
            print(f"FAILED:CNF-0119-probe2 {row['id']} original wording dropped")
            return 1
    print(f"overclaim_rows={len(overclaims)} all code_was_fine with scoped rewrite")

    overridden = [c for c in doc["cases"] if c.get("majority_overridden")]
    if not overridden:
        print("FAILED:CNF-0119-probe2 no majority-overridden case")
        return 1
    d8 = overridden[0]
    print(
        f"majority_overridden={d8['id']} votes={d8['agent_votes']} "
        f"majority={d8['majority_would_have_picked']} "
        f"probe={d8['winning_side']}"
    )

    n_ok, n_why = close({"id": "x", "disposition": None})
    if n_ok:
        print("FAILED:CNF-0119-probe2 null disposition accepted")
        return 1
    f_ok, f_why = close({"id": "x", "disposition": "implementation-defect"})
    if not f_ok:
        print(f"FAILED:CNF-0119-probe2 dispositioned close refused {f_why}")
        return 1
    print(f"router null_refused={n_why} full_closed={f_why}")
    print("SUCCESS:CNF-0119-probe2 overclaim anchors reviewer-added-mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
