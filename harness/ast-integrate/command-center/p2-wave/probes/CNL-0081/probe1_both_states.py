#!/usr/bin/env python3
"""Named probe 1: A10 parse unchanged + both-states FIRE/SILENT + schema check."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from a10_grammar import (  # noqa: E402
    SPEC_SIX,
    THIS_EXPRESSION,
    ParseError,
    accepted_unchanged,
    parse,
)
from evaluate import decide  # noqa: E402
from fixtures import (  # noqa: E402
    fire_state,
    silent_quality_fail_state,
    silent_unresolved_state,
)
from jsonschema import Draft7Validator  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0081-executable-stopping-example-quality-gate-pass-and-unresolv.schema.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0081-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNL-0081":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:CNL-0081" not in text:
        return fail("sentinel absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("expression_verbatim") != THIS_EXPRESSION:
        return fail("expression_verbatim mismatch")

    node = accepted_unchanged(THIS_EXPRESSION)
    if node.source_text != THIS_EXPRESSION:
        return fail("parser rewrote expression")
    if node.kind != "AND" or node.op != "AND":
        return fail(f"root {node.kind}/{node.op} want AND")

    for expr in SPEC_SIX:
        parsed = parse(expr)
        if parsed.source_text != expr:
            return fail(f"six-example rewrite {expr!r}")

    try:
        parse("quality_gate == PASS AND AND 0")
        return fail("malformed expression was accepted")
    except ParseError:
        pass

    fire = decide(fire_state())
    silent = decide(silent_unresolved_state())
    qfail = decide(silent_quality_fail_state())
    if fire["decision"] != "FIRE":
        return fail(f"FIRE fixture -> {fire['decision']}")
    if silent["decision"] != "SILENT":
        return fail(f"SILENT-unresolved -> {silent['decision']}")
    if qfail["decision"] != "SILENT":
        return fail(f"SILENT-quality-fail -> {qfail['decision']}")
    if fire["decision"] == silent["decision"]:
        return fail("detector silent in both states")

    Draft7Validator.check_schema(doc)
    validator = Draft7Validator(doc)
    errors = sorted(validator.iter_errors(fire_state()), key=lambda e: list(e.path))
    if errors:
        return fail(f"FIRE fixture schema errors {errors[0].message}")

    print(
        json.dumps(
            {
                "parse_unchanged": True,
                "root": node.kind,
                "six_accepted": len(SPEC_SIX),
                "malformed_rejected": True,
                "FIRE": fire,
                "SILENT_unresolved": silent,
                "SILENT_quality_fail": qfail,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    print(
        "FIRE=FIRE SILENT-unresolved=SILENT SILENT-quality-fail=SILENT "
        "parse=unchanged"
    )
    print("SUCCESS:CNL-0081-probe1 both-states and A10 parse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
