#!/usr/bin/env python3
"""Named probe 2: clean four-op drill + skip accounting + destroy-and-catch.

Different field than probe 1. Probe 1 reads hostile-path identity and
install-time owner deletion. This probe reads isolation, per-operation
hashed/skipped/altered counts, the skip-vs-pass split, and a reviewer
attempt to destroy the owner case-sibling through uninstall.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lifecycle import APPLICATORS, OPS, apply_uninstall_casefold_wipe  # noqa: E402
from oracle import run_op  # noqa: E402
from profile import (  # noqa: E402
    CASE_OWNER_REL,
    IsolationError,
    assert_isolated,
    fresh_profile,
    owner_home,
)

ART = REPO / "command-center/receipts/REL-0008.json"


def fail(msg: str) -> int:
    print(f"FAILED:REL-0008-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:REL-0008" not in text:
        return fail("sentinel absent")

    fired = False
    try:
        assert_isolated(owner_home())
    except IsolationError:
        fired = True
    if not fired:
        return fail("isolation did not fire on owner HOME")

    live_rows = []
    with fresh_profile() as (root, info, seed):
        if not info.get("isolated") or root.resolve() == owner_home():
            return fail("canary not isolated")
        for name in ("install", "upgrade", "rollback", "uninstall"):
            result = run_op(root, name, APPLICATORS[name], OPS[name])
            if not result.silent:
                return fail(f"clean {name} loss={result.loss}")
            if not isinstance(result.paths_hashed, int) or result.paths_hashed < 1:
                return fail(f"clean {name} hashed_path_count not a positive int")
            if seed["fifo_rel"] in result.verified_unchanged:
                return fail(f"clean {name} folded skip into pass")
            if seed["fifo_rel"] not in result.skipped_paths:
                return fail(f"clean {name} fifo not NOT-CHECKED")
            if result.honest_pass_count >= result.lying_pass_count:
                return fail(f"clean {name} skip-fold metric collapsed")
            live_rows.append(result.as_dict())

    with fresh_profile() as (root, _info, _seed):
        run_op(root, "install", APPLICATORS["install"], OPS["install"])
        destroyed = run_op(
            root,
            "uninstall-casefold-wipe",
            apply_uninstall_casefold_wipe,
            OPS["uninstall"],
        )
    lost = [row["path"] for row in destroyed.loss]
    if CASE_OWNER_REL not in lost:
        return fail(f"reviewer destroy not caught lost={lost}")

    report = doc.get("report") or {}
    if report.get("kind") != "lifecycle-drill-receipt":
        return fail(f"report.kind={report.get('kind')}")
    recorded_ops = report.get("operations") or []
    if len(recorded_ops) != 4:
        return fail(f"receipt operations={len(recorded_ops)} want=4")
    for live, rec in zip(live_rows, recorded_ops):
        if rec.get("name") != live["name"]:
            return fail(f"receipt op name drift {rec.get('name')}")
        if rec.get("paths_hashed") != live["paths_hashed"]:
            return fail(f"receipt hashed drift {live['name']}")
        if rec.get("paths_skipped") != live["paths_skipped"]:
            return fail(f"receipt skipped drift {live['name']}")
        if rec.get("oracle_silent") is not True:
            return fail(f"receipt {live['name']} not silent")
        if rec.get("skipped_are_not_checked") is not True:
            return fail(f"receipt {live['name']} skipped not marked NOT-CHECKED")
        if rec.get("skip_folded_into_pass") is not False:
            return fail(f"receipt {live['name']} folded skips")

    if report.get("hashed_path_count") != live_rows[0]["paths_hashed"]:
        return fail("receipt hashed_path_count drift")
    if report.get("skip_folded_into_pass") is not False:
        return fail("receipt skip_folded_into_pass not false")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        return fail("receipt reviewer not independent PASS")
    recorded_destroy = report.get("reviewer_destroy") or {}
    if CASE_OWNER_REL not in (recorded_destroy.get("lost_paths") or []):
        return fail("receipt reviewer_destroy drift")

    out = {
        "probe": "probe2-clean-four-ops",
        "unit_id": "REL-0008",
        "isolation_fired_on_home": True,
        "ops_silent": [r["name"] for r in live_rows],
        "hashed_path_count": live_rows[0]["paths_hashed"],
        "paths_skipped": live_rows[0]["paths_skipped"],
        "skip_folded_into_pass": False,
        "reviewer_caught": True,
        "destroyed_owner_path": CASE_OWNER_REL,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"isolated=True hashed_path_count={live_rows[0]['paths_hashed']} "
        f"skipped={live_rows[0]['paths_skipped']} destroy_caught={CASE_OWNER_REL}"
    )
    print("SUCCESS:REL-0008-probe2 clean four-ops and destroy-and-catch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
