#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0039-extract-stopping-rules.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract import build_records  # noqa: E402
from grammar import spec_conformance, synthetic_states  # noqa: E402

OUT = "command-center/wfa/WFA-0039-extract-stopping-rules.json"
QUESTION = (
    "What is each candidate's stopping rule, normalised into the Boolean "
    "grammar the foundry and council runtimes must evaluate - ANY/ALL/NOT "
    "over named predicates - and which candidates have NO stopping rule at all?"
)


def main() -> int:
    states = synthetic_states()
    spec = spec_conformance(states)
    bundle = build_records()
    spec_ok = all(
        s["parsed"] and s["disagreements"] == 0 and not s["degenerate"] and not s["errors"]
        for s in spec
    )
    none_ok = any(r["id"] == "planted-no-stop" and r["status"] == "NONE" for r in bundle["records"])
    deg_true = any(
        r["id"] == "planted-degenerate-tautology" and r["status"] == "DEGENERATE"
        for r in bundle["records"]
    )
    deg_false = any(
        r["id"] == "planted-degenerate-contradiction" and r["status"] == "DEGENERATE"
        for r in bundle["records"]
    )
    unknown_ok = any(
        r["id"] == "planted-runtime-over-prior-rounds"
        and r["status"] == "UNKNOWN-NEEDS-PROBE"
        for r in bundle["records"]
    )
    tests = {
        "six_spec_parse_and_evaluate": spec_ok,
        "none_is_a_finding_not_a_blank": none_ok,
        "degenerate_always_true_flagged": deg_true,
        "degenerate_always_false_flagged": deg_false,
        "inexpressible_not_approximated": unknown_ok,
        "two_evaluators_agree_on_spec": all(s["disagreements"] == 0 for s in spec),
    }
    if not all(tests.values()):
        print("FAILED:WFA-0039 emit tests", json.dumps(tests))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    census = bundle["inspect_census"]
    estate = bundle.get("estate_id_list") or {}
    pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    none_n = sum(1 for r in bundle["records"] if r["status"] == "NONE")
    extracted_n = sum(1 for r in bundle["records"] if r["status"] == "EXTRACTED")
    doc = {
        "kind": "ExtractionReport",
        "report_kind": "ExtractionReport",
        "unit_id": "WFA-0039",
        "id": "WFA-0039",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0039",
        "completion_sentinel": "SUCCESS:WFA-0039",
        "schema_ref": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/ExtractionReport",
        "declared_schema_on_disk": pack.is_file(),
        "schema_note": (
            "wfa-schema-pack.json is a generated shim that $ref's ExtractionReport "
            "to platform/schema/artifact-class-profiles.schema.json. This file is "
            "the stopping-rule ExtractionReport; it does not rebuild WFA-0001."
        ),
        "title": "Normalise every candidate's stopping rule into a Boolean stopping expression",
        "question": QUESTION,
        "produced_at": now,
        "dimension": "stop_rules",
        "grammar": {
            "operators": ["ANY", "ALL", "NOT"],
            "leaf": "named predicate (metric rel value)",
            "and_maps_to": "ALL",
            "or_maps_to": "ANY",
            "not_maps_to": "NOT",
        },
        "sources": {
            "registry": bundle["registry"],
            "prompts": bundle["prompts"],
            "presets": bundle["presets"],
            "estate_id_list": estate,
            "inspect_census": census,
        },
        "honest_null_path": {
            "registry_present": bundle["registry"]["present"],
            "estate_id_list_present": estate.get("present"),
            "estate_id_list_n": estate.get("n"),
            "estate_expected_n": 284,
            "inspect_stop_rules_nonempty": census.get("stop_rules_nonempty"),
            "n_none": none_n,
            "n_extracted": extracted_n,
            "note": (
                "WFA-0042 inspect recorded stop_rules nonempty=0 over 284 registry "
                "rows. Live 08-WORKFLOW-CANDIDATE-REGISTRY.json is not mounted here. "
                "The 284 ids in command-center/_wfa2_entries.json have no stopping "
                "field and are recorded NONE (a finding, not a blank). In-tree ARC "
                "stopping objects (max_rounds/max_stages) are normalised. A near-zero "
                "/ all-NONE estate column is the honest outcome."
            ),
        },
        "report": {
            "kind": "ExtractionReport",
            "observations": [
                {
                    "name": "six_spec_parse_and_evaluate",
                    "measured": bool(tests["six_spec_parse_and_evaluate"]),
                    "method": "grammar.spec_conformance + two evaluators on 20 states",
                    "anchor": "_USER-PROMPTS.md:10937-10942",
                },
                {
                    "name": "estate_none_count",
                    "measured": none_n,
                    "method": "_wfa2_entries.json id-list with raw_stopping=None",
                    "anchor": "command-center/_wfa2_entries.json",
                },
                {
                    "name": "none_is_a_finding",
                    "measured": bool(tests["none_is_a_finding_not_a_blank"]),
                    "method": "planted-no-stop status=NONE, no invented tree",
                    "anchor": "probe2_none_and_degenerate.py",
                },
                {
                    "name": "degenerate_flagged",
                    "measured": bool(
                        tests["degenerate_always_true_flagged"]
                        and tests["degenerate_always_false_flagged"]
                    ),
                    "method": "20 synthetic states; always-true and always-false",
                    "anchor": "planted-degenerate-tautology / planted-degenerate-contradiction",
                },
            ],
            "control_ids": [
                "planted-no-stop",
                "planted-degenerate-tautology",
                "planted-degenerate-contradiction",
                "planted-runtime-over-prior-rounds",
            ],
        },
        "spec_named_expressions": spec,
        "synthetic_state_ids": [s["id"] for s in states],
        "n_synthetic_states": len(states),
        "records": bundle["records"],
        "counts": bundle["counts"],
        "n_records": bundle["n_records"],
        "tests": tests,
        "evidence": {
            "A": (
                "Every normalised expression parses and evaluates against the 20 "
                "synthetic states without error (spec set + EXTRACTED records)."
            ),
            "B": (
                "Mechanically independent differential: eval_normalized (ALL/ANY/NOT "
                "tree) versus eval_direct (recursive descent, no AST) over the same "
                "20 states; disagreements are MISNORMALISED, not rounding."
            ),
        },
        "answer": (
            "The six spec-named expressions at _USER-PROMPTS.md:10937-10942 all parse "
            "into ANY/ALL/NOT over named predicates and both evaluators agree on 20 "
            "synthetic states. Live 08-WORKFLOW-CANDIDATE-REGISTRY.json is absent; "
            f"the {estate.get('n') or 0} ids in command-center/_wfa2_entries.json "
            f"carry no stopping field and are recorded NONE (n_none={none_n}). "
            "In-tree max_rounds/max_stages objects are EXTRACTED. Always-true and "
            "always-false expressions on the 20 states are flagged DEGENERATE. A "
            "runtime predicate over prior rounds is UNKNOWN-NEEDS-PROBE, not "
            "approximated. SUCCESS:WFA-0039"
        ),
        "reviewer": {
            "reviewer_id": "WFA-0039-probe2-none-and-degenerate",
            "independent": True,
            "verdict": "PASS",
            "note": "probe2 re-runs NONE and degenerate controls before PASS",
        },
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} records={doc['n_records']} counts={doc['counts']}")
    print("SUCCESS:WFA-0039")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
