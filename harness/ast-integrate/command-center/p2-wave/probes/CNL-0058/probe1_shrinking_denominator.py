#!/usr/bin/env python3
"""Probe 1: shrinking-denominator both-states control + schema garbage rejection.

Planted-bad must FIRE; known-good must be SILENT. Same ballots with a shrunk
denominator must not silently cross 2/3. Negative control recorded verbatim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures_lib as F  # noqa: E402
import tally as T  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md"
)
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"
RULE = T.SUPERMAJORITY_2_3


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0058-probe1 {msg}")
    return 1


def main() -> int:
    bad = F.load_fixture("planted-bad")
    good = F.load_fixture("known-good")
    void = F.load_fixture("quorum-void")
    maj = F.load_fixture("majority-not-supermajority")
    death = F.load_fixture("death-unreplaced")

    r_bad = T.decide(bad, RULE)
    r_good = T.decide(good, RULE)
    r_void = T.decide(void, RULE)
    r_maj_m = T.decide(maj, T.MAJORITY)
    r_maj_s = T.decide(maj, RULE)
    replaced = T.replace_seat(death, "F", "F2", T.YES)
    if replaced.get("id") == "death-unreplaced":
        replaced["id"] = "replacement"
    r_death = T.decide(death, RULE)
    r_rep = T.decide(replaced, RULE)

    print("verbatim_fire " + T.compact(r_bad))
    print("verbatim_silent " + T.compact(r_good))
    print("verbatim_quorum_void " + T.compact(r_void))
    print("verbatim_majority " + T.compact(r_maj_m))
    print("verbatim_super_on_maj_fixture " + T.compact(r_maj_s))
    print("verbatim_death " + T.compact(r_death))
    print("verbatim_replacement " + T.compact(r_rep))

    if r_bad["detector"] != "FIRE":
        return fail("planted-bad detector not FIRE")
    if r_bad["frozen_pass"] is True or r_bad["shrunk_pass"] is not True:
        return fail("planted-bad must fail freeze-N and pass shrunk N")
    if r_bad["yes"] != 3 or r_bad["freeze_n"] != 6 or r_bad["shrunk_n"] != 4:
        return fail("planted-bad counts unexpected")
    if r_bad["outcome"] != "FAIL":
        return fail("planted-bad official outcome must be FAIL on freeze-N")

    if r_good["detector"] != "SILENT":
        return fail("known-good detector not SILENT")
    if r_good["frozen_pass"] is not True or r_good["outcome"] != "PASS":
        return fail("known-good must PASS freeze-N supermajority")
    if r_good["yes"] != 4 or r_good["freeze_n"] != 6 or r_good["shrunk_n"] != 6:
        return fail("known-good counts unexpected")

    if r_void["outcome"] != "NO_QUORUM":
        return fail("quorum-void must be NO_QUORUM")
    if r_void["detector"] != "FIRE":
        return fail("quorum-void shrinking would pass; detector must FIRE")
    if r_void["quorum_met"] is True:
        return fail("quorum-void participating must miss quorum")

    if r_maj_m["frozen_pass"] is not True or r_maj_s["frozen_pass"] is not False:
        return fail("N=5 with 3 yes must be majority PASS and supermajority FAIL")

    if r_death["freeze_n"] != 6 or r_rep["freeze_n"] != 6:
        return fail("replacement must not drop freeze-N")
    if r_death["outcome"] != "FAIL":
        return fail("unreplaced death with 3 yes / 6 must FAIL supermajority")
    if r_rep["outcome"] != "PASS" or r_rep["yes"] != 4:
        return fail("replacement yes must PASS freeze-N supermajority")
    if r_rep["detector"] != "SILENT":
        return fail("honest replacement pass must be SILENT")

    same_yes = r_bad["yes"]
    if not T.threshold_met(same_yes, r_bad["shrunk_n"], RULE):
        return fail("shrunk denominator did not cross; fixture is not shrinking")
    if T.threshold_met(same_yes, r_bad["freeze_n"], RULE):
        return fail("freeze-N already passes; fixture is not planted-bad")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("design note missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0058" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        return fail(f"schema errors: {errors[0].message}")

    garbage_docs = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0058", "state": "SUCCESS", "sentinel": "SUCCESS:CNL-0058"},
    ]
    rejected = 0
    for g in garbage_docs:
        ge = list(validator.iter_errors(g))
        print(f"garbage_rejected={bool(ge)} keys={sorted(g)}")
        if ge:
            rejected += 1
    if rejected != 3:
        return fail(f"schema vacuous: rejected {rejected}/3 garbage docs")

    bs = doc.get("both_states") or {}
    if "FIRE" not in str(bs.get("verbatim_fire") or ""):
        return fail("artifact both_states.verbatim_fire missing FIRE")
    if "SILENT" not in str(bs.get("verbatim_silent") or ""):
        return fail("artifact both_states.verbatim_silent missing SILENT")
    measured = (doc.get("measured") or {}).get("supermajority") or {}
    for key, live in (
        ("planted-bad", r_bad),
        ("known-good", r_good),
        ("quorum-void", r_void),
    ):
        row = measured.get(key) or {}
        for field in ("yes", "freeze_n", "shrunk_n", "detector", "outcome"):
            if row.get(field) != live[field]:
                return fail(f"artifact measured.{key}.{field} != live {live[field]!r}")

    print("both_states planted-bad=FIRE known-good=SILENT schema_garbage=3/3")
    print("SUCCESS:CNL-0058-probe1 shrinking-denominator both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
