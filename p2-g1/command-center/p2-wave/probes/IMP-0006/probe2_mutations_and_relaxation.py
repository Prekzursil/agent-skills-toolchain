#!/usr/bin/env python3
"""Named probe 2 (IMP-0006): six mutations distinct + additionalProperties relaxation.

Both-states discipline: the six mutated manifests must each fail with their
DISTINCT expected error code on the strict schema (fires on bad state), and
the unknown-key case must go GREEN once additionalProperties is relaxed
(proving the case tests the rule it claims). The duplicate-key control rides
the module's object_pairs hook.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import manifest_schema as ms  # noqa: E402

UNIT = "IMP-0006"
RECEIPT = REPO / "command-center" / "receipts" / f"{UNIT}.json"


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        print(f"FAILED:{UNIT}-probe2 receipt missing")
        return 1
    receipt_text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(receipt_text)

    schema = ms.load_schema()
    live = ms.live_manifest_object()
    rows = ms.six_mutations(live, schema)
    if len(rows) != 6:
        print(f"FAILED:{UNIT}-probe2 expected six mutations, got {len(rows)}")
        return 1
    detail = []
    ok = True
    for r in rows:
        res = r["result"]
        js_codes = res["jsonschema"]["codes"]
        fast_codes = res["fastjsonschema"]["codes"]
        js_hit = r["expected"] in js_codes
        fast_hit = r["expected"] in fast_codes
        strict_green = res["ok"]
        detail.append(
            {
                "label": r["label"],
                "expected": r["expected"],
                "jsonschema_hit": js_hit,
                "independent_checker_hit": fast_hit,
                "strict_green_required": strict_green,
            }
        )
        if r["label"] == "duplicate-key":
            # must FAIL strict (duplicate detection forces ok False) and the
            # independent lane must catch it too
            if strict_green or not fast_hit:
                ok = False
        elif not (js_hit and fast_hit and not strict_green):
            ok = False
    relaxed = ms.relax_additional_properties(schema)
    unknown = dict(live)
    unknown["unexpected_top_level"] = True
    strict_unknown = ms.validate_instance(unknown, schema)
    relaxed_unknown = ms.validate_instance(unknown, relaxed)
    relax_row = {
        "unknown_key_strict_green": strict_unknown["ok"],
        "unknown_key_relaxed_green": relaxed_unknown["ok"],
        "proves_rule": (not strict_unknown["ok"]) and relaxed_unknown["ok"],
    }
    if not relax_row["proves_rule"]:
        ok = False
    neg = doc.get("negative_control") or {}
    print(
        json.dumps(
            {
                "unit_id": UNIT,
                "probe": "probe2-mutations-and-relaxation",
                "mutations": detail,
                "relaxation_control": relax_row,
                "receipt_negative_control_codes": neg.get("codes"),
                "receipt_fired_on_bad_state": neg.get("fired_on_bad_state"),
            },
            indent=1,
        )
    )
    if not ok:
        print(f"FAILED:{UNIT}-probe2 mutation or relaxation control failed")
        return 1
    print(f"SUCCESS:{UNIT}-probe2 six mutations distinct, relaxation control holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
