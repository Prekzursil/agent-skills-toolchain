"""Probe: are SEM-001 and SEM-012 mutually exclusive on a custom-metric stopping leaf?

CLAIM UNDER TEST (asserted in several preset metadata.notes blocks): a spec cannot
simultaneously satisfy
  * SEM-001 - stopping.source_expression must parse to a tree IDENTICAL to stopping.expression, and
  * SEM-012 - a custom: metric should declare a `producer`,
because the reference parser has no surface syntax for `producer` and therefore cannot
emit that key.

Both states are exercised:
  A. tree WITH producer + source_expression -> expect SEM-001 ERROR   (collision confirmed)
  B. tree WITHOUT producer + source_expression -> expect SEM-012 WARN (the cost of dropping it)
  C. tree WITH producer, NO source_expression -> expect clean        (the workaround used)

SECOND, WIDER CLAIM (found by SEM-001 rejecting C-D37, which uses NO custom metric):
the same exclusion applies to `note`, the schema's own inline-comment channel, present on all
four stop_leaf variants. So source_expression is incompatible with per-dial documentation of any
kind, not merely with custom producers.

  D. registry leaf WITH note + source_expression -> expect SEM-001 ERROR
  E. registry leaf WITHOUT note + source_expression -> expect clean (the control: proves D's
     rejection is caused by `note` alone and not by anything else in the fixture)

Run from the repo root:  python platform/council/presets/_probe_sem_rule_collision.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", "lib"))
sys.path.insert(0, LIB)

from councilspec.expression import parse  # noqa: E402
from councilspec.validate import validate_spec  # noqa: E402

SOURCE = "custom:rollback_plan_recorded == true"


def base_spec(stopping):
    return {
        "schema_version": "1.0.0",
        "council_id": "probe-sem-collision",
        "objective": {
            "statement": "Probe the SEM-001 / SEM-012 interaction.",
            "risk_tier": "low",
            "desired_output": "decision",
        },
        "participants": {
            "selection": {"mode": "automatic"},
            "count": {"mode": "exact", "exact_n": 2},
        },
        "topology": {"kind": "flat"},
        "protocol": {"sequence": [{"kind": "synthesis"}]},
        "voting": {"method": "synthesis_only"},
        "stopping": stopping,
    }


def rules_hit(result):
    hit = set()
    for f in result["findings"]:
        hit.add((f["rule"], f["severity"]))
    return hit


def main() -> int:
    parsed = parse(SOURCE)
    print(f"parse({SOURCE!r}) -> {parsed}")
    print(f"parser emitted a 'producer' key? {'producer' in parsed}")

    with_producer = dict(parsed)
    with_producer["producer"] = "apply-plan preflight"

    cases = {
        "A_producer_plus_source": base_spec(
            {"expression": with_producer, "source_expression": SOURCE}
        ),
        "B_no_producer_plus_source": base_spec(
            {"expression": dict(parsed), "source_expression": SOURCE}
        ),
        "C_producer_no_source": base_spec({"expression": with_producer}),
        "D_note_plus_source": base_spec(
            {
                "expression": {
                    "metric": "coverage_score",
                    "op": ">=",
                    "value": 1,
                    "note": "every cell marked",
                },
                "source_expression": "coverage_score >= 1",
            }
        ),
        "E_no_note_plus_source": base_spec(
            {
                "expression": {"metric": "coverage_score", "op": ">=", "value": 1},
                "source_expression": "coverage_score >= 1",
            }
        ),
    }

    observed = {}
    for name, spec in cases.items():
        res = validate_spec(spec)
        observed[name] = (res["ok"], sorted(rules_hit(res)), res["schema_errors"])
        print(f"\n{name}: ok={res['ok']}")
        for msg in res["schema_errors"]:
            print(f"   schema   {msg}")
        for msg in res["semantic_errors"]:
            print(f"   semantic {msg}")
        for msg in res["warnings"]:
            print(f"   warn     {msg}")

    failures = []
    if "producer" in parsed:
        failures.append("parser DOES emit producer; the collision claim is refuted")
    if ("SEM-001", "ERROR") not in observed["A_producer_plus_source"][1]:
        failures.append("case A did not raise SEM-001; collision NOT confirmed")
    if observed["A_producer_plus_source"][0]:
        failures.append("case A validated OK; collision NOT confirmed")
    if ("SEM-012", "WARN") not in observed["B_no_producer_plus_source"][1]:
        failures.append("case B did not raise SEM-012 WARN; detector control failed")
    if not observed["B_no_producer_plus_source"][0]:
        failures.append("case B should still be ok=True (WARN does not fail)")
    if not observed["C_producer_no_source"][0]:
        failures.append("case C (the workaround actually shipped) is NOT clean")
    if observed["C_producer_no_source"][1]:
        failures.append(
            f"case C raised findings: {observed['C_producer_no_source'][1]}"
        )
    if ("SEM-001", "ERROR") not in observed["D_note_plus_source"][1]:
        failures.append(
            "case D did not raise SEM-001; the `note` exclusion is NOT confirmed"
        )
    if not observed["E_no_note_plus_source"][0]:
        failures.append(
            "case E (same fixture minus `note`) was rejected, so case D's rejection cannot "
            "be attributed to `note`; the control failed"
        )

    print()
    if failures:
        for f in failures:
            print(f"  - {f}")
        print(
            "FAILED:sem-rule-collision-probe " + f"{len(failures)} expectation(s) unmet"
        )
        return 1
    print(
        "SUCCESS:sem-rule-collision-probe CONFIRMED - stopping.source_expression is mutually "
        "exclusive with BOTH `producer` (SEM-012, case A) and `note` (case D, isolated by the "
        "case-E control) on any stop leaf, because the reference parser emits neither key. "
        "Per-dial documentation and the human-readable source form cannot coexist; these presets "
        "keep the documentation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
