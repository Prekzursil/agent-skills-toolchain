#!/usr/bin/env python3
"""Probe 2: independent catalog recount + custom-role negative controls.

Signal class: regex over WORK-UNIT-CATALOG.json CNL-0038..CNL-0046 questions
(not protocols.json import), plus authoring-contract checks on planted-bad
and known-good custom roles. Schema-validates the design note if present.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import authoring as A  # noqa: E402
import catalog_pids as P  # noqa: E402

NOTE = (
    REPO
    / "command-center"
    / "design"
    / "council"
    / "CNL-0028-role-template-library-and-the-custom-role-authoring-contra.md"
)
SCHEMA = REPO / "command-center" / "schema" / "council-design-note.schema.json"
PROTOCOLS = HERE / "protocols.json"
OUT = HERE / "probe2-reviewer.raw.json"


def main() -> int:
    extracted = P.catalog_protocol_ids()
    census = json.loads(PROTOCOLS.read_text(encoding="utf-8"))
    fixture_ids = sorted((r["id"] for r in census["protocols"]), key=lambda x: int(x[1:]))
    catalog_match = extracted["ids"] == fixture_ids and extracted["n"] == 58

    good = A.check_custom_role(A.good_custom_role())
    self_judge = A.check_custom_role(A.bad_self_judge())
    missing = A.check_custom_role(A.bad_missing_capabilities())
    escalate = A.check_custom_role(A.bad_rights_escalation())

    schema_ok = False
    schema_errors = 0
    sentinel_ok = False
    if NOTE.is_file() and SCHEMA.is_file():
        import jsonschema

        note = json.loads(NOTE.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        validator = jsonschema.Draft7Validator(schema)
        errs = list(validator.iter_errors(note))
        schema_errors = len(errs)
        schema_ok = schema_errors == 0
        sentinel_ok = "SUCCESS:CNL-0028" in NOTE.read_text(encoding="utf-8")
        bogus = dict(note)
        bogus.pop("unit_id", None)
        bogus_errs = list(validator.iter_errors(bogus))
        vacuous = len(bogus_errs) == 0
    else:
        vacuous = True
        bogus_errs = []

    both_states = (
        good["accepted"] is True
        and self_judge["accepted"] is False
        and "SELF_JUDGE" in self_judge["codes"]
        and missing["accepted"] is False
        and "MISSING_CAPABILITIES" in missing["codes"]
        and escalate["accepted"] is False
        and "RIGHTS_ESCALATION" in escalate["codes"]
    )
    payload = {
        "catalog_n": extracted["n"],
        "catalog_ids": extracted["ids"],
        "fixture_ids": fixture_ids,
        "catalog_match": catalog_match,
        "good_accepted": good["accepted"],
        "self_judge_codes": self_judge["codes"],
        "missing_codes": missing["codes"],
        "escalate_codes": escalate["codes"],
        "schema_ok": schema_ok,
        "schema_errors": schema_errors,
        "sentinel_ok": sentinel_ok,
        "validator_vacuous": vacuous,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "catalog_n="
        + str(extracted["n"])
        + " catalog_match="
        + str(catalog_match)
        + " good_accepted="
        + str(good["accepted"])
        + " self_judge="
        + json.dumps(self_judge["codes"])
        + " missing="
        + json.dumps(missing["codes"])
        + " escalate="
        + json.dumps(escalate["codes"])
        + " schema_ok="
        + str(schema_ok)
        + " schema_errors="
        + str(schema_errors)
        + " sentinel_ok="
        + str(sentinel_ok)
        + " validator_vacuous="
        + str(vacuous)
    )
    print(
        "NEGATIVE_CONTROL_VERBATIM: check_custom_role(authors=['proposal'] AND "
        "judges=['proposal']) returns accepted=false codes=['SELF_JUDGE']; "
        "check_custom_role(missing capabilities object) returns accepted=false "
        "codes containing MISSING_CAPABILITIES; a known-good custom role that "
        "extends critic is accepted=true."
    )
    ok = (
        catalog_match
        and both_states
        and schema_ok
        and sentinel_ok
        and vacuous is False
    )
    if not ok:
        print("FAILED:CNL-0028-probe2 catalog recount and authoring negatives")
        return 1
    print("SUCCESS:CNL-0028-probe2 independent recount and negative controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
