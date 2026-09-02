#!/usr/bin/env python3
"""Probe 1: compiler-branch table. Every enum value routes; no silent default.

Signal 1 is compiler.py dict lookup (KeyError path / missing-key reject).
Does not consult jsonschema.
"""
from __future__ import annotations

import inspect
import json
import sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compiler as C  # noqa: E402

RAW = HERE / "probe1-branch-table.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0003-probe1 {msg}")
    return 1


def main() -> int:
    src = inspect.getsource(C.select)
    if ".get(" in src:
        return fail("select() contains .get( — silent-default risk")

    table = C.cartesian_protocol_ids()
    expected = (
        len(C.RISK_FAMILY) * len(C.OUTPUT_FAMILY) * len(C.INTENT_FAMILY)
    )
    if len(table) != expected:
        return fail(f"cartesian_size={len(table)} want={expected}")

    routed: dict[str, set[str]] = {f: set() for f in C.ENUM_FIELDS}
    rows = []
    for risk, output, intent in product(
        C.RISK_FAMILY, C.OUTPUT_FAMILY, C.INTENT_FAMILY
    ):
        charter = C.good_charter(
            risk_tier=risk, desired_output=output, consensus_intent=intent
        )
        result = C.select(charter)
        if not result.ok or not result.protocol_id:
            return fail(f"enum-combo-rejected {risk}/{output}/{intent} {result.reason}")
        want = table[(risk, output, intent)]
        if result.protocol_id != want:
            return fail(f"protocol mismatch {result.protocol_id} != {want}")
        routed["risk_tier"].add(risk)
        routed["desired_output"].add(output)
        routed["consensus_intent"].add(intent)
        rows.append(
            {
                "risk_tier": risk,
                "desired_output": output,
                "consensus_intent": intent,
                "protocol_id": result.protocol_id,
            }
        )

    for field, values in C.ENUM_FIELDS.items():
        if routed[field] != set(values):
            return fail(f"unrouted {field}: {set(values) - routed[field]}")

    # Prose fields are not branch keys: objective/criteria do not change protocol_id.
    a = C.select(C.good_charter(objective="Merge the pull request after review."))
    b = C.select(C.good_charter(objective="Rewrite the kernel scheduler."))
    if not a.ok or not b.ok or a.protocol_id != b.protocol_id:
        return fail("objective changed protocol_id")
    with_sc = C.select(C.good_charter())
    without_sc = C.select(C.good_charter(success_criteria=""))
    if not with_sc.ok or not without_sc.ok:
        return fail("success_criteria presence flipped ok")
    if with_sc.protocol_id != without_sc.protocol_id:
        return fail("success_criteria changed protocol_id")
    if C.ABSENT_CRITERIA_TOKEN not in without_sc.fallbacks:
        return fail("absent success_criteria missing fallback token")
    if C.ABSENT_CRITERIA_TOKEN in with_sc.fallbacks:
        return fail("present success_criteria still claimed absent")

    # Unknown / missing enum: COMPILE_REJECT, never a protocol.
    unknown = C.select(C.good_charter(risk_tier="urgent-ish"))
    if unknown.ok or unknown.protocol_id is not None:
        return fail("unknown enum silent-defaulted")
    if unknown.reason != "unknown_enum:risk_tier:urgent-ish":
        return fail(f"unknown reason={unknown.reason}")
    missing = C.select(C.good_charter(desired_output=""))
    if missing.ok or missing.reason != "missing_enum:desired_output":
        return fail(f"missing enum reason={missing.reason}")
    empty_obj = C.select(C.good_charter(objective=""))
    if empty_obj.ok or empty_obj.reason != "objective_required":
        return fail(f"empty objective reason={empty_obj.reason}")

    # Losing option DOES silent-default — proving the check is not vacuous.
    lose = C.losing_select(C.good_charter(risk_tier="urgent-ish"))
    if not lose.ok or lose.protocol_id is None:
        return fail("losing option did not silent-default (control vacuous)")

    RAW.write_text(
        json.dumps(
            {
                "cartesian": expected,
                "routed_values": {k: sorted(v) for k, v in routed.items()},
                "unknown_reason": unknown.reason,
                "missing_reason": missing.reason,
                "losing_protocol_id": lose.protocol_id,
                "sample_rows": rows[:3],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"cartesian={expected} routed_risk={len(routed['risk_tier'])} "
        f"routed_output={len(routed['desired_output'])} "
        f"routed_intent={len(routed['consensus_intent'])} "
        f"unknown_reject={unknown.reason} "
        f"losing_silent_default={lose.protocol_id}"
    )
    print("SUCCESS:CNL-0003-probe1 compiler-branch table every enum routes; no silent default")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
