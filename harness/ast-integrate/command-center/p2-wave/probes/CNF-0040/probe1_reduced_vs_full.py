#!/usr/bin/env python3
"""Probe 1: re-run IMP-0136 verification under declared (reduced) vs full grant."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import catalog_perms as C  # noqa: E402
import choke as K  # noqa: E402
import subject as S  # noqa: E402


def main() -> int:
    before = K.EVALUATE_CALLS
    impl = C.implementing()
    declared = impl["declared_permissions"]
    wu = C.workunit_tool_permissions_field()
    with tempfile.TemporaryDirectory(prefix="cnf0040-p1-") as tmp:
        pair = S.run_pair(declared, Path(tmp))
        mutant = S.post_spawn_mutant_overpriv(declared, declared)
    reduced, full = pair["reduced"], pair["full"]
    after = K.EVALUATE_CALLS
    print(
        json.dumps(
            {
                "probe": "probe1-reduced-vs-full",
                "unit_id": "CNF-0040",
                "implementing_unit": impl["id"],
                "declared": declared,
                "reduced_ok": reduced["ok"],
                "full_ok": full["ok"],
                "reduced_class": reduced["classification"],
                "full_class": full["classification"],
                "outcomes_relation": pair["outcomes_relation"],
                "spawns_overpriv": reduced["spawns_overpriv"],
                "spawns_compliant": reduced["spawns_compliant"],
                "post_spawn_mutant_detector_red": mutant["detector_red"],
                "post_spawn_mutant_spawns": mutant["spawns"],
                "evaluate_calls": after - before,
                "source_paths_present": impl["source_paths_present"],
                "workunit_has_tool_permissions": wu["has_tool_permissions"],
                "workunit_fields": wu["fields"],
            },
            sort_keys=True,
        )
    )
    if after <= before:
        print("FAILED:CNF-0040-probe1 choke point evaluate() was never called")
        return 1
    if not reduced["ok"]:
        print(
            f"FAILED:CNF-0040-probe1 reduced grant failed: {reduced['error_text']}"
        )
        return 1
    if not full["ok"]:
        print(f"FAILED:CNF-0040-probe1 full grant failed: {full['error_text']}")
        return 1
    if set(pair["full_grant"]) <= set(pair["reduced_grant"]):
        print("FAILED:CNF-0040-probe1 full grant is not a strict superset")
        return 1
    if reduced["spawns_overpriv"] != 0 or reduced["spawns_compliant"] != 1:
        print("FAILED:CNF-0040-probe1 spawn counts")
        return 1
    if full["spawns_overpriv"] != 0 or full["spawns_compliant"] != 1:
        print("FAILED:CNF-0040-probe1 full-grant spawn counts")
        return 1
    if pair["outcomes_relation"] not in {"explained", "differ", "differ-and-explained"}:
        print("FAILED:CNF-0040-probe1 outcomes not related")
        return 1
    if not mutant["detector_red"] or mutant["zero_spawn_assertion_holds"]:
        print(
            "FAILED:CNF-0040-probe1 post-spawn mutant did not turn the "
            "zero-spawn assertion red"
        )
        return 1
    print(
        f"reduced_ok={reduced['ok']} full_ok={full['ok']} "
        f"relation={pair['outcomes_relation']} "
        f"mutant_red={mutant['detector_red']}"
    )
    print("SUCCESS:CNF-0040-probe1 reduced vs full grant and pre-spawn control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
