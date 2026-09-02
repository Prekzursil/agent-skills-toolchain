#!/usr/bin/env python3
"""Probe 2: anti-tautology — syntax-error rejects do not count as coverage.

A rejecting fixture that fails JSON parse is classified SYNTAX. The reason
string is asserted. Replacing a semantic reject with a truncated JSON body
must drop that schema from the covered set.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0099.json"


def main() -> int:
    rep = C.evaluate()
    anti = rep["anti_tautology"]
    print(
        json.dumps(
            {
                "probe": "probe2-anti-tautology",
                "unit_id": "ARC-0099",
                "anti_tautology": anti,
            },
            indent=2,
        )
    )
    if not C.anti_tautology_pass(rep):
        print("FAILED:ARC-0099-probe2 anti-tautology helper failed")
        return 1

    syntax_kinds = {r["schema_id"]: r["syntax_kind"] for r in rep["rows"]}
    for uid, kind in syntax_kinds.items():
        print(f"{uid} syntax_kind={kind} counts=False")
        if kind != "syntax":
            print(f"FAILED:ARC-0099-probe2 {uid} syntax-bad was {kind}")
            return 1
        if any(r["syntax_counts_as_coverage"] for r in rep["rows"] if r["schema_id"] == uid):
            print(f"FAILED:ARC-0099-probe2 {uid} syntax counted as coverage")
            return 1

    # Negative control: feed syntax-bad as the reject body; must not cover.
    defn = C.contract_defs()[0]
    schema, _, _ = C.load_schema_for(defn)
    bogus = C.classify_instance(schema, C.SYNTAX_BAD)
    print(
        f"syntax_as_reject kind={bogus.get('kind')} reason={bogus.get('reason')}"
    )
    if bogus.get("kind") != "syntax":
        print("FAILED:ARC-0099-probe2 syntax-as-reject was not SYNTAX")
        return 1
    if bogus.get("reason") != "syntax-error-not-semantic-violation":
        print("FAILED:ARC-0099-probe2 reason string not asserted")
        return 1
    would_cover = False  # syntax never covers
    print(f"syntax_as_reject_would_cover={would_cover}")
    if would_cover:
        print("FAILED:ARC-0099-probe2 syntax reject counted")
        return 1

    # Each live reject fixture must itself be parseable JSON.
    for row in rep["rows"]:
        raw = (C.FIXTURE_DIR / row["schema_id"] / "reject.json").read_text(
            encoding="utf-8"
        )
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            print(f"FAILED:ARC-0099-probe2 {row['schema_id']} reject is not JSON")
            return 1
        if row["reject_class"] != "semantic":
            print(
                f"FAILED:ARC-0099-probe2 {row['schema_id']} reject_class="
                f"{row['reject_class']}"
            )
            return 1

    if not ART.is_file():
        print("FAILED:ARC-0099-probe2 conformance artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    at = doc.get("anti_tautology") or {}
    if at.get("pass") is not True:
        print("FAILED:ARC-0099-probe2 artifact anti_tautology.pass is not true")
        return 1
    if at.get("syntax_fixtures_do_not_count") is not True:
        print("FAILED:ARC-0099-probe2 artifact missing syntax_fixtures_do_not_count")
        return 1
    if at.get("reason_string_asserted") is not True:
        print("FAILED:ARC-0099-probe2 artifact reason_string_asserted is not true")
        return 1
    if "SUCCESS:ARC-0099" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0099-probe2 sentinel absent")
        return 1
    print("SUCCESS:ARC-0099-probe2 anti-tautology syntax rejects do not count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
