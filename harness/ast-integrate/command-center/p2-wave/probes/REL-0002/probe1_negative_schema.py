#!/usr/bin/env python3
"""Probe 1: catalog negative controls against the rollback-contract schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402
import validator as V  # noqa: E402


def main() -> int:
    fail = False
    doc = I.build_inventory()
    validator = V.rollback_validator()
    clean = V.error_strings(validator, doc)
    print(
        json.dumps(
            {
                "clean_errors": clean,
                "n_actions": len(doc["actions"]),
                "catalog_types": I.catalog_types_covered(doc),
            },
            sort_keys=True,
        )
    )
    if clean:
        print(f"FAILED:REL-0002-probe1 clean inventory invalid: {clean[:6]}")
        fail = True

    m1 = V.mutant_no_inverse_no_irreversible(doc)
    e1 = V.error_strings(validator, m1)
    print(f"no_inverse_no_IRREVERSIBLE errors={len(e1)} sample={e1[:3]}")
    if not e1:
        print("FAILED:REL-0002-probe1 missing inverse was accepted")
        fail = True

    m2 = V.mutant_inverse_outside_creation_set(doc)
    e2 = V.error_strings(validator, m2)
    print(f"inverse_outside_creation_set errors={len(e2)} sample={e2[:3]}")
    if not e2:
        print("FAILED:REL-0002-probe1 outsider inverse was accepted")
        fail = True
    if not any("creation set" in x or INV_HINT in x for x in e2):
        # still require the creation-set invariant to fire, not a random error
        if not any("predated" in x.lower() or "creation" in x.lower() for x in e2):
            print("FAILED:REL-0002-probe1 outsider inverse failed for the wrong reason")
            fail = True

    m3 = V.mutant_partial_omits_residue(doc)
    e3 = V.error_strings(validator, m3)
    print(f"partial_omits_residue errors={len(e3)} sample={e3[:3]}")
    if not e3:
        print("FAILED:REL-0002-probe1 partial inverse without residue was accepted")
        fail = True
    if not any("residue" in x.lower() for x in e3):
        print("FAILED:REL-0002-probe1 residue omission failed for the wrong reason")
        fail = True

    silent = V.error_strings(validator, doc)
    print(f"both_states clean_still_silent={silent == []}")
    if silent:
        print("FAILED:REL-0002-probe1 clean inventory no longer silent after mutants")
        fail = True

    if fail:
        print("FAILED:REL-0002-probe1 negative schema controls")
        return 1
    print(
        "SUCCESS:REL-0002-probe1 no-inverse, outsider-target, missing-residue "
        "all fail; clean inventory silent"
    )
    return 0


INV_HINT = V.INV_PATH


if __name__ == "__main__":
    raise SystemExit(main())
