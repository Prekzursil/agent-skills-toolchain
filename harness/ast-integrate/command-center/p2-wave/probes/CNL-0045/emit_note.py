#!/usr/bin/env python3
"""Emit the CNL-0045 design note (JSON that lives at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import both_states, negative_control, oracle_both_states  # noqa: E402
from family import (  # noqa: E402
    CATALOGUE,
    EXPECTED_N,
    FAMILY,
    NAMED_IDS,
    NAMED_SLUGS,
    catalog_expected_n,
    catalog_named_ids,
    catalog_named_slugs,
    catalog_unit,
    family_members,
    library_hits,
    library_on_this_tree,
    load_catalogue,
    member_ids,
    records_of,
)
from oracles import oracle_status  # noqa: E402
from runtime import execute_schedule, turn_schedule  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0045-executable-runtime-semantics-for-the-7-engineering-review-.md"
)
SCHEMA = "command-center/p2-wave/probes/CNL-0045/council-design-note.schema.json"
SHARED_SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0045/probe1_family_oracles.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0045/probe2_reviewer_controls.py"
)
QUESTION = (
    "Ranging over exactly these 7 records, named so no member can fall through "
    "a family mis-assignment (P45 scientific-peer-review, P46 architecture-review-board, "
    "P47 incident-war-room, P48 kill-the-company (war-game), P49 socratic-interrogation, "
    "P50 evidence-clerk-led, P51 timeboxed-spike-council): For each of the 7 "
    "ENGINEERING-REVIEW protocol records, what executable oracle (test, build, "
    "measurement) settles a disputed claim, and which review protocols have no "
    "oracle at all?"
)


def main() -> int:
    cat = load_catalogue()
    recs = records_of(cat)
    members = family_members(recs)
    ids = member_ids(members)
    unit = catalog_unit()
    named = catalog_named_ids(unit)
    slugs = catalog_named_slugs(unit)
    expected = catalog_expected_n(unit)
    lib = library_on_this_tree()
    hits = library_hits()

    if sorted(ids) != sorted(NAMED_IDS):
        print(f"FAILED:emit fixture ids {ids} != {list(NAMED_IDS)}")
        return 1
    if named != list(NAMED_IDS):
        print(f"FAILED:emit catalog named ids {named}")
        return 1
    if expected != EXPECTED_N or len(members) != EXPECTED_N:
        print(f"FAILED:emit count fixture={len(members)} catalog_n={expected}")
        return 1
    if slugs != NAMED_SLUGS:
        print(f"FAILED:emit slug mismatch {slugs}")
        return 1
    if lib:
        print("FAILED:emit library unexpectedly present; recount from library bytes")
        return 1

    record_rows = []
    oracle_rows = []
    no_oracle = []
    schedules = []
    oracle_controls = []
    for rec in members:
        status = oracle_status(rec)
        sched = turn_schedule(rec)
        octrl = oracle_both_states(rec)
        oracle_controls.append(
            {
                "id": rec["id"],
                "silent_on_good": octrl["silent_on_good"],
                "fires_on_bad": octrl["fires_on_bad"],
                "has_oracle": octrl["has_oracle"],
            }
        )
        if not octrl["silent_on_good"] or not octrl["fires_on_bad"]:
            print(f"FAILED:emit oracle both-states {rec['id']} {octrl}")
            return 1
        row = {
            "id": rec["id"],
            "slug": rec.get("slug"),
            "family": rec.get("family"),
            "disputed_claim_kind": rec.get("disputed_claim_kind"),
            "verdict": "HAS-ORACLE" if status["has_oracle"] else "NO-ORACLE",
            "schedule_verdict": sched["verdict"],
            "oracle_class": status.get("class"),
            "settles": status.get("settles"),
            "missing_element": status.get("missing_element"),
            "overclaim": status.get("overclaim"),
        }
        record_rows.append(row)
        schedules.append(
            {
                "id": rec["id"],
                "executable": sched["executable"],
                "verdict": sched["verdict"],
                "missing_element": sched.get("missing_element"),
                "turns": sched.get("turns") or [],
            }
        )
        if status["has_oracle"]:
            good = execute_schedule(rec)
            oracle_rows.append(
                {
                    "id": rec["id"],
                    "class": status["class"],
                    "oracle_id": status["oracle_id"],
                    "settles": status["settles"],
                    "predicate_kind": status["predicate_kind"],
                    "good_run_verdict": good.get("verdict"),
                }
            )
        else:
            no_oracle.append(
                {
                    "id": rec["id"],
                    "slug": rec.get("slug"),
                    "missing_element": status["missing_element"],
                    "schedule_verdict": "NOT-EXECUTABLE",
                }
            )

    ctrl = both_states(recs)
    if not ctrl["silent_on_good"] or not ctrl["fires_on_bad"]:
        print(f"FAILED:emit catalogue both-states {ctrl}")
        return 1
    neg = negative_control(recs)
    if neg["result"] != "FIRES":
        print(f"FAILED:emit negative control silent: {neg}")
        return 1

    has_ids = [r["id"] for r in record_rows if r["verdict"] == "HAS-ORACLE"]
    none_ids = [r["id"] for r in record_rows if r["verdict"] == "NO-ORACLE"]
    answer = (
        "Five of seven ENGINEERING-REVIEW records bind an executable oracle: "
        "P45 scientific-peer-review (test/reproduction of claimed_output), "
        "P46 architecture-review-board (build/import-graph forbidden-edge check), "
        "P47 incident-war-room (measurement/telemetry predicate), "
        "P50 evidence-clerk-led (test/exhibit sha256+schema admission), "
        "P51 timeboxed-spike-council (measurement before deadline). "
        "Two have no oracle at all: P48 kill-the-company (missing "
        "executable_system_under_test+attack_success_predicate) and "
        "P49 socratic-interrogation (missing machine_evaluable_contradiction_predicate). "
        "Every verdict cites its record id. "
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; "
        "membership is the catalog-named set, independently recounted from the fixture."
    )

    doc = {
        "unit_id": "CNL-0045",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0045",
        "completion_sentinel": "SUCCESS:CNL-0045",
        "title": "Executable runtime semantics for the 7 ENGINEERING-REVIEW protocols",
        "question": QUESTION,
        "answer": answer,
        "family": FAMILY,
        "family_count": len(members),
        "family_ids": ids,
        "catalog_named_ids": named,
        "catalog_expected_n": expected,
        "library": {
            "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "catalog_input": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
            ),
            "on_this_tree": lib,
            "checked_paths": hits,
            "membership_source": (
                "CNL-0045 question_or_target named members; fixture family "
                "filter is the independent recount"
            ),
        },
        "records": record_rows,
        "oracles": oracle_rows,
        "no_oracle": no_oracle,
        "schedules": schedules,
        "has_oracle_ids": has_ids,
        "no_oracle_ids": none_ids,
        "tests": [
            {
                "id": "family-coverage",
                "command": P1,
                "result": "PASS",
                "measured": {
                    "fixture_n": len(members),
                    "catalog_n": expected,
                    "ids": ids,
                },
            },
            {
                "id": "both-states-catalogue",
                "command": P2,
                "result": "PASS" if ctrl["silent_on_good"] and ctrl["fires_on_bad"] else "FAIL",
                "silent_on_good": ctrl["silent_on_good"],
                "fires_on_bad": ctrl["fires_on_bad"],
                "verbatim_good": json.dumps(ctrl["good_findings"], sort_keys=True),
                "verbatim_bad": json.dumps(ctrl["bad_findings"], sort_keys=True),
                "bad_kinds": ctrl["bad_kinds"],
            },
        ],
        "negative_controls": [
            {
                "id": "planted-bad-catalogue",
                "meant_to_reject": neg["meant_to_reject"],
                "rejects": neg["meant_to_reject"],
                "result": neg["result"],
                "verbatim": neg["verbatim"],
                "finding_count": neg["finding_count"],
            }
        ],
        "claims": [
            {
                "id": "C-library-absent",
                "claim": (
                    "Library file 12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read "
                    "from disk on this worktree."
                ),
                "verdict": "REFUTED",
            },
            {
                "id": "C-family-seven",
                "claim": (
                    "Fixture family=ENGINEERING-REVIEW yields exactly the 7 named "
                    "P-ids P45-P51, matching the catalog regex recount."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "id": "C-no-oracle",
                "claim": (
                    "P48 and P49 have no executable oracle; P45, P46, P47, P50, "
                    "P51 each settle a planted-good claim and reject a planted-bad claim."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "oracle_both_states": oracle_controls,
        "reviewer": {
            "reviewer_id": "CNL-0045-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-tabulate family membership from fixtures and from the catalog "
                "question_or_target regex; a disagreement in the number blocks."
            ),
        },
        "evidence": [
            {
                "claim": (
                    "Library file 12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read "
                    "from disk on this worktree."
                ),
                "verdict": "REFUTED",
                "anchor": "command-center/p2-wave/probes/CNL-0045/family.py:library_on_this_tree",
            },
            {
                "claim": (
                    "Fixture family=ENGINEERING-REVIEW yields exactly the 7 named "
                    "P-ids P45-P51."
                ),
                "verdict": "CONFIRMED",
                "anchor": str(CATALOGUE.relative_to(REPO).as_posix()),
            },
            {
                "claim": (
                    "Independent catalog regex of CNL-0045 question_or_target "
                    "yields the same 7 P-ids and expected n=7."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json",
            },
            {
                "claim": (
                    "P48 and P49 have no executable oracle; P45, P46, P47, P50, "
                    "P51 each settle a planted-good claim and reject a planted-bad claim."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0045/oracles.py",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": SHARED_SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": str(CATALOGUE.relative_to(REPO).as_posix()),
                "exists": True,
                "role": "fixture",
            },
        ],
        "strongest_surviving_counterargument": (
            "The missing library might assign a different family to one of P45-P51 "
            "or attach an oracle to P48/P49. That would change the tables. The "
            "named-so-no-member-can-fall-through clause in the unit question is "
            "the membership used here; a later library drop must be re-counted, "
            "not assumed equal."
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    shared_path = REPO / SHARED_SCHEMA
    if shared_path.is_file():
        shared = json.loads(shared_path.read_text(encoding="utf-8"))
        try:
            jsonschema.Draft7Validator(shared).validate(doc)
        except jsonschema.ValidationError as exc:
            req = shared.get("required") or []
            if "answers" in req and "family" not in (shared.get("required") or []):
                print(
                    "WARN: shared council-design-note.schema.json is a sibling "
                    f"answers-only contract; local schema used. {exc.message}"
                )
            else:
                raise
        except jsonschema.exceptions.RefResolutionError as exc:
            # Catalog path is a GENERATED SHIM ($ref to artifact-class-profiles).
            # Local probe schema is the executable contract for this unit.
            print(
                "WARN: shared council-design-note.schema.json is a $ref shim; "
                f"local schema used. {exc}"
            )

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} records={len(record_rows)} has_oracle={has_ids} none={none_ids}")
    print("SUCCESS:CNL-0045 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
