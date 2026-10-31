"""Probe: can a stop leaf carry `note` / `producer` while the spec also declares
`stopping.source_expression`?

Why it matters for build/preset-4: the presets must be "editable (documented, commented
fields - not an opaque blob)". JSON has no comments, so per-leaf `note` is the only place a
metric can be explained next to itself. But SEM-001 requires
`parse(source_expression) == stopping.expression` as a DICT EQUALITY, and
`councilspec.expression.parse` never emits `note` or `producer` keys. If that makes the two
mutually exclusive, every preset must move its per-metric prose into `metadata.notes`.

Both-states control: the same spec is checked WITH and WITHOUT source_expression, so a
"SEM-001 fires" reading cannot be an artifact of the spec being broken some other way.

Run: python platform/council/_probe_note_vs_source_expression.py
"""

from __future__ import annotations

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "lib"))
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from councilspec.expression import parse  # noqa: E402
from councilspec.validate import validate_spec  # noqa: E402

BASE = {
    "schema_version": "1.0.0",
    "council_id": "probe-note-vs-source",
    "objective": {
        "statement": "Probe whether leaf note survives the SEM-001 round trip.",
        "risk_tier": "low",
        "desired_output": "review_verdict",
    },
    "participants": {
        "selection": {"mode": "mixed"},
        "count": {"mode": "exact", "exact_n": 2},
    },
    "topology": {"kind": "flat"},
    "protocol": {"sequence": [{"kind": "synthesis", "stage_id": "s1"}]},
    "voting": {"method": "synthesis_only"},
    "stopping": {
        "source_expression": "consensus >= 0.8",
        "expression": {"metric": "consensus", "op": ">=", "value": 0.8},
    },
}


def _rule_ids(result):
    return sorted({e.split()[1] for e in result["semantic_errors"]})


def main() -> int:
    rows = []

    # 1. control: plain leaf + source_expression must be clean.
    plain = copy.deepcopy(BASE)
    r = validate_spec(plain)
    rows.append(("leaf WITHOUT note, WITH source_expression", r["ok"], _rule_ids(r)))

    # 2. leaf carries `note` AND the spec declares source_expression.
    noted = copy.deepcopy(BASE)
    noted["stopping"]["expression"]["note"] = (
        "consensus is the vote-share agreement index"
    )
    r_noted = validate_spec(noted)
    rows.append(
        ("leaf WITH note, WITH source_expression", r_noted["ok"], _rule_ids(r_noted))
    )

    # 3. same leaf+note but source_expression removed -> the other half of the both-states test.
    noted_nosrc = copy.deepcopy(noted)
    noted_nosrc["stopping"].pop("source_expression")
    r_nosrc = validate_spec(noted_nosrc)
    rows.append(
        ("leaf WITH note, NO source_expression", r_nosrc["ok"], _rule_ids(r_nosrc))
    )

    # 4. custom metric + producer (SEM-012 wants a producer) + source_expression.
    cust = copy.deepcopy(BASE)
    cust["stopping"]["source_expression"] = "custom:hook_observed_firing == true"
    cust["stopping"]["expression"] = {
        "metric": "custom:hook_observed_firing",
        "op": "==",
        "value": True,
        "value_type": "boolean",
        "producer": "hooks/_dispatch/manifest.json observed-fire probe",
    }
    r_cust = validate_spec(cust)
    rows.append(
        (
            "custom leaf WITH producer, WITH source_expression",
            r_cust["ok"],
            _rule_ids(r_cust),
        )
    )

    # 5. custom metric, producer dropped, source_expression kept -> WARN only, still ok.
    cust_nop = copy.deepcopy(cust)
    cust_nop["stopping"]["expression"].pop("producer")
    r_nop = validate_spec(cust_nop)
    rows.append(
        (
            "custom leaf NO producer, WITH source_expression",
            r_nop["ok"],
            _rule_ids(r_nop)
            + ["WARN:" + ",".join(sorted({w.split()[1] for w in r_nop["warnings"]}))],
        )
    )

    width = max(len(r[0]) for r in rows)
    for label, ok, rules in rows:
        print(f"{label:<{width}}  ok={str(ok):<5} rules={rules}")

    print()
    print("parse() leaf keys                     :", sorted(parse("consensus >= 0.8")))
    print("schema-legal leaf keys (numeric)      : ['metric', 'note', 'op', 'value']")

    conflict = (
        r["ok"] is True
        and r_noted["ok"] is False
        and r_nosrc["ok"] is True
        and r_cust["ok"] is False
        and r_nop["ok"] is True
    )
    print()
    if conflict:
        print(
            "CONFIRMED: `note` / `producer` on a stop leaf is MUTUALLY EXCLUSIVE with"
        )
        print(
            "           stopping.source_expression, because SEM-001 compares trees by dict"
        )
        print(
            "           equality and parse() emits neither key. Both-states control held:"
        )
        print(
            "           the identical leaf validates once source_expression is removed."
        )
        print("SUCCESS:probe-note-vs-source-expression conflict CONFIRMED")
        return 0
    print(
        "REFUTED or INCONCLUSIVE - the five readings above do not form the conflict pattern."
    )
    print("FAILED:probe-note-vs-source-expression pattern not reproduced")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
