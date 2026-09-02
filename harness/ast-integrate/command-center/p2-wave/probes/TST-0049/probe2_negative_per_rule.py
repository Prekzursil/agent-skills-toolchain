#!/usr/bin/env python3
"""Probe 2: one negative case per compatibility-matrix contract rule."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import suite as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0049.json"
SENTINEL = "SUCCESS:TST-0049"

EXPECTED = (
    ("blank-cell", "R-blank"),
    ("supported-without-evidence", "R-supported-evidence"),
    ("untested-as-pass", "R-untested-not-pass"),
    ("untested-missing-token", "R-untested-token"),
    ("inferred-as-supported", "R-inferred-distinct"),
    ("installer-exit-as-run", "R-installer-not-evidence"),
    ("unpinned-supported", "R-unpinned"),
    ("all-green-partial-estate", "R-partial-green"),
    ("failed-without-run-or-untested", "R-run-id-or-untested"),
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0049-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 400:
        return fail("receipt missing or tiny")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0049":
        return fail(f"unit_id {doc.get('unit_id')!r}")

    by_id = {fix["id"]: fix for fix in S.fixtures()}
    conforming = S.evaluate(by_id["conforming-mixed"]["matrix"])
    if not conforming["ok"]:
        print(json.dumps(conforming["violations"], indent=2)[:2000])
        return fail("conforming fixture not silent")

    fired = []
    for fid, rule in EXPECTED:
        got = S.evaluate(by_id[fid]["matrix"])
        if got["ok"]:
            return fail(f"{fid} stayed green")
        if rule not in got["rule_ids"]:
            return fail(f"{fid} missed {rule}; got {got['rule_ids']}")
        fired.append({"id": fid, "rule": rule, "rules": got["rule_ids"]})

    stored_neg = {
        n.get("id")
        for n in (doc.get("negative_controls") or [])
        if isinstance(n, dict)
    }
    missing_stored = [fid for fid, _rule in EXPECTED if fid not in stored_neg]
    if missing_stored:
        return fail(f"receipt missing negative_controls {missing_stored}")

    out = {
        "probe": "probe2-negative-per-rule",
        "unit_id": "TST-0049",
        "pass": True,
        "conforming_silent": True,
        "rules_fired": len(fired),
        "fired": fired,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"conforming_silent=true rules_fired={len(fired)}")
    print("SUCCESS:TST-0049-probe2 negative case per contract rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
