#!/usr/bin/env python3
"""Probe 2: independent (non-jsonschema) validator over the same 36 cases.

A disagreement with python-jsonschema is a schema-portability defect, not a
tie to be broken by preference. This probe does not import jsonschema.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import independent_validator as IV  # noqa: E402
import pack_lib as L  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0001-probe2 {msg}")
    return 1


def main() -> int:
    if "jsonschema" in sys.modules:
        return fail("jsonschema already imported; probe2 must stay independent")
    pack = L.load_pack()
    try:
        L.assert_additional_properties_false(pack)
    except AssertionError as exc:
        return fail(str(exc))
    defs = L.defs_of(pack)
    accept_n = 0
    reject_n = 0
    for name in L.RECORD_TYPES:
        defn = defs[name]
        valid, invalid = L.bundled_examples(defn, name)
        v_err = IV.iter_errors(valid, defn, pack)
        i_err = IV.iter_errors(invalid, defn, pack)
        if v_err:
            return fail(f"{name} valid example rejected independently: {v_err[:4]}")
        if not i_err:
            return fail(f"{name} invalid example accepted independently")
        root_v = IV.iter_errors(valid, pack, pack)
        root_i = IV.iter_errors(invalid, pack, pack)
        if root_v:
            return fail(f"{name} valid example rejected by independent root oneOf: {root_v[:3]}")
        if not root_i:
            return fail(f"{name} invalid example accepted by independent root oneOf")
        key, mutant = L.delete_first_required(valid, defn)
        m_err = IV.iter_errors(mutant, defn, pack)
        if not m_err:
            return fail(f"{name} both-states silent independently after deleting {key}")
        accept_n += 1
        reject_n += 1
        print(
            f"{name} independent valid=accept invalid=reject "
            f"invalid_errors={len(i_err)} both_states_deleted={key}"
        )
    print(f"cases_accept={accept_n} cases_reject={reject_n} total=36")
    if accept_n != 18 or reject_n != 18:
        return fail("expected 18 accept + 18 reject")
    if "jsonschema" in sys.modules:
        return fail("jsonschema imported during probe2")
    print("SUCCESS:WFA-0001-probe2 independent validator 36 cases + both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
