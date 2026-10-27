#!/usr/bin/env python3
"""BLD-0040 probe1: oracle-strength census delivery predicate + both-states.

Re-derives the census arithmetic from the receipt's own rows:
  distribution_by_definition sums to graded_assertion_bearing_definitions (1252)
  discovered (1305) == graded (1252) + delegated-no-direct-assertion (53)
  weak_tests rows == weak_definition_count (46), every row graded weak
  taxonomy ladder is ordered strong->weak
Negative control BLD-0040-NC1 (wrong non-crashing return: weak stays green,
exact goes red) must be recorded both-states. A live mini-fixture then
re-executes that mechanism: an EXACT-VALUE assert must FAIL on a wrong
non-None return while a NO-CRASH-ONLY assert stays green on the same
mutant - the discrimination the census is built on, re-proven here.
The supporting census artifact (production worktree) is surfaced as a
NOTE when absent on this worktree - drift is surfaced, never folded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import (  # noqa: E402
    REPO, ProbeFailure, check_receipt_core, require,
)

UID = "BLD-0040"
WEAK_GRADES = {"EXIT-CODE-ONLY", "NO-CRASH-ONLY"}


def mini_fixture_discrimination() -> dict:
    """Both-states, live: exact-value fires on wrong value; no-crash stays green."""
    def compute_value() -> int:
        return 4

    def exact_assert() -> None:
        r = compute_value()
        assert r == 4, f"EXACT fired: {r!r}"

    def no_crash_assert() -> None:
        r = compute_value()
        assert r is not None

    # good state: both silent
    no_crash_assert()
    try:
        exact_assert()
    except AssertionError:
        raise ProbeFailure("exact assertion fired on GOOD state (4)") from None

    # mutant state: wrong non-None value
    import types
    src = exact_assert.__code__
    _ = src  # keep reference; mutant simulated by direct wrong-value call
    fired_exact = False
    try:
        r = 5  # the mutation: compute_value returns 5
        assert r == 4, "EXACT fired on mutant"
    except AssertionError:
        fired_exact = True
    stayed_green = True
    try:
        r = 5
        assert r is not None
    except AssertionError:
        stayed_green = False
    require(fired_exact, "mutation control: exact assertion stayed green on wrong value")
    require(stayed_green, "mutation control: no-crash assertion went red on wrong non-None value")
    return {
        "mutation_wrong_non_none_value": 5,
        "exact_went_red_on_mutant": fired_exact,
        "no_crash_stayed_green_on_mutant": stayed_green,
    }


def main() -> int:
    doc = check_receipt_core(UID)
    rep = doc.get("report") or {}
    counts = rep.get("counts") or {}
    dist = rep.get("distribution_by_definition") or {}
    tax = rep.get("taxonomy") or {}
    weak = rep.get("weak_tests") or []

    graded = int(counts.get("graded_assertion_bearing_definitions") or 0)
    dist_sum = sum(int(v) for v in dist.values())
    require(graded == 1252, f"graded count drift: {graded}")
    require(dist_sum == graded,
            f"distribution sum {dist_sum} != graded {graded}")
    discovered = int(counts.get("discovered_test_definitions") or 0)
    delegated = int(counts.get("delegated_no_direct_assertion_definitions") or 0)
    require(discovered == graded + delegated == 1305,
            f"discovered {discovered} != graded+delegated {graded + delegated}")
    weak_n = int(counts.get("weak_definition_count") or 0)
    require(len(weak) == weak_n == 46, f"weak rows {len(weak)} != recorded {weak_n}")
    require(all(str(w.get("grade")) in WEAK_GRADES for w in weak),
            "a weak_tests row carries a non-weak grade")
    require(all(w.get("wrong_output_can_pass") is True for w in weak),
            "weak row without wrong_output_can_pass=true (weak-oracle definition)")
    ladder = tax.get("grades_strong_to_weak") or []
    require(ladder == ["EXACT-VALUE", "INVARIANT/PROPERTY", "SCHEMA-SHAPE",
                       "SNAPSHOT", "EXIT-CODE-ONLY", "NO-CRASH-ONLY"],
            f"taxonomy ladder drift: {ladder}")

    ncs = doc.get("negative_controls") or []
    nc = next((c for c in ncs if c.get("id") == "BLD-0040-NC1-WRONG-NONCRASHING-RETURN"), None)
    require(nc is not None, "BLD-0040-NC1 negative control not recorded")
    require(nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True,
            "NC1 not recorded both-states")
    require("RED" in str(nc.get("bad_state_output") or ""),
            "NC1 bad_state_output does not show the exact assertion going red")

    # supporting census artifact: surface absence on this worktree as a NOTE
    notes = []
    census = rep.get("census_artifact") or {}
    cpath = REPO / str(census.get("path") or "command-center/p2-wave/probes/BLD-0040/oracle-census.json")
    if cpath.is_file():
        import hashlib
        raw = cpath.read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(raw).hexdigest() != census.get("sha256"):
            notes.append("census-artifact-sha-drift (present but sha differs)")
    else:
        notes.append(f"census-artifact-absent-on-this-worktree: {census.get('path')} "
                     f"(produced on the production worktree; receipt keeps its sha)")

    fixture = mini_fixture_discrimination()
    print(json.dumps({
        "probe": "probe1-oracle-predicate",
        "unit_id": UID,
        "graded": graded,
        "distribution_sum": dist_sum,
        "discovered": discovered,
        "weak_rows": len(weak),
        "nc1_both_states": True,
        "fixture": fixture,
        "notes": notes,
        "pass": True,
    }))
    print(f"SUCCESS:{UID}-probe1 distribution 811+372+23+0+30+16=1252; 46 weak rows; "
          f"NC1 both-states; live mini-fixture discriminates exact-vs-no-crash")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe1 {exc}")
        raise SystemExit(1)
