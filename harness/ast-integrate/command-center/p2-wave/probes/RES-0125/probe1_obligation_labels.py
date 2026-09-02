#!/usr/bin/env python3
"""Probe 1: obligation labels and the proposed-norm control.

Re-checks the live artifact, then runs two mutants that must go red:
unlabelled rows, and an all-required-by-terms table (the catalog control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from check import (  # noqa: E402
    ART,
    check_artifact,
    load_indexes,
    mutant_all_required,
    mutant_drop_labels,
)
from labels import ALLOWED_LABELS, SENTINEL, UNIT  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail(f"artifact absent {ART}")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    indexes = load_indexes()
    live = check_artifact(doc, indexes)
    print(json.dumps({"live": live, "allowed_labels": list(ALLOWED_LABELS)}, sort_keys=True))
    if not live["pass"]:
        return fail(f"live {live['errors']}")

    dropped = check_artifact(mutant_drop_labels(doc), indexes)
    if dropped["pass"]:
        return fail("unlabelled mutant stayed green")
    if "bad-label" not in " ".join(dropped["errors"]):
        return fail(f"unlabelled mutant errors={dropped['errors']}")

    all_req = check_artifact(mutant_all_required(doc), indexes)
    if all_req["pass"]:
        return fail("all-required-by-terms mutant stayed green (proposed-norm control inert)")
    if "proposed-norm-control-failed" not in all_req["errors"]:
        return fail(f"all-required mutant errors={all_req['errors']}")

    rows = doc.get("obligation_table") or []
    labels = sorted({r.get("required_versus_proposed") for r in rows})
    proposed = [r["id"] for r in rows if r.get("required_versus_proposed") == "proposed-norm"]
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-obligation-labels",
                "unit_id": UNIT,
                "rows": len(rows),
                "labels_present": labels,
                "proposed_norm_ids": proposed,
                "unlabelled_mutant_red": True,
                "all_required_mutant_red": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:RES-0125-probe1 labels valid, proposed-norm present, "
        "both mutants red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
