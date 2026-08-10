"""Differential oracle + coverage census for the shared completion predicate.

Runs the settling experiment that command-center/COMPLETION-GATES.json names for gate A's
``implementation_state`` ("NOT-CHECKED. No shared reducer implementing these 12 conditions was
located... if each call site has its own check, that is the seeded failure class 'two completion
predicates disagree' (spec line 11314) already live").

Three measurements, all mechanical:

  A. CONDITION -> IMPLEMENTING FUNCTION table (IMP-0415's evidence_requirement: a twelve-row table
     mapping each spec condition to the exact function and line that evaluates it; any condition
     with no implementing line is a gap). Derived by parsing the module's AST, not by reading prose.

  B. SCHEMA-ONLY coverage. For each of the twelve isolated mutations, does the shared receipt
     envelope (platform/schema/receipt.schema.json, authored by the receipt-envelope lane) reject
     the mutated receipt on its own? Every mutation the schema ACCEPTS is a condition that only the
     reducer enforces - i.e. a caller who validates the schema and skips the reducer would pass it.

  C. LEGACY-PREDICATE differential against hooks/_shared/completion.py, which describes itself as
     "the ONE shared completion predicate (C1) for this harness". For each mutation, its verdict vs
     this reducer's. Every mutation where the legacy predicate says DONE and this reducer says not
     complete is a live instance of the seeded 'two completion predicates disagree' class.

Emits JSON on stdout and exits 0 when all three measurements completed (this is a MEASUREMENT tool;
a non-zero exit means it could not measure, never that the reducer is bad).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from completion_predicate import CONDITIONS, evaluate  # noqa: E402
from test_completion_predicate import MUTATORS, SENTINEL, Case  # noqa: E402

MODULE = HERE / "completion_predicate.py"
RECEIPT_SCHEMA = REPO_ROOT / "platform" / "schema" / "receipt.schema.json"
LEGACY = REPO_ROOT / "hooks" / "_shared" / "completion.py"


def condition_function_table() -> list[dict[str, Any]]:
    """Map each of the twelve conditions to the function that evaluates it, by AST."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    funcs = {
        node.name: node.lineno
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    rows: list[dict[str, Any]] = []
    for n, text, spec_line in CONDITIONS:
        matches = sorted(name for name in funcs if name.startswith(f"_c{n}_"))
        rows.append(
            {
                "condition": n,
                "spec_line": spec_line,
                "text": text,
                "function": matches[0] if matches else None,
                "anchor": (
                    f"platform/lib/completion_predicate.py:{funcs[matches[0]]}"
                    if matches
                    else None
                ),
                "gap": not matches,
            }
        )
    return rows


def schema_only_coverage(tmp: Path) -> dict[str, Any]:
    try:
        import jsonschema
    except ImportError:
        return {"status": "NOT-CHECKED", "why": "jsonschema not installed"}
    if not RECEIPT_SCHEMA.is_file():
        return {"status": "NOT-CHECKED", "why": f"{RECEIPT_SCHEMA} absent"}
    try:
        schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        validator = cls(schema)
    except Exception as exc:  # noqa: BLE001
        return {"status": "NOT-CHECKED", "why": f"schema not loadable: {exc}"}

    control = Case(tmp / "schema-control")
    control_errors = [e.message for e in validator.iter_errors(control.receipt)]
    rows: list[dict[str, Any]] = []
    for n in sorted(MUTATORS):
        c = Case(tmp / f"schema{n}")
        receipt, _ = MUTATORS[n](c)
        errors = [e.message for e in validator.iter_errors(receipt)]
        rows.append(
            {
                "condition": n,
                "schema_rejects": bool(errors),
                "first_error": errors[0] if errors else None,
            }
        )
    accepted = [r["condition"] for r in rows if not r["schema_rejects"]]
    return {
        "status": "MEASURED",
        "detector_control": {
            "known_good_receipt_accepted": not control_errors,
            "errors": control_errors[:3],
        },
        "rows": rows,
        "schema_rejects_count": sum(1 for r in rows if r["schema_rejects"]),
        "schema_accepts_count": len(accepted),
        "conditions_only_the_reducer_enforces": accepted,
    }


WHOLE_FILE_TAIL = 10**7  # search the whole artifact, not just its last 600 bytes


def legacy_differential(tmp: Path) -> dict[str, Any]:
    if not LEGACY.is_file():
        return {"status": "NOT-CHECKED", "why": f"{LEGACY} absent"}
    sys.path.insert(0, str(LEGACY.parent))
    try:
        import completion as legacy  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        return {"status": "NOT-CHECKED", "why": f"legacy module not importable: {exc}"}

    # The legacy predicate searches only the LAST `sentinel_tail` bytes for the sentinel, and
    # `classify()` does not expose that knob. Running the coverage differential at the default 600 B
    # made the KNOWN-GOOD control read FAILED, so the whole comparison measured nothing. The
    # coverage differential therefore runs with a whole-file window (control must pass), and the
    # tail-window behaviour is measured separately below with its own both-states control.
    control = Case(tmp / "legacy-control")
    ctrl_path = control.root / control.artifact_rel
    ctrl_ok, ctrl_why = legacy.artifact_ok(
        str(ctrl_path), SENTINEL, 512, sentinel_tail=WHOLE_FILE_TAIL
    )
    rows: list[dict[str, Any]] = []
    for n in sorted(MUTATORS):
        c = Case(tmp / f"legacy{n}")
        receipt, over = MUTATORS[n](c)
        mine = evaluate(receipt, c.options(**over))
        art = c.root / c.artifact_rel
        ok, why = legacy.artifact_ok(
            str(art), SENTINEL, 512, sentinel_tail=WHOLE_FILE_TAIL
        )
        rows.append(
            {
                "condition": n,
                "reducer_verdict": mine.verdict.value,
                "reducer_unsatisfied": mine.unsatisfied,
                "legacy_ok": ok,
                "legacy_reason": why,
                "disagree": ok and not mine.is_complete,
            }
        )
    disagreements = [r["condition"] for r in rows if r["disagree"]]

    # Independent measurement: the tail-window rule itself, with a both-states control. The SAME
    # file is judged with the default 600 B window and with a whole-file window; if the two agree,
    # this probe cannot see the divergence and must say so rather than report a finding.
    tail_case = Case(tmp / "tail-window")
    tp = tail_case.root / tail_case.artifact_rel
    raw = tp.read_bytes()
    idx = raw.decode("utf-8", "replace").find(SENTINEL)
    default_ok, default_why = legacy.artifact_ok(str(tp), SENTINEL, 512)
    whole_ok, whole_why = legacy.artifact_ok(
        str(tp), SENTINEL, 512, sentinel_tail=WHOLE_FILE_TAIL
    )
    mine_tail = evaluate(tail_case.receipt, tail_case.options())
    tail_window = {
        "artifact_bytes": len(raw),
        "sentinel_byte_offset": idx,
        "legacy_default_sentinel_tail": legacy.DEFAULT_SENTINEL_TAIL,
        "legacy_default_window_ok": default_ok,
        "legacy_default_window_reason": default_why,
        "legacy_whole_file_ok": whole_ok,
        "legacy_whole_file_reason": whole_why,
        "reducer_condition_5": mine_tail.condition(5).outcome.value,
        "reducer_verdict": mine_tail.verdict.value,
        "both_states_control_discriminates": default_ok != whole_ok,
        "divergence": (not default_ok) and whole_ok and mine_tail.is_complete,
    }
    return {
        "status": "MEASURED",
        "legacy_module": "hooks/_shared/completion.py",
        "legacy_self_description": "the ONE shared completion predicate (C1) for this harness",
        "coverage_differential_window": "whole-file (see note in source)",
        "detector_control": {
            "known_good_case_ok": ctrl_ok,
            "expected": True,
            "control_passes": bool(ctrl_ok),
            "reason": ctrl_why,
        },
        "rows": rows,
        "disagreement_count": len(disagreements),
        "conditions_legacy_does_not_enforce": disagreements,
        "tail_window_divergence": tail_window,
    }


def main() -> int:
    import argparse
    import tempfile

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out", default=None, help="write the PURE JSON report here (no sentinel line)"
    )
    ns = ap.parse_args()

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        table = condition_function_table()
        schema = schema_only_coverage(tmp)
        legacy = legacy_differential(tmp)

    report = {
        "artifact": "platform/lib/_predicate_differential.py output",
        "measured_at_repo_root": str(REPO_ROOT),
        "A_condition_function_table": table,
        "A_gaps": [r["condition"] for r in table if r["gap"]],
        "B_schema_only_coverage": schema,
        "C_legacy_predicate_differential": legacy,
    }
    blob = json.dumps(report, indent=2)
    if ns.out:
        Path(ns.out).write_text(blob + "\n", encoding="utf-8")
    else:
        print(blob)

    controls = {
        "A_no_condition_gap": not report["A_gaps"],
        "B_measured": schema.get("status") == "MEASURED",
        "B_control": bool(
            schema.get("detector_control", {}).get("known_good_receipt_accepted")
        ),
        "C_measured": legacy.get("status") == "MEASURED",
        "C_control": bool(legacy.get("detector_control", {}).get("control_passes")),
        "C_tail_control_discriminates": bool(
            legacy.get("tail_window_divergence", {}).get(
                "both_states_control_discriminates"
            )
        ),
    }
    failed = [k for k, v in controls.items() if not v]
    if failed:
        print(f"FAILED:predicate-differential controls_not_passing={failed}")
        return 1
    print(
        "SUCCESS:predicate-differential A_gaps=0 "
        f"B_schema_accepts={schema['schema_accepts_count']}/12 "
        f"C_legacy_unenforced={legacy['conditions_legacy_does_not_enforce']} "
        f"C_tail_divergence={legacy['tail_window_divergence']['divergence']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
