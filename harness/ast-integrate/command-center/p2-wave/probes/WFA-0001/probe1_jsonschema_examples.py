#!/usr/bin/env python3
"""Probe 1: python-jsonschema Draft 2020-12 over the 36 bundled examples.

Also asserts additionalProperties:false on all 18 $defs, and that deleting
one required key from each valid example flips it to invalid.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pack_lib as L  # noqa: E402

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0001-probe1 {msg}")
    return 1


def validator_for(pack: dict, defn: dict) -> Draft202012Validator:
    return Draft202012Validator(defn, registry=None)


def accepts(v: Draft202012Validator, instance: object) -> bool:
    return not list(v.iter_errors(instance))


def main() -> int:
    pack = L.load_pack()
    text = L.PACK_PATH.read_text(encoding="utf-8")
    if str(pack.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {pack.get('state')}")
    if L.SENTINEL not in text:
        return fail("catalog sentinel absent from pack")
    try:
        Draft202012Validator.check_schema(pack)
    except SchemaError as exc:
        return fail(f"check_schema: {exc}")

    try:
        names = L.assert_additional_properties_false(pack)
    except AssertionError as exc:
        return fail(str(exc))
    print(f"additionalProperties_false={len(names)}/18")

    root_v = Draft202012Validator(pack)
    garbage_errors = [len(list(root_v.iter_errors(g))) for g in GARBAGE]
    print(f"garbage_error_counts={garbage_errors}")
    if any(n == 0 for n in garbage_errors):
        return fail("pack used as contract accepts garbage (vacuous)")

    defs = L.defs_of(pack)
    accept_n = 0
    reject_n = 0
    for name in L.RECORD_TYPES:
        defn = defs[name]
        valid, invalid = L.bundled_examples(defn, name)
        v = Draft202012Validator(defn)
        if not accepts(v, valid):
            errs = [e.message for e in v.iter_errors(valid)]
            return fail(f"{name} valid example rejected: {errs[:4]}")
        if accepts(v, invalid):
            return fail(f"{name} invalid example accepted")
        if not accepts(root_v, valid):
            return fail(f"{name} valid example rejected by pack root oneOf")
        if accepts(root_v, invalid):
            return fail(f"{name} invalid example accepted by pack root oneOf")
        accept_n += 1
        reject_n += 1
        key, mutant = L.delete_first_required(valid, defn)
        if accepts(v, mutant):
            return fail(f"{name} both-states silent after deleting {key}")
        print(f"{name} valid=accept invalid=reject both_states_deleted={key}")

    print(f"cases_accept={accept_n} cases_reject={reject_n} total=36")
    if accept_n != 18 or reject_n != 18:
        return fail("expected 18 accept + 18 reject")
    print("SUCCESS:WFA-0001-probe1 jsonschema 36 cases + both-states + additionalProperties")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
