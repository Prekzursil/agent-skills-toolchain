#!/usr/bin/env python3
"""Named probe 2: empty result vs query error; SBOM-ABSENT stays in query space.

Reviewer requirement: packages published without an SBOM are visible as unknown,
never filtered out of the query space.
NEGATIVE CONTROL: a component in zero packages returns explicit empty, not error.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MARKET = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MARKET))

import planted as fx  # noqa: E402
from sbom_registry import EMPTY_RESULT, QUERY_ERROR, SBOM_ABSENT, SbomRegistry  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0092-p2-") as tmp:
        reg = SbomRegistry(Path(tmp))
        pub = fx.populate(reg)
        if pub["delta"]["ok"] is not True or pub["delta"]["sbom_status"] != SBOM_ABSENT:
            print("FAILED:IMP-0092-probe2 delta not recorded SBOM-ABSENT")
            print(json.dumps(pub["delta"], default=str)[:2000])
            return 1
        if pub["epsilon_rejected"]["ok"] is not False:
            print("FAILED:IMP-0092-probe2 invalid SBOM was accepted")
            return 1

        empty = reg.indexed_query(fx.ZERO_NAME, fx.ZERO_VER)
        brute_empty = reg.brute_force_query(fx.ZERO_NAME, fx.ZERO_VER)
        err = reg.indexed_query("", "")
        if not empty["ok"] or not empty["empty"] or empty["kind"] != EMPTY_RESULT:
            print("FAILED:IMP-0092-probe2 zero-hit was not explicit empty")
            print(json.dumps(empty, default=str)[:2000])
            return 1
        if not brute_empty["ok"] or not brute_empty["empty"]:
            print("FAILED:IMP-0092-probe2 brute zero-hit was not empty")
            return 1
        if err["ok"] or err["kind"] != QUERY_ERROR or err["empty"] is not False:
            print("FAILED:IMP-0092-probe2 invalid query not distinguishable from empty")
            print(json.dumps(err, default=str)[:2000])
            return 1
        if empty["matches"] != [] or err["matches"] is not None:
            print("FAILED:IMP-0092-probe2 matches field does not distinguish empty vs error")
            return 1

        space = reg.query_space()
        absent_id = f"{fx.ABSENT_PKG}@{fx.ABSENT_VER}"
        space_ids = {r["id"] for r in space}
        if absent_id not in space_ids:
            print("FAILED:IMP-0092-probe2 SBOM-ABSENT filtered from query space")
            print(sorted(space_ids))
            return 1
        if "pkg-epsilon@0.0.1" in space_ids:
            print("FAILED:IMP-0092-probe2 rejected invalid SBOM appeared in query space")
            return 1

        planted = reg.indexed_query(fx.PLANTED_NAME, fx.PLANTED_VER)
        if absent_id not in planted["query_space_ids"]:
            print("FAILED:IMP-0092-probe2 absent id missing from query_space_ids")
            return 1
        if absent_id not in planted["unknown_ids"]:
            print("FAILED:IMP-0092-probe2 absent id missing from unknown (filtered)")
            return 1
        if absent_id in planted["match_ids"]:
            print("FAILED:IMP-0092-probe2 SBOM-ABSENT falsely listed as a match")
            return 1
        unknown_row = next(r for r in planted["unknown"] if r["id"] == absent_id)
        if unknown_row["sbom_status"] != SBOM_ABSENT:
            print("FAILED:IMP-0092-probe2 unknown row not marked SBOM-ABSENT")
            return 1
        if planted.get("sbom_absent_visible") is not True:
            print("FAILED:IMP-0092-probe2 sbom_absent_visible is not true")
            return 1
        brute = reg.brute_force_query(fx.PLANTED_NAME, fx.PLANTED_VER)
        if absent_id not in brute["unknown_ids"]:
            print("FAILED:IMP-0092-probe2 brute filtered SBOM-ABSENT")
            return 1

        out = {
            "probe": "probe2-absent-and-empty",
            "unit_id": "IMP-0092",
            "pass": True,
            "empty_ok": True,
            "empty_kind": empty["kind"],
            "error_kind": err["kind"],
            "empty_distinguishable_from_error": True,
            "sbom_absent_id": absent_id,
            "sbom_absent_in_query_space": True,
            "sbom_absent_in_unknown": True,
            "sbom_absent_not_a_match": True,
            "invalid_sbom_rejected": True,
            "reviewer_verdict": "PASS",
            "reviewer_claim": "SBOM-ABSENT packages are visible as unknown, not filtered out",
        }
        print(json.dumps(out, sort_keys=True))
        print(
            "empty_vs_error=True absent_visible=True "
            f"absent_id={absent_id} unknown={planted['unknown_ids']}"
        )
        print("SUCCESS:IMP-0092-probe2 SBOM-ABSENT visible; empty distinguishable from error")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
