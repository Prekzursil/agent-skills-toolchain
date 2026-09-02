#!/usr/bin/env python3
"""Probe 2: six distinct mutation failures + additionalProperties mutation.

NEGATIVE CONTROL: missing name, bad semver, unknown top-level key, wrong type,
empty keywords, duplicate key — each fails with a distinct error.

MUTATION: relax additionalProperties; the unknown-key case goes green,
proving that case tests the rule it claims.

Reviewer gate: a manifest authored from the schema (not copied from
plugin.json) validates, including Phase-4 fields.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import manifest_schema as ms  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0006.json"
SENTINEL = "SUCCESS:IMP-0006"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0006-probe2 {msg}")
    return 1


def check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size < 200:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "sentinel absent"
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable:{exc}"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    return None


def main() -> int:
    err = check_receipt()
    if err:
        return fail(err)

    live = ms.live_manifest_object()
    schema = ms.load_schema()
    rows = ms.six_mutations(live, schema)
    codes = []
    summaries = []
    for row in rows:
        result = row["result"]
        expected = row["expected"]
        ok_fail = result["ok"] is False and result["libraries_agree"] is True
        in_js = expected in result["jsonschema"]["codes"]
        in_fj = expected in result["fastjsonschema"]["codes"]
        summaries.append(
            {
                "label": row["label"],
                "expected": expected,
                "fired": ok_fail and in_js and in_fj,
                "jsonschema_codes": result["jsonschema"]["codes"],
                "fastjsonschema_codes": result["fastjsonschema"]["codes"],
            }
        )
        if not (ok_fail and in_js and in_fj):
            return fail(f"mutation {row['label']} did not fire distinctly: {result}")
        codes.append(expected)
    if len(set(codes)) != 6:
        return fail(f"errors not distinct: {codes}")

    unknown = copy.deepcopy(live)
    unknown["unexpected_top_level"] = True
    strict = ms.validate_instance(unknown, schema)
    if strict["ok"] or ms.UNKNOWN_KEY not in strict["jsonschema"]["codes"]:
        return fail("unknown-key case did not fail under additionalProperties:false")
    relaxed = ms.relax_additional_properties(schema)
    green = ms.validate_instance(unknown, relaxed)
    if not green["ok"] or not green["libraries_agree"]:
        return fail(f"additionalProperties mutation did not go green: {green}")

    authored = ms.reviewer_authored_manifest()
    if authored == live or authored.get("name") == live.get("name"):
        return fail("reviewer manifest is not independent of live plugin.json")
    review = ms.validate_instance(authored, schema)
    if not review["ok"]:
        return fail(f"reviewer-authored manifest failed schema: {review}")

    extras = ms.control_plane_siblings()
    if extras:
        return fail(f"second manifest file: {extras}")

    payload = {
        "probe": "probe2-mutations-and-additionalproperties",
        "unit_id": "IMP-0006",
        "mutations": summaries,
        "distinct_error_count": len(set(codes)),
        "additionalproperties_mutation": {
            "unknown_key_strict_ok": strict["ok"],
            "unknown_key_relaxed_ok": green["ok"],
            "proves_rule": (not strict["ok"]) and green["ok"],
        },
        "reviewer_independent_manifest": {
            "name": authored["name"],
            "ok": review["ok"],
            "has_phase4_fields": bool(
                authored.get("min_client_version") and authored.get("supported_clients")
            ),
        },
        "second_manifest_files": extras,
        "ok": True,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    print("SUCCESS:IMP-0006-probe2 six distinct failures + additionalProperties mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
