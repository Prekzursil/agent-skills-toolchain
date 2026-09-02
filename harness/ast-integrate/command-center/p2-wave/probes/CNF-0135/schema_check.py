#!/usr/bin/env python3
"""Validate a ledger document against the local CNF-0135 ledger schema.

Does not import the catalog shim (command-center/schema/discrepancy-ledger.schema.json):
that file is a generated $ref to an unresolvable https://ast-integrate.invalid URL and
carries no test_id constraint. Repo-root `platform/` can also shadow stdlib platform
and break jsonschema, so this module unshadows before importing jsonschema.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _unshadow_stdlib() -> None:
    cleaned: list[str] = []
    for p in sys.path:
        try:
            resolved = Path(p or ".").resolve()
        except OSError:
            cleaned.append(p)
            continue
        if resolved == REPO:
            continue
        cleaned.append(p)
    sys.path[:] = cleaned


_unshadow_stdlib()

from jsonschema import Draft7Validator  # noqa: E402

SCHEMA = HERE / "ledger.schema.json"
CATALOG_SCHEMA = REPO / "command-center" / "schema" / "discrepancy-ledger.schema.json"
TEST_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,}$"


def load_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def validator() -> Draft7Validator:
    return Draft7Validator(load_schema())


def validate(doc: dict) -> None:
    validator().validate(doc)


def error_paths(doc: dict) -> list[str]:
    out = []
    for err in validator().iter_errors(doc):
        out.append("/".join(str(p) for p in err.absolute_path) + ": " + err.message)
    return out


def _self_test() -> int:
    good = {
        "unit_id": "CNF-0135",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0135",
        "entries": [
            {
                "id": "D-001",
                "status": "CLOSED_CONFIRMER_REVISED",
                "test_id": "T-SUM-010",
                "preregistered_at": "2026-08-24T17:00:01Z",
                "verbatim_result": "10",
            },
            {
                "id": "D-003",
                "status": "IRREDUCIBLE",
                "test_id": None,
                "irreducible": {"both_parties_attested_no_executable_test": True},
            },
        ],
    }
    validate(good)
    missing = json.loads(json.dumps(good))
    missing["entries"][0].pop("test_id")
    miss = error_paths(missing)
    empty = json.loads(json.dumps(good))
    empty["entries"][0]["test_id"] = ""
    emp = error_paths(empty)
    garbage = error_paths({"totally": "unrelated"})
    if not miss:
        print("FAILED:schema_check missing test_id was accepted")
        return 1
    if not emp:
        print("FAILED:schema_check empty test_id was accepted")
        return 1
    if not garbage:
        print("FAILED:schema_check garbage was accepted")
        return 1
    print(
        json.dumps(
            {
                "missing": miss[0],
                "empty": emp[0],
                "garbage": garbage[0],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0135-schema-check both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
