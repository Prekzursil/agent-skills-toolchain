#!/usr/bin/env python3
"""Named probe 1: planted silent drop fires; unchanged pair is silent.

Both-states on the live requirements-mining-reconciliation handler, plus
the four-blueprint contract smoke so the other three are not stubs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from product_blueprints.engine import run_blueprint, smoke_all  # noqa: E402
from product_blueprints.requirements import reconcile  # noqa: E402

FIX = HERE / "fixtures"
PLANTED_ID = "REQ-PHASE13-11073"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def main() -> int:
    baseline = _read("baseline.md")
    planted_rev = _read("planted-revision.md")
    unchanged_rev = _read("unchanged-revision.md")
    explicit_rev = _read("explicit-drop-revision.md")
    revised_rev = _read("revised-login-revision.md")

    planted = run_blueprint(
        "requirements-mining-reconciliation",
        {"baseline_text": baseline, "revision_text": planted_rev},
    )
    unchanged = run_blueprint(
        "requirements-mining-reconciliation",
        {"baseline_text": baseline, "revision_text": unchanged_rev},
    )
    explicit = reconcile(baseline, explicit_rev)
    revised = reconcile(baseline, revised_rev)
    smoke = smoke_all()

    planted_ids = planted.get("silent_drop_ids") or []
    planted_fires = (
        PLANTED_ID in planted_ids
        and planted.get("silent_drop_count", 0) >= 1
        and planted.get("accounting_complete") is True
    )
    unchanged_silent = (
        unchanged.get("silent_drop_count") == 0
        and unchanged.get("silently_disappeared") == []
        and unchanged.get("accounting_complete") is True
        and unchanged.get("baseline_count") == planted.get("baseline_count")
    )
    explicit_ok = (
        explicit["silent_drop_count"] == 0
        and any(r["id"] == PLANTED_ID for r in explicit["explicitly_dropped"])
    )
    revised_ok = (
        revised["silent_drop_count"] == 0
        and any(r["id"] == "REQ-LOGIN-01" for r in revised["revised"])
        and PLANTED_ID not in revised["silent_drop_ids"]
    )
    same_bytes = unchanged_rev == baseline
    payload = {
        "probe": "probe1-silent-drop-both-states",
        "unit_id": "IMP-0246",
        "planted_fires": planted_fires,
        "planted_ids": planted_ids,
        "unchanged_silent": unchanged_silent,
        "unchanged_silent_count": unchanged.get("silent_drop_count"),
        "explicit_drop_not_silent": explicit_ok,
        "revision_not_silent": revised_ok,
        "unchanged_pair_byte_identical": same_bytes,
        "accounting_planted": planted.get("accounted"),
        "accounting_baseline": planted.get("baseline_count"),
        "four_blueprint_smoke": smoke["pass"],
        "smoke_ids": [r["id"] for r in smoke["rows"]],
        "workflow_id": planted.get("workflow_id"),
        "pass": bool(
            planted_fires
            and unchanged_silent
            and explicit_ok
            and revised_ok
            and same_bytes
            and smoke["pass"]
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0246-probe1 planted silent-drop both-states")
        return 1
    print(
        "SUCCESS:IMP-0246-probe1 planted "
        f"{PLANTED_ID} detected; unchanged pair silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
