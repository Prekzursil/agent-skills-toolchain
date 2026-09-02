#!/usr/bin/env python3
"""Probe 1: singularity of the capability-to-authority table.

Every row has exactly one authority. A planted two-authority row MUST fail
the same checker (both-states). Does not trust a precomputed authority_count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hybrid as H  # noqa: E402

DESIGN = H.REPO / "command-center/phase3/A9/DESIGN.json"


def row_key(row: dict) -> tuple[str, str]:
    auths = H._authority_list(row)
    auth = auths[0] if len(auths) == 1 else ",".join(auths)
    return (str(row.get("capability_class")), auth)


def main() -> int:
    if not DESIGN.is_file():
        print("FAILED:ARC-0059-probe1 DESIGN.json absent")
        return 1
    doc = json.loads(DESIGN.read_text(encoding="utf-8"))
    table = H.design_get(doc, "capability_to_authority_table")
    planes = H.design_get(doc, "control_planes")
    if not isinstance(table, list) or len(table) < 8:
        print(f"FAILED:ARC-0059-probe1 table missing or short n={type(table)}")
        return 1
    if not isinstance(planes, list) or len(planes) < 2:
        print("FAILED:ARC-0059-probe1 control_planes missing")
        return 1

    ok_live, defects_live = H.check_singularity(table, planes)
    print(f"live_table rows={len(table)} planes={len(planes)} ok={ok_live}")
    for d in defects_live:
        print(f"  live_defect {d}")

    derived = H.table_from_planes(planes)
    live_set = {row_key(r) for r in table}
    derived_set = {row_key(r) for r in derived}
    match_planes = live_set == derived_set
    print(f"table_matches_planes_governs={match_planes}")
    if not match_planes:
        print(f"  only_table={sorted(live_set - derived_set)[:8]}")
        print(f"  only_planes={sorted(derived_set - live_set)[:8]}")

    kernel = H.table_from_planes(H.CONTROL_PLANES)
    ok_kernel, defects_kernel = H.check_singularity(kernel, H.CONTROL_PLANES)
    kernel_set = {row_key(r) for r in kernel}
    match_kernel = live_set == kernel_set
    print(f"kernel_ok={ok_kernel} table_matches_kernel={match_kernel}")
    for d in defects_kernel:
        print(f"  kernel_defect {d}")

    planted = H.planted_duplicate_table()
    ok_planted, defects_planted = H.check_singularity(planted, H.CONTROL_PLANES)
    fired = (not ok_planted) and any("P0" in d for d in defects_planted)
    print(f"planted_duplicate ok={ok_planted} fired_on_bad={fired}")
    for d in defects_planted[:6]:
        print(f"  planted {d}")

    two_auth_rows = [r for r in table if len(H._authority_list(r)) != 1]
    print(f"live_non_singular_rows={len(two_auth_rows)}")

    if not (ok_live and ok_kernel and match_planes and match_kernel and fired):
        print("FAILED:ARC-0059-probe1 singularity assertion")
        return 1
    print("SUCCESS:ARC-0059-probe1 singularity assertion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
