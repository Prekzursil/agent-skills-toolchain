#!/usr/bin/env python3
"""Named probe 2: NOT-CHECKED guard, pre-registration, two-stratum re-derive.

Guard: the tool must refuse to emit an n when false-pass is NOT-CHECKED.
Pre-registration: threshold timestamp precedes confirmation records (both-states).
Reviewer: re-derive n for two strata and match the receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import calculator as C  # noqa: E402
import inputs as I  # noqa: E402
from prereg import (  # noqa: E402
    live_confirmation_records,
    precedes,
    threshold_timestamp,
)

ART = REPO / "command-center/receipts/CNF-0138.json"
THR = REPO / I.THRESHOLD_REL
EARLIER = HERE / "fixtures/confirmation_records/earlier.json"
LATER = HERE / "fixtures/confirmation_records/later.json"
NOT_CHECKED = HERE / "fixtures/false_pass_not_checked.json"


def emit_n(false_pass_doc: dict, p: float, beta: float, tau: float):
    """Return n or raise SamplingRefuse. Must not swallow NOT-CHECKED into 0."""
    phi = C.parse_false_pass(false_pass_doc)
    return C.sizes(p, beta, phi, tau)["n"]


def main() -> int:
    if not ART.is_file() or not THR.is_file():
        print("FAILED:CNF-0138-probe2 artifact or threshold missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    threshold = json.loads(THR.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0138" not in json.dumps(doc):
        print("FAILED:CNF-0138-probe2 sentinel")
        return 1

    # --- Guard: NOT-CHECKED refuses; must not emit an n ---
    nc = json.loads(NOT_CHECKED.read_text(encoding="utf-8"))
    refused = False
    leaked_n = None
    try:
        leaked_n = emit_n(nc, doc["inputs"]["p"], doc["inputs"]["beta"], doc["inputs"]["tau"])
    except C.SamplingRefuse as exc:
        refused = True
        if "NOT-CHECKED" not in str(exc):
            print(f"FAILED:CNF-0138-probe2 refuse message missing NOT-CHECKED: {exc}")
            return 1
    if not refused or leaked_n is not None:
        print(f"FAILED:CNF-0138-probe2 emitted n={leaked_n} for NOT-CHECKED")
        return 1
    # Assuming zero would yield a smaller n than the CHECKED bound; prove the
    # CHECKED path still emits a number.
    checked_n = emit_n(
        json.loads((HERE / "fixtures/false_pass_checked.json").read_text(encoding="utf-8")),
        doc["inputs"]["p"],
        doc["inputs"]["beta"],
        doc["inputs"]["tau"],
    )
    if not isinstance(checked_n, int) or checked_n < 1:
        print("FAILED:CNF-0138-probe2 CHECKED path did not emit n")
        return 1

    # --- Pre-registration both-states ---
    t0, src = threshold_timestamp(threshold)
    earlier = json.loads(EARLIER.read_text(encoding="utf-8"))
    later = json.loads(LATER.read_text(encoding="utf-8"))
    if precedes(threshold, earlier["recorded_at"]):
        print("FAILED:CNF-0138-probe2 earlier confirmation incorrectly passed")
        return 1
    if not precedes(threshold, later["recorded_at"]):
        print("FAILED:CNF-0138-probe2 later confirmation incorrectly failed")
        return 1
    live = live_confirmation_records(REPO)
    for rec in live:
        if not precedes(threshold, rec["recorded_at"]):
            print(
                "FAILED:CNF-0138-probe2 live confirmation precedes freeze "
                f"{rec}"
            )
            return 1
    # Git timestamp: prefer git path committer date; otherwise declared frozen_at
    # on a worktree that is not a git repository.
    if src not in {"git-path-committer-date", "declared_frozen_at"}:
        print(f"FAILED:CNF-0138-probe2 unknown timestamp source {src}")
        return 1
    if threshold.get("frozen_at") != doc["threshold"]["frozen_at"]:
        print("FAILED:CNF-0138-probe2 receipt freeze drifted from threshold file")
        return 1
    if abs(float(threshold["rate"]) - float(doc["threshold"]["rate"])) > 1e-12:
        print("FAILED:CNF-0138-probe2 tau drifted")
        return 1

    # --- Reviewer: two strata re-derived ---
    n_required = doc["worked_example"]["tool"]["n_stable"]
    sampled = [r for r in doc["per_stratum"] if not r["census"]]
    if len(sampled) < 2:
        print("FAILED:CNF-0138-probe2 need two non-census strata")
        return 1
    matched = []
    for row in sampled[:2]:
        want = min(n_required, row["population"])
        if want != row["n"]:
            print(
                f"FAILED:CNF-0138-probe2 stratum {row['id']} n={row['n']} "
                f"rederived={want}"
            )
            return 1
        matched.append({"id": row["id"], "n": want, "population": row["population"]})

    census = [r for r in doc["per_stratum"] if r["census"]]
    for row in census:
        if row["n"] != row["population"]:
            print(f"FAILED:CNF-0138-probe2 census {row['id']} not 100%")
            return 1

    print(
        json.dumps(
            {
                "not_checked_refused": True,
                "checked_n": checked_n,
                "timestamp_source": src,
                "frozen_at": threshold["frozen_at"],
                "git_available": bool(threshold.get("git_available")),
                "earlier_rejected": True,
                "later_accepted": True,
                "live_confirmation_count": len(live),
                "reviewer_strata": matched,
                "freeze_dt": t0.isoformat(),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0138-probe2 guard pre-registration two-strata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
