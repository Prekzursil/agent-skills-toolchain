#!/usr/bin/env python3
"""Probe 2: two-strikes pivot at strike two, not three; text-matching mutant.

Mechanically different from probe 1 (class-cap table with distinct fingerprints):
this probe holds the fingerprint constant, asserts PIVOT at attempt 2 with
required_fix named, and shows a text-matching mutant collapsing typed classes
that production keeps apart. AST of decide() must not load a message field.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ENG = REPO / "tools" / "command-center" / "retry_engine.py"
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import retry_engine as R  # noqa: E402

FORBIDDEN_ATTRS = frozenset(
    {
        "message",
        "raw_text",
        "error_text",
        "error_string",
        "stderr",
        "stdout",
        "errmsg",
        "err_msg",
    }
)


def ast_decide_reads_text(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    typed_has_message = False
    decide_args: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "TypedFailure":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    if item.target.id in FORBIDDEN_ATTRS:
                        typed_has_message = True
                        hits.append(f"TypedFailure.{item.target.id}")
        if isinstance(node, ast.FunctionDef) and node.name == "decide":
            decide_args = [a.arg for a in node.args.args]
            if any(a in FORBIDDEN_ATTRS or a in {"text", "error", "msg"} for a in decide_args):
                hits.append(f"decide args {decide_args}")
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            hits.append(f"attr .{node.attr} L{node.lineno}")
    return {
        "hits": hits,
        "typed_has_message": typed_has_message,
        "decide_args": decide_args,
        "clean": not hits and not typed_has_message,
    }


def mutant_decide_from_text(message: str, failed_so_far: int, max_attempts: int) -> str:
    """Defect: text-matching-instead-of-typing. Not used by production."""
    blob = (message or "").lower()
    if "schema" in blob and "invalid" in blob and "timeout" not in blob:
        return "STOP"
    if any(tok in blob for tok in ("timeout", "reset", "429", "unavailable")):
        if failed_so_far < max_attempts:
            return "RETRY"
        return "STOP"
    if failed_so_far < max_attempts:
        return "RETRY"
    return "STOP"


def main() -> int:
    demo = R.two_strikes_demo()
    ast_report = ast_decide_reads_text(ENG)

    # Mutant vs production on swapped decoy strings.
    schema_msg = "timeout: connection reset after 429"
    transient_msg = "artifact schema looks invalid on the wire"
    prod_schema = R.decide(
        [R.TypedFailure(failure_class="schema-invalid", fingerprint="mutant-pair")],
        R.RetryPolicy(max_attempts=3, two_strikes_pivot=True),
    )
    prod_transient = R.decide(
        [R.TypedFailure(failure_class="severed-stream", fingerprint="mutant-pair")],
        R.RetryPolicy(max_attempts=3, two_strikes_pivot=True),
    )
    mut_schema = mutant_decide_from_text(schema_msg, 1, 3)
    mut_transient = mutant_decide_from_text(transient_msg, 1, 3)

    production_diverges = prod_schema.action != prod_transient.action
    mutant_collapses_or_inverts = mut_schema != "STOP" or mut_transient != "RETRY"
    # Production: schema-invalid STOP, severed-stream RETRY regardless of text.
    # Mutant: schema_msg contains timeout/reset/429 => RETRY; transient_msg
    # contains schema+invalid without timeout => STOP. Inverted.
    mutant_inverted = mut_schema == "RETRY" and mut_transient == "STOP"

    # Distinct fingerprints still reach catalog cap=3 (probe1's isolation,
    # re-checked here so a two-strikes-always-on mutant would fail).
    cap_ok = demo["distinct_reaches_catalog_cap"] is True
    pivot_ok = demo["pivot_at_strike_two"] is True
    no_third = demo["did_not_take_third_attempt"] is True
    zero_invalid = demo["schema_invalid_zero_retries"] is True
    required_fix = demo["same_fingerprint"]["required_fix"] == R.PIVOT_REQUIRED_FIX

    # Infinite-grind guard: a spoofed policy with max_attempts at the safety
    # cap still stops, never loops.
    grind_pol = R.RetryPolicy(
        max_attempts=R.SAFETY_MAX_ATTEMPTS,
        two_strikes_pivot=False,
        backoff_seconds=(1,),
    )
    grind = R.observe_attempts("timeout", grind_pol, distinct_fingerprints=True)
    grind_ok = (
        grind.observed_attempt_count <= R.SAFETY_MAX_ATTEMPTS
        and grind.terminal_action in {"STOP", "PIVOT"}
    )

    report = {
        "probe": "probe2-two-strikes-and-text-mutant",
        "unit_id": "IMP-0448",
        "demo": demo,
        "ast": ast_report,
        "production": {
            "schema_invalid": prod_schema.action,
            "severed_stream": prod_transient.action,
            "diverges": production_diverges,
        },
        "mutant": {
            "schema_invalid_msg_action": mut_schema,
            "severed_stream_msg_action": mut_transient,
            "inverted": mutant_inverted,
            "collapses_or_inverts": mutant_collapses_or_inverts,
        },
        "pivot_at_strike_two": pivot_ok,
        "no_third_attempt": no_third,
        "distinct_reaches_cap": cap_ok,
        "schema_invalid_zero_retries": zero_invalid,
        "required_fix_named": required_fix,
        "ast_clean": ast_report["clean"],
        "grind_ok": grind_ok,
        "grind_attempts": grind.observed_attempt_count,
        "pass": bool(
            pivot_ok
            and no_third
            and cap_ok
            and zero_invalid
            and required_fix
            and ast_report["clean"]
            and production_diverges
            and mutant_inverted
            and grind_ok
            and prod_schema.action == "STOP"
            and prod_transient.action == "RETRY"
        ),
    }
    print(json.dumps(report, indent=1, sort_keys=True, default=str))
    print(
        f"pivot_ok={pivot_ok} no_third={no_third} cap_ok={cap_ok} "
        f"ast_clean={ast_report['clean']} mutant_inverted={mutant_inverted} "
        f"required_fix={required_fix} grind_ok={grind_ok}"
    )
    if not report["pass"]:
        print("FAILED:IMP-0448-probe2 two-strikes / text-matching mutant")
        if ast_report["hits"]:
            print("ast hits", ast_report["hits"])
        return 1
    print(
        "SUCCESS:IMP-0448-probe2 pivot fires at strike two not three; "
        "text-matching mutant inverts; decide() has no message field"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
