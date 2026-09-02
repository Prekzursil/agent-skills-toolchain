"""Load fixtures and run intact vs one-gate-mutant both-states."""
from __future__ import annotations

import json
from pathlib import Path

from oracle import judge, mutate_one_gate, named_gate
from structural import structural_census
from translate import translate

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
MUTANT_STAGE = "review"
MUTANT_FIELD = "score"
MUTANT_OP = "lt"


def load_json(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def load_source() -> dict:
    return load_json("foreign-workflow.json")


def load_cases() -> list[dict]:
    return [
        load_json("case-pass.json"),
        load_json("case-stop-score.json"),
        load_json("case-stop-approved.json"),
    ]


def run() -> dict:
    foreign = load_source()
    native = translate(foreign)
    cases = load_cases()
    intact_rows = [judge(foreign, native, c) for c in cases]
    intact_all = all(r["pass"] for r in intact_rows)
    mutant = mutate_one_gate(
        native, stage=MUTANT_STAGE, field=MUTANT_FIELD, new_op=MUTANT_OP
    )
    pass_case = cases[0]
    mutant_row = judge(foreign, mutant, pass_case)
    named = named_gate(mutant_row["mismatches"])
    struct_intact = structural_census(foreign, native)
    struct_mutant = structural_census(foreign, mutant)
    named_ok = (
        named is not None
        and named.get("stage") == MUTANT_STAGE
        and named.get("field") == MUTANT_FIELD
    )
    return {
        "intact_pass": bool(intact_all),
        "mutant_fail": mutant_row["pass"] is False,
        "cases_intact_all_match": bool(intact_all),
        "intact_rows": [
            {
                "case_id": r["case_id"],
                "equivalent": r["equivalent"],
                "stop": r["source_trace"]["stop"],
                "stages_entered": r["source_trace"]["stages_entered"],
            }
            for r in intact_rows
        ],
        "mutated_gate": {
            "stage": MUTANT_STAGE,
            "field": MUTANT_FIELD,
            "new_op": MUTANT_OP,
            "oracle_named": named,
            "oracle_named_the_gate": named_ok,
        },
        "mutant_mismatches": mutant_row["mismatches"],
        "mutant_source_trace": mutant_row["source_trace"],
        "mutant_translation_trace": mutant_row["translation_trace"],
        "structural_intact": struct_intact,
        "structural_mutant": struct_mutant,
        "structural_census_passes_mutant": bool(
            struct_mutant.get("would_pass_wfa0141_style")
        ),
        "oracle_fails_mutant": mutant_row["pass"] is False,
        "native_stage_count": len(native["stages"]),
        "native_gate_count": len(native["gates"]),
        "pass": bool(
            intact_all
            and mutant_row["pass"] is False
            and named_ok
            and struct_mutant.get("would_pass_wfa0141_style")
        ),
    }


def _nested(doc: dict, key: str) -> dict:
    if isinstance(doc.get(key), dict):
        return doc[key]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get(key), dict):
        return report[key]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    if isinstance(ext.get(key), dict):
        return ext[key]
    return {}


def doc_kind(doc: dict) -> str:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    return str(report.get("kind") or doc.get("kind") or "")


def doc_both_states(doc: dict) -> dict:
    return _nested(doc, "both_states")


def doc_distinction(doc: dict) -> dict:
    return _nested(doc, "wfa0141_distinction")
