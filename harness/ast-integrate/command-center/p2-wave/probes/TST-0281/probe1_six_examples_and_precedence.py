#!/usr/bin/env python3
"""Probe 1: six spec examples parse, evaluate, and publish ASTs; precedence."""

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
    ast_to_dict,
    evaluate_source,
    parse,
    run_fixture,
    validate_spec,
)
from council.stopping.spec_examples import SPEC_EXAMPLES  # noqa: E402


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:TST-0281-probe1 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    if len(SPEC_EXAMPLES) != 6:
        return fail(f"need six spec examples, got {len(SPEC_EXAMPLES)}")

    examples: list[dict] = []
    for ex in SPEC_EXAMPLES:
        source = str(ex["source"])
        producers = list(ex["producers"])  # type: ignore[arg-type]
        node = validate_spec(source, producers=producers)
        ast = ast_to_dict(node)
        fire = evaluate_source(source, ex["fire"])  # type: ignore[arg-type]
        silent = evaluate_source(source, ex["silent"])  # type: ignore[arg-type]
        unknown = evaluate_source(source, ex["not_checked"])  # type: ignore[arg-type]
        fixture = run_fixture(
            source,
            [ex["silent"], ex["fire"]],  # type: ignore[list-item]
            producers=producers,
        )
        row = {
            "id": ex["id"],
            "spec_line": ex["spec_line"],
            "cnl": ex["cnl"],
            "source": source,
            "ast": ast,
            "fire": fire.as_dict(),
            "silent": silent.as_dict(),
            "not_checked": unknown.as_dict(),
            "fixture_stop_round": fixture["stop_round"],
        }
        examples.append(row)
        if fire.stop is not True or fire.value is not True:
            return fail(f"{ex['id']} fire fixture did not stop", row)
        if silent.stop is not False or silent.value is not False:
            return fail(f"{ex['id']} silent fixture stopped", row)
        if unknown.stop is not False:
            return fail(f"{ex['id']} NOT-CHECKED stopped", row)
        if fixture["stop_round"] != 2:
            return fail(f"{ex['id']} fixture did not stop on round 2", fixture)
        print(
            f"{ex['id']} line={ex['spec_line']} source={source!r} "
            f"fire_stop={fire.stop} silent_stop={silent.stop} "
            f"not_checked={unknown.value}"
        )

    # Extra timer arms must also fire when the catalog names a disjunction.
    e3 = next(x for x in SPEC_EXAMPLES if x["id"] == "E3")
    timer = evaluate_source(str(e3["source"]), e3["fire_timer_arm"])  # type: ignore[arg-type]
    if timer.stop is not True:
        return fail("E3 timer arm did not fire")
    e5 = next(x for x in SPEC_EXAMPLES if x["id"] == "E5")
    timer5 = evaluate_source(str(e5["source"]), e5["fire_timer_arm"])  # type: ignore[arg-type]
    if timer5.stop is not True:
        return fail("E5 timer arm did not fire")

    precedence = [
        {
            "source": "NOT false AND false",
            "expected": False,
            "got": evaluate_source("NOT false AND false").value,
            "meaning": "(NOT false) AND false",
        },
        {
            "source": "NOT (false AND false)",
            "expected": True,
            "got": evaluate_source("NOT (false AND false)").value,
            "meaning": "NOT of a false conjunction",
        },
        {
            "source": "true OR false AND false",
            "expected": True,
            "got": evaluate_source("true OR false AND false").value,
            "meaning": "true OR (false AND false)",
        },
        {
            "source": "(true OR false) AND false",
            "expected": False,
            "got": evaluate_source("(true OR false) AND false").value,
            "meaning": "parentheses override AND/OR",
        },
        {
            "source": "NOT unique_ideas >= 100",
            "expected": False,
            "got": evaluate_source(
                "NOT unique_ideas >= 100",
                {"unique_ideas": {"status": "CHECKED", "value": 100}},
            ).value,
            "meaning": "NOT binds a comparison, not the identifier",
        },
    ]
    for row in precedence:
        if row["got"] != row["expected"]:
            return fail("precedence", row)

    # Unsuccessful search must not satisfy proof_of_impossibility.
    e6 = next(x for x in SPEC_EXAMPLES if x["id"] == "E6")
    search = evaluate_source(
        str(e6["source"]), e6["unsuccessful_search"]  # type: ignore[arg-type]
    )
    if search.stop:
        return fail("unsuccessful search fired proof_of_impossibility")

    payload = {
        "ok": True,
        "probe": "probe1-six-examples-and-precedence",
        "unit_id": "TST-0281",
        "examples": examples,
        "precedence": precedence,
        "timer_arms": {"E3": timer.as_dict(), "E5": timer5.as_dict()},
        "unsuccessful_search_stop": search.stop,
        "ast_count": len(examples),
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print(
        f"examples={len(examples)} asts_published={len(examples)} "
        f"precedence={len(precedence)}"
    )
    print("SUCCESS:TST-0281-probe1 six spec examples parsed, evaluated, ASTs published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
