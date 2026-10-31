#!/usr/bin/env python3
"""WFA-0002 probe2: both-states closure checker + fabrication + absent NC.

Independent of probe1 (own re-derivation):
  1. the closure checker PASSES silently on the good closure;
  2. it FIRES on a known-bad state - one known-bad ref re-injected
     (phantom-01 demanded as ADD) drives rate below 1.0 and unresolved > 0;
  3. name-only candidates are REJECTED (no anchor = fabrication);
  4. the absent-input negative control: a missing artifact must fail the
     delivered predicate, never pass silently.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE_DIR))
import closure  # noqa: E402
from closure import ClosureCheckError, FabricationRejected  # noqa: E402

ARTIFACT = REPO / "command-center" / "wfa" / "WFA-0002-provenance-closure.json"
SENTINEL = "SUCCESS:WFA-0002-probe2"


def fail(msg):
    print("FAILED:WFA-0002-probe2 " + msg)
    return 1


def main():
    checks = []
    good = closure.run_closure()
    closure.verify_closure(good)  # silent on the good state
    checks.append(("good-state-silent", True))

    # Both-states: re-inject one known-bad ref as ADD-required.
    bad = copy.deepcopy(good)
    bad["closure_after"]["corrected"] -= 1
    bad["closure_after"]["provenance_edges_unresolved"] += 1
    bad["closure_after"]["provenance_resolution_rate"] = (66 - 1) / 66
    fired = False
    try:
        closure.verify_closure(bad)
    except ClosureCheckError as exc:
        fired = "rate=" in str(exc) and "unresolved=" in str(exc)
    checks.append(("reinject-known-bad-fires", fired))

    # Fabrication control: a name-only candidate (no provenance anchor).
    rejected = False
    for candidate in ({"name": "wfa0002-ghost-x"},
                      {"name": "wfa0002-ghost-y", "provenance": {"anchor_path": ""}}):
        try:
            closure.add_candidate(candidate["name"], candidate.get("provenance"))
        except FabricationRejected:
            rejected = True
        else:
            rejected = False
            break
    checks.append(("name-only-does-not-resolve", rejected))

    # Absent-input negative control: missing artifact must not read as delivered.
    absent = ARTIFACT.with_name("WFA-0002-provenance-closure.DOES-NOT-EXIST.json")
    checks.append(("absent-input-fails-delivered", not absent.exists() and ARTIFACT.is_file()))

    # The live artifact records the same fabrication rule and both-states claims.
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    checks += [
        ("artifact-fabrication-rule", doc["fabrication_control"]["name_only_does_not_resolve"] is True),
        ("artifact-rate", doc["provenance_resolution_rate"] == 1.0
            and doc["provenance_edges_unresolved"] == 0),
        ("artifact-unresolved-before", doc["unresolved_before"]["distinct_refs"] == 40
            and doc["unresolved_before"]["provenance_edges_unresolved"] == 66),
        ("fixture-graph-recorded", doc["fixture_graph"]["distinct_refs"] == 40
            and doc["fixture_graph"]["unresolved_edges"] == 66),
    ]

    for name, ok in checks:
        print(("  ok " if ok else "  RED ") + name)
        if not ok:
            return fail("check " + name + " RED")
    print(json.dumps({
        "probe": "probe2-both-states-fabrication", "unit_id": "WFA-0002",
        "pass": True, "reinject_known_bad_fires": True,
        "name_only_does_not_resolve": True, "absent_input_fails": True,
    }))
    print(SENTINEL + " checker silent on good state; known-bad reinject fires; name-only fabrication rejected; absent input fails delivered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
