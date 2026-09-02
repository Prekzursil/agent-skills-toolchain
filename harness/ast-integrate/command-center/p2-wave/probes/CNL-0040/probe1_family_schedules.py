#!/usr/bin/env python3
"""Probe 1: enumerate JUDICIAL family, execute all 6 schedules, cite record ids."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402
import runtime as R  # noqa: E402
import controls as C  # noqa: E402
import reviewer as V  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0040-executable-runtime-semantics-for-the-6-judicial-protocols.md"
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0040-probe1 {msg}")
    return 1


def main() -> int:
    enum = F.enumerate_family()
    print(
        "catalog_n={0} fixture_n={1} ids={2} match={3} library_present={4}".format(
            enum["catalog"]["n"],
            enum["fixture"]["n"],
            ",".join(enum["ids"]),
            enum["match"],
            bool((enum["library"] or {}).get("present")),
        )
    )
    if not enum["match"]:
        return fail("family-enumeration-mismatch")
    if enum["catalog"]["n"] != F.EXPECTED_N:
        return fail("catalog-count")

    goods = C.all_good_executable()
    for pid, row in goods["rows"].items():
        print(
            "schedule {0} ok={1} admitted={2} excluded={3} verdict={4}".format(
                pid, row["ok"], row["admitted"], row["excluded"], row["verdict"]
            )
        )
        if not row["ok"]:
            return fail(f"good-run-{pid}")
        if row["record_id"] != pid:
            return fail(f"record-id-{pid}")
    if goods["n"] != F.EXPECTED_N:
        return fail("good-run-count")

    for pid, spec in R.PROTOCOLS.items():
        sched = spec.get("turn_schedule") or []
        if spec.get("executable"):
            if len(sched) < 3:
                return fail(f"thin-schedule-{pid}")
        elif not spec.get("missing_element"):
            return fail(f"not-executable-missing-element-{pid}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact-unparseable:{exc}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if "SUCCESS:CNL-0040" not in text:
        return fail("sentinel-absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)

    art_ids = [p.get("record_id") for p in (doc.get("protocols") or [])]
    if art_ids != enum["ids"]:
        return fail(f"artifact-ids {art_ids}")
    for p in doc.get("protocols") or []:
        rid = p.get("record_id")
        verdict = str(p.get("verdict") or "")
        if rid not in verdict and rid not in json.dumps(p, sort_keys=True):
            return fail(f"verdict-missing-record-id-{rid}")
        if p.get("executable") is True:
            if not (p.get("turn_schedule") or []):
                return fail(f"artifact-schedule-{rid}")
        else:
            if not p.get("missing_element"):
                return fail(f"artifact-not-executable-{rid}")

    tab = V.retabulate(doc)
    print(
        "reviewer verdict={0} disagreement={1} numbers={2}".format(
            tab["verdict"], tab["disagreement"], tab["numbers"]
        )
    )
    if tab["disagreement"]:
        return fail("reviewer-number-disagreement")

    covered = sorted(art_ids)
    counted = F.EXPECTED_N
    print(f"mechanical_count executable_or_named={len(covered)} family_n={counted}")
    if len(covered) != counted:
        return fail("coverage-vs-family-count")

    print("SUCCESS:CNL-0040-probe1 family-enumeration schedules record-ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
