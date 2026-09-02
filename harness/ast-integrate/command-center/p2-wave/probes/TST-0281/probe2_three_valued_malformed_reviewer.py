#!/usr/bin/env python3
"""Probe 2: independent reviewer — Kleene NOT-CHECKED, malformed-at-validate,
both-states, short-circuit vs full eval.

Does not import probe 1. Starts from the production evaluator and the six
spec strings. Reproduces the both-states control before signing off.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from council.stopping.expr import (  # noqa: E402
    NOT_CHECKED,
    SpecValidationError,
    evaluate_source,
    run_fixture,
    validate_spec,
)
from council.stopping.spec_examples import SPEC_EXAMPLES  # noqa: E402


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:TST-0281-probe2 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def coerce_unknown_to_false(value: object) -> bool:
    """Illegal coercion the honest evaluator must not perform."""
    if value == NOT_CHECKED:
        return False
    return bool(value)


def main() -> int:
    # Both-states on every spec example: fire vs silent.
    both_states = []
    for ex in SPEC_EXAMPLES:
        source = str(ex["source"])
        fire = evaluate_source(source, ex["fire"])  # type: ignore[arg-type]
        silent = evaluate_source(source, ex["silent"])  # type: ignore[arg-type]
        unknown = evaluate_source(source, ex["not_checked"])  # type: ignore[arg-type]
        both_states.append(
            {
                "id": ex["id"],
                "source": source,
                "fire_stop": fire.stop,
                "silent_stop": silent.stop,
                "not_checked_value": unknown.value,
                "not_checked_stop": unknown.stop,
            }
        )
        if not fire.stop:
            return fail(f"{ex['id']} fire state silent")
        if silent.stop:
            return fail(f"{ex['id']} silent state fired")
        if unknown.stop:
            return fail(f"{ex['id']} NOT-CHECKED fired a stop")
        if unknown.value != NOT_CHECKED and unknown.value is not False:
            # OR with a determined false-and-unknown arm may be NOT-CHECKED;
            # AND with a false arm may be false without coercion of the unknown.
            pass

    # The ignorance-stop: NOT of an unchecked metric must not become true.
    not_src = "NOT (completeness_score >= 0.90)"
    honest = evaluate_source(
        not_src, {"completeness_score": {"status": "NOT-CHECKED"}}
    )
    mutant_stop = not coerce_unknown_to_false(honest.value)
    if honest.value != NOT_CHECKED:
        return fail("NOT of NOT-CHECKED was not Kleene unknown", honest.as_dict())
    if honest.stop:
        return fail("NOT of NOT-CHECKED stopped")
    if not mutant_stop:
        return fail("mutant control did not show the ignorance-stop")

    # AND unknown,true must stay unknown (coercion to false would yield false,
    # which happens to also not-stop, so the NOT case above is the discriminator).
    and_u = evaluate_source(
        "unique_ideas >= 100 AND completeness_score >= 0.90",
        {
            "unique_ideas": {"status": "CHECKED", "value": 100},
            "completeness_score": {"status": "NOT-CHECKED"},
        },
    )
    if and_u.value != NOT_CHECKED or and_u.stop:
        return fail("AND with NOT-CHECKED coerced", and_u.as_dict())

    # Malformed rejected at spec-validation, never at round 12.
    malformed = [
        "unique_ideas >= AND 100",
        "AND unique_ideas >= 100",
        "((unique_ideas >= 100)",
        "unique_ideas >= 100 AND AND completeness_score >= 0.90",
    ]
    dummy = [{"unique_ideas": {"status": "CHECKED", "value": 100}}] * 12
    malformed_rows = []
    for src in malformed:
        try:
            run_fixture(src, dummy, producers=["unique_ideas", "completeness_score"])
            return fail(f"malformed reached rounds: {src!r}")
        except SpecValidationError as exc:
            if exc.phase != "spec-validation":
                return fail(f"wrong phase {exc.phase} for {src!r}")
            malformed_rows.append(
                {"source": src, "phase": exc.phase, "error": str(exc)}
            )

    # Short-circuit vs full evaluation of side-effecting terms.
    observed: list[str] = []

    def note(name: str) -> None:
        observed.append(name)

    and_sc = evaluate_source(
        "left == true AND right == true",
        {
            "left": {"status": "CHECKED", "value": False, "observe": note},
            "right": {"status": "CHECKED", "value": True, "observe": note},
        },
    )
    if "right" in and_sc.observed:
        return fail("pure AND did not short-circuit", and_sc.as_dict())
    try:
        validate_spec(
            "left == true AND right == true",
            bindings={
                "left": {"status": "CHECKED", "value": False, "impure": True},
                "right": {"status": "CHECKED", "value": True, "impure": True},
            },
        )
        return fail("impure expression accepted at spec-validation")
    except SpecValidationError as exc:
        impure_phase = exc.phase
    observed.clear()
    full = evaluate_source(
        "left == true AND right == true",
        {
            "left": {
                "status": "CHECKED",
                "value": False,
                "impure": True,
                "observe": note,
            },
            "right": {
                "status": "CHECKED",
                "value": True,
                "impure": True,
                "observe": note,
            },
        },
        force_full=True,
    )
    if set(full.observed) != {"left", "right"}:
        return fail("forced full eval did not observe both arms", full.as_dict())
    if full.short_circuited:
        return fail("forced full eval still short-circuited")

    payload = {
        "ok": True,
        "probe": "probe2-three-valued-malformed-reviewer",
        "unit_id": "TST-0281",
        "independent": True,
        "starts_from_tests": True,
        "both_states": both_states,
        "not_checked_not_coerced": True,
        "ignorance_not_stop": {
            "source": not_src,
            "honest_value": honest.value,
            "honest_stop": honest.stop,
            "mutant_would_stop": mutant_stop,
        },
        "malformed_at_spec_validation": malformed_rows,
        "impure_rejected_phase": impure_phase,
        "short_circuit_skipped_right": "right" not in and_sc.observed,
        "full_eval_observed": full.observed,
        "reviewer_id": "TST-0281-probe2-three-valued-malformed-reviewer",
        "verdict": "PASS",
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print(
        f"both_states={len(both_states)} malformed={len(malformed_rows)} "
        f"mutant_would_stop={mutant_stop} honest_stop={honest.stop}"
    )
    print(
        "SUCCESS:TST-0281-probe2 independent reviewer reproduced both-states "
        "and NOT-CHECKED control"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
