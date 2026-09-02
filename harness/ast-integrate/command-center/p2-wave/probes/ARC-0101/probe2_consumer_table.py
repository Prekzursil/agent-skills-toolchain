#!/usr/bin/env python3
"""Probe 2: duplicate-key and case-variant behaviour is measured per consumer.

Never assumed. A live consumer that preserved both Name and name must not be
recorded as case-insensitive. The seeded casefold hook MUST collapse. The
strict duplicate hook MUST error. Dropping assumed=false from a live row
must make the checker fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import jsonschema  # noqa: E402
import report as R  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0101.json"
SCHEMA = REPO / "command-center/schema/conformance-report.schema.json"
ALLOWED_DUP = frozenset({"last-wins", "first-wins", "error", "unexpected-value"})
ALLOWED_CASE = frozenset(
    {"both-preserved", "casefold-collapse", "dropped-one", "error"}
)


def check_table(rows: list[dict], *, require_assumed_false: bool = True) -> tuple[bool, str]:
    if not isinstance(rows, list) or len(rows) < 4:
        return False, "consumer-table-short"
    live = [r for r in rows if r.get("role") == "live-consumer" and r.get("available")]
    if len(live) < 2:
        return False, f"live-consumers-few:{len(live)}"
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            return False, f"row[{i}]-not-object"
        if require_assumed_false and row.get("assumed") is not False:
            return False, f"row[{i}]-assumed-not-false"
        dup = row.get("duplicate_key") or {}
        case = row.get("case_variant") or {}
        if require_assumed_false and dup.get("assumed") is not False:
            return False, f"row[{i}]-dup-assumed"
        if require_assumed_false and case.get("assumed") is not False:
            return False, f"row[{i}]-case-assumed"
        if dup.get("behaviour") not in ALLOWED_DUP:
            return False, f"row[{i}]-bad-dup:{dup.get('behaviour')}"
        if case.get("behaviour") not in ALLOWED_CASE:
            return False, f"row[{i}]-bad-case:{case.get('behaviour')}"
    seeded = [r for r in rows if r.get("role") == "seeded-failure-class-control"]
    if not seeded or seeded[0].get("case_variant", {}).get("behaviour") != "casefold-collapse":
        return False, "seeded-casefold-did-not-collapse"
    strict = [r for r in rows if r.get("role") == "strict-duplicate-control"]
    if not strict or strict[0].get("duplicate_key", {}).get("behaviour") != "error":
        return False, "strict-duplicate-did-not-error"
    live_dups = {r["duplicate_key"]["behaviour"] for r in live}
    if "last-wins" not in live_dups:
        return False, f"live-duplicate-behaviours:{sorted(live_dups)}"
    live_case = {r["case_variant"]["behaviour"] for r in live}
    if "both-preserved" not in live_case:
        return False, f"live-case-behaviours:{sorted(live_case)}"
    return True, f"live={len(live)} dup={sorted(live_dups)} case={sorted(live_case)}"


def main() -> int:
    live = R.measured()
    table = live["consumers"]
    ok, why = check_table(table)
    print(f"live_table_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0101-probe2 live consumer table failed")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0101-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0101-probe2 self-declared {doc.get('state')}")
        return 1
    aok, awhy = check_table(doc.get("consumers") or [])
    print(f"artifact_table_ok={aok} {awhy}")
    if not aok:
        print("FAILED:ARC-0101-probe2 artifact consumer table failed")
        return 1
    art_fp = doc.get("fingerprint") or {}
    live_fp = live["fingerprint"]
    for key in (
        "live_duplicate_behaviours",
        "live_case_behaviours",
        "any_live_consumer_case_insensitive",
        "seeded_casefold_collapses",
        "strict_duplicate_errors",
    ):
        if art_fp.get(key) != live_fp.get(key):
            print(f"FAILED:ARC-0101-probe2 fingerprint mismatch {key}")
            return 1
    claimed_ci = (doc.get("answers") or {}).get("any_live_consumer_case_insensitive")
    if claimed_ci != live_fp.get("any_live_consumer_case_insensitive"):
        print("FAILED:ARC-0101-probe2 case-insensitive answer does not match live table")
        return 1
    if claimed_ci is True and not live_fp.get("any_live_consumer_case_insensitive"):
        print("FAILED:ARC-0101-probe2 overclaim: case-insensitive while live parsers preserved both keys")
        return 1
    if (doc.get("answers") or {}).get("duplicate_key_measured_not_assumed") is not True:
        print("FAILED:ARC-0101-probe2 duplicate-key behaviour was not marked measured")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant.get("consumers") or []:
        if row.get("role") == "live-consumer":
            row.pop("assumed", None)
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0101-probe2 no live assumed flag to strip")
        return 1
    mok, mwhy = check_table(mutant.get("consumers") or [], require_assumed_false=True)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0101-probe2 mutant without assumed=false was accepted")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    art_errors = list(validator.iter_errors(doc))
    empty_errors = list(validator.iter_errors({}))
    print(f"schema artifact_errors={len(art_errors)} empty_errors={len(empty_errors)}")
    if art_errors:
        print(f"FAILED:ARC-0101-probe2 artifact fails output schema: {art_errors[0].message}")
        return 1
    if not empty_errors:
        print("FAILED:ARC-0101-probe2 output schema accepts empty object (vacuous)")
        return 1
    if "SUCCESS:ARC-0101" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0101-probe2 sentinel absent")
        return 1
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:ARC-0101-probe2 reviewer is not independent")
        return 1
    print("SUCCESS:ARC-0101-probe2 consumer table measured not assumed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
