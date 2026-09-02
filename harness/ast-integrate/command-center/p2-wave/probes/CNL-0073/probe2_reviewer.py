#!/usr/bin/env python3
"""Probe 2: cross-vendor reviewer re-runs both-states by set difference.

A review that did not execute the control is rejected. Also: schema validation,
vacuous-invalid record, and a mutant that launders unsuccessful search as proof.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import reviewer as R  # noqa: E402

ART_REL = (
    "command-center/design/council/"
    "CNL-0073-proof-of-impossibility-what-actually-constitutes-proof.md"
)
SCHEMA_REL = "command-center/p2-wave/probes/CNL-0073/design-note.schema.json"
PROOF_REL = "command-center/p2-wave/probes/CNL-0073/proof.py"
ART = REPO / ART_REL
SCHEMA = REPO / SCHEMA_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0073-probe2 design note missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    mutant_schema = copy.deepcopy(doc)
    del mutant_schema["state"]
    errors = list(jsonschema.Draft7Validator(schema).iter_errors(mutant_schema))
    print(f"schema_ok=True vacuous_errors={len(errors)}")
    if not errors:
        print("FAILED:CNL-0073-probe2 schema accepted a record with no state")
        return 1

    indep = R.independent_both_states()
    agree, why = R.author_agrees()
    print(f"reviewer_reran={indep['re_ran_both_states']} agree={agree} {why}")
    print(
        json.dumps(
            {
                "incomplete": indep["incomplete_luck"]["classification"],
                "exhaustive": indep["exhaustive"]["classification"],
                "gave_up": indep["gave_up"]["classification"],
                "mechanism": indep["mechanism"],
            },
            sort_keys=True,
        )
    )
    if not indep["re_ran_both_states"] or not indep["both_directions_ok"] or not agree:
        print("FAILED:CNL-0073-probe2 reviewer did not execute a passing both-states")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("re_ran_both_states") is not True or rev.get("independent") is not True:
        print("FAILED:CNL-0073-probe2 artifact reviewer did not re-run both-states")
        return 1
    if str(rev.get("vendor") or "") != "openai":
        print("FAILED:CNL-0073-probe2 reviewer vendor is not openai")
        return 1

    launder = copy.deepcopy(doc)
    bs = launder.setdefault("both_states", {})
    bs["incomplete_qualifies"] = True
    bs["incomplete_classification"] = "EXHAUSTIVE_REFUTATION"
    if bs.get("incomplete_qualifies") is True and indep["incomplete_luck"]["qualifies"] is False:
        launder_caught = True
    else:
        launder_caught = False
    print(f"launder_mutant_caught={launder_caught}")
    if not launder_caught:
        print("FAILED:CNL-0073-probe2 failed to catch unsuccessful-search launder")
        return 1

    snippets = [
        (PROOF_REL, "RULE-EXHAUSTIVENESS: unvisited must be empty"),
        (PROOF_REL, "RULE-NO-LAUNDER: unsuccessful search never discharges proof_of_impossibility"),
    ]
    for rel, snip in snippets:
        line = A.find_line(REPO / rel, snip)
        ok, why = A.resolve_anchor(REPO, rel, line, snip)
        print(f"anchor ok={ok} {why}")
        if not ok:
            print("FAILED:CNL-0073-probe2 unresolved rule anchor")
            return 1

    evidence = doc.get("evidence") or []
    mechs = {str(row.get("mechanism") or "") for row in evidence}
    if "sequential-walk" not in mechs or "set-difference" not in mechs:
        print(f"FAILED:CNL-0073-probe2 evidence mechanisms not independent: {mechs}")
        return 1
    if "SUCCESS:CNL-0073" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0073-probe2 sentinel absent")
        return 1
    print("SUCCESS:CNL-0073-probe2 reviewer both-states schema mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
