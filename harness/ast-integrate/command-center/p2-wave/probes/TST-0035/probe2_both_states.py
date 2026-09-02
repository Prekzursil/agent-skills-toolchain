#!/usr/bin/env python3
"""Probe 2: both-states control and one negative per contract rule.

Conforming Python and Node fixtures must PASS. Each of name, version,
entry_points, engines, files has a deliberately non-conforming input that
FAILS the gate. Independent of probe 1's live sdist table.
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

from plugin.package_metadata_contract import RULES, run_conformance_suite  # noqa: E402

ART = REPO / "command-center/receipts/TST-0035.json"
SENTINEL = "SUCCESS:TST-0035"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0035-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0035":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    suite = run_conformance_suite()
    if not suite["conforming_pass"]:
        return fail(f"conforming fixture failed {suite['cases'][:2]}")
    if not suite["both_states"]:
        return fail("both-states control failed")
    for field in RULES:
        info = suite["per_rule"][field]
        if not info["ok"]:
            return fail(f"no negative for {field}")
    negatives = [c for c in suite["cases"] if c["state"] == "nonconforming"]
    if len(negatives) < len(RULES):
        return fail(f"negatives={len(negatives)}")
    for case in negatives:
        if case["gate_pass"] or not case["target_field_inconsistent"]:
            return fail(f"negative leaked {case['id']} {case}")

    stored_ok = doc.get("suite", {}).get("suite_ok")
    if stored_ok is not True:
        return fail(f"receipt suite_ok={stored_ok}")

    print(
        json.dumps(
            {
                "probe": "probe2-both-states",
                "unit_id": "TST-0035",
                "suite_ok": suite["suite_ok"],
                "both_states": suite["both_states"],
                "conforming_pass": suite["conforming_pass"],
                "per_rule": suite["per_rule"],
                "negative_ids": [c["id"] for c in negatives],
            },
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:TST-0035-probe2 both-states negatives={len(negatives)} "
        f"rules={list(RULES)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
