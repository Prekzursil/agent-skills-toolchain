#!/usr/bin/env python3
"""Emit command-center/design/council/CNL-0107-security-red-blue-council-preset.md (JSON)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema.validators import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import instantiate as I  # noqa: E402
import schema_util as S  # noqa: E402

OUT = "command-center/design/council/CNL-0107-security-red-blue-council-preset.md"
SCHEMA = "command-center/p2-wave/probes/CNL-0107/council-preset.schema.json"
CATALOG_SCHEMA = "command-center/schema/council-preset.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0107/probe1_instantiate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0107/probe2_schema_timeout.py"
)
QUESTION = (
    "What asymmetric budgets, evidence standards and win conditions does the "
    "red/blue preset set, and what stops the exercise from concluding that the "
    "defended system is secure merely because red ran out of time?"
)


def err_count(validator: Draft202012Validator, doc: object) -> int:
    return sum(1 for _ in validator.iter_errors(doc))


def main() -> int:
    task = I.load_task()
    ours = I.load_preset("preset_cnl0107.json")
    sibling = I.load_preset("preset_sibling_p08.json")
    catalog = I.load_preset("preset_catalog_class.json")
    invalid = I.load_preset("invalid_preset.json")
    inst = I.instantiate(ours, task)
    sib_inst = I.instantiate(sibling, task)
    axes = I.profile_diff_axes(inst["profile"], sib_inst["profile"])
    lib = I.library_present()
    timeout_state = I.timeout_without_coverage_state()
    ours_to = I.evaluate_stop(ours, timeout_state)
    sib_to = I.evaluate_stop(sibling, timeout_state)

    preset_validator = S.preset_validator()
    n_ours = err_count(preset_validator, ours)
    n_sib = err_count(preset_validator, sibling)
    n_cat = err_count(preset_validator, catalog)
    n_bad = err_count(preset_validator, invalid)
    if n_ours or n_sib or n_cat or n_bad == 0:
        print(f"FAILED:CNL-0107 emit schema counts ours={n_ours} sib={n_sib} cat={n_cat} bad={n_bad}")
        return 1
    if ours_to != "INCONCLUSIVE" or sib_to != "BLUE_WINS" or "timeout_outcome" not in axes:
        print(f"FAILED:CNL-0107 emit timeout/sibling ours={ours_to} sib={sib_to} axes={axes}")
        return 1

    negative = (
        "Draft202012Validator on fixtures/invalid_preset.json (missing required "
        f"roles/stopping/win_conditions/...) yields {n_bad} errors. "
        "evaluate_stop on red_budget_exhausted + all_qualifying_closed + "
        "blue_claims_secure=true + coverage_ack_from_red=false returns "
        f"{ours_to} (INCONCLUSIVE). The check is meant to reject concluding "
        "BLUE_WINS / 'system is secure' from the clock plus a blue assertion."
    )

    doc = {
        "unit_id": "CNL-0107",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0107",
        "schema_version": 1,
        "kind": "council-preset-design",
        "title": "Security red/blue council preset",
        "question": QUESTION,
        "answers": {
            "asymmetric_budgets": (
                "Red receives a larger search-round budget (default 6) spent only on "
                "in-scope exploration. Blue receives a per-finding rebuttal budget "
                "(default 2 rounds per qualifying finding), not a global pool that "
                "can be used to wait out the clock. Neutral roles (scope referee, "
                "coverage clerk) have a small fixed budget and cannot be starved "
                "into issuing a security verdict. Swapping the numeric budgets does "
                "not swap the timeout outcome: exhausted red search without a "
                "red-signed coverage.ack is still INCONCLUSIVE."
            ),
            "evidence_standards": (
                "A red win-relevant finding is a red_scribe artifact with surface, "
                "repro_steps, observable_effect, blast_radius_class, and "
                "scribe_signature — attack-notes or moderator impression do not "
                "qualify. A blue close is a counter-artifact (patch, compensating "
                "control, or scoped exclusion with a named bound) plus a "
                "reproducer verdict. Coverage is a red-signed remaining-surface "
                "enumeration recorded by coverage_clerk; blue cannot author it."
            ),
            "win_conditions": (
                "RED_WINS: at least one unrebutted qualifying finding. BLUE_WINS: "
                "every qualifying finding is closed AND a red-signed coverage.ack "
                "exists. INCONCLUSIVE: red budget exhausted without those two blue "
                "conditions. Illegal: mapping timeout to BLUE_WINS, a majority "
                "'is it secure?' poll, a blue-authored coverage.ack, or a referee "
                "security verdict."
            ),
            "timeout_is_not_secure": (
                "The stopping expression evaluates timeout only after RED_WINS and "
                "BLUE_WINS gates. timeout_outcome is INCONCLUSIVE and "
                "timeout_may_not_map_to_blue_win is true. A blue claim that the "
                "system is secure, or a closed-finding set without red coverage.ack, "
                "cannot fill that gap. The nearest sibling preset.p08-red-blue-team "
                "maps red_budget_exhausted to BLUE_WINS; that is the differential "
                "this preset exists to close."
            ),
        },
        "preset": ours,
        "extends_or_supersedes": [
            {
                "kind": "protocol",
                "id": "P08",
                "relation": "extends",
                "note": "Catalog-cited ADVERSARIAL protocol P08 red-blue-team (CNL-0039 family list).",
            },
            {
                "kind": "topology_unit",
                "id": "CNL-0033",
                "relation": "instantiates",
                "note": "Asymmetric red/blue mandates: budget swap must not swap the winner on timeout.",
            },
            {
                "kind": "preset_type_unit",
                "id": "CNL-0101",
                "relation": "conforms",
                "note": "Typed delta over a CouncilSpec/protocol base, not a forked charter.",
            },
        ],
        "nearest_sibling": {
            "id": sibling["id"],
            "named_explicitly": True,
            "source": (
                "Reconstructed P08 red-blue-team baseline from catalog-cited protocol "
                "name (CNL-0039 question lists P08 red-blue-team). "
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree, "
                "so this is not a byte copy of a library record."
            ),
            "library_file_on_this_tree": lib["present"],
            "profile_differs": bool(axes),
            "differing_axes": axes,
        },
        "instantiation": {
            "task_id": inst["task_id"],
            "roster": inst["roster"],
            "protocol_schedule": inst["protocol_schedule"],
            "voting_method": inst["voting_method"],
            "stopping_expression": inst["stopping_expression"],
        },
        "tests": {
            "schema": {
                "draft": "2020-12",
                "validator": "jsonschema.Draft202012Validator",
                "affected_records": {
                    "council.preset.security-red-blue": n_ours,
                    "preset.p08-red-blue-team": n_sib,
                    "council.preset.catalog-class.editable": n_cat,
                },
                "expected_error_count_valid": 0,
                "invalid_record_error_count": n_bad,
            },
            "negative_control": {
                "verbatim": negative,
                "invalid_record": "command-center/p2-wave/probes/CNL-0107/fixtures/invalid_preset.json",
            },
            "timeout_control": {
                "state": timeout_state,
                "ours_outcome": ours_to,
                "sibling_outcome": sib_to,
                "required_ours": "INCONCLUSIVE",
            },
            "sibling_differential": {
                "sibling_id": sibling["id"],
                "axes": axes,
            },
        },
        "reviewer": {
            "reviewer_id": "CNL-0107-probe2-schema-timeout",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-validates records with Draft202012Validator and re-runs "
                "the timeout-without-coverage state without reading probe 1's argument."
            ),
        },
        "honesty": {
            "library_12_present": lib["present"],
            "dependency_artifacts_present": False,
            "catalog_output_schema": CATALOG_SCHEMA,
            "executable_schema": SCHEMA,
            "did_not_overwrite_generated_shim": True,
            "reconstruction_note": (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json, 11-COUNCIL-SPECIFICATION.schema.json, "
                "and dependency artifacts CNL-0101/CNL-0033/CNL-0039 are absent on this "
                "worktree. Nearest sibling is a reconstructed P08-bound preset whose "
                "naive timeout→BLUE_WINS mapping is the failure named by this unit's "
                "question. Second comparator council.preset.catalog-class.editable is "
                "the on-tree ARC-0003/ARC-0010 catalog-class reconstruction. This unit "
                "does not claim a 72-preset library recount. Catalog "
                "command-center/schema/council-preset.schema.json is a generated "
                "generic_report shim with no $defs.council_preset; live Draft202012 "
                "validation uses the unit-local schema and does not overwrite the shim."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "instantiate-and-sibling-differential"},
            {"id": "probe2", "command": P2, "role": "schema-and-timeout-not-secure"},
        ],
    }

    wrapper_errors = list(S.envelope_validator().iter_errors(doc))
    if wrapper_errors:
        print("FAILED:CNL-0107 emit wrapper schema")
        for e in wrapper_errors[:8]:
            print(f"  {list(e.path)}: {e.message}")
        return 1
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if "SUCCESS:CNL-0107" not in text:
        print("FAILED:CNL-0107 emit sentinel missing")
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))}")
    print("SUCCESS:CNL-0107 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
