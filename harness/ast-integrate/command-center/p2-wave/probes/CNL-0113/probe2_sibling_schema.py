#!/usr/bin/env python3
"""Probe 2: nearest-sibling differential, Draft202012Validator, negative control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0113-jury-family-evidence-adjudication-and-benchmark-results-ju.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0113-probe2 {msg}")
    return 1


def main() -> int:
    j01 = E.evidence_adjudication_preset()
    j02 = E.benchmark_results_preset()
    catalog = E.sibling_catalog()
    nn = E.nearest_sibling(j02, catalog)
    print(
        f"nearest sibling_id={nn['sibling_id']} name={nn['sibling_name']} "
        f"distance={nn['distance']} axes={nn['differing_axes']}"
    )
    if nn["sibling_id"] != "C-J01":
        return fail(f"nearest-not-C-J01:{nn['sibling_id']}")
    if nn["distance"] < 1:
        return fail("distance-zero")
    if not nn["differing_axes"]:
        return fail("no-differing-axes")
    clone = E.name_only_clone(j01, "C-J02-FAKE", "benchmark-results-jury")
    d_clone = E.distance(j01, clone)
    print(f"name-only clone distance={d_clone} (want 0)")
    if d_clone != 0:
        return fail("name-only-clone-not-caught")
    status = E.catalog_schema_status()
    print(
        f"working_schema={status['executable_schema']} "
        f"catalog_has_defs_preset={status['has_defs_preset']} "
        f"rewrote_shared={status['rewrote_shared_schema']}"
    )
    if not status["exists"]:
        return fail("catalog-schema-path-missing")
    if status["rewrote_shared_schema"]:
        return fail("must-not-rewrite-shared-schema")
    valid_errs = E.validate_records([j01, j02])
    invalid_errs = E.validate_records([E.invalid_record()])
    print(f"valid_error_count={len(valid_errs)} invalid_record_error_count={len(invalid_errs)}")
    if valid_errs:
        return fail(f"valid-records:{valid_errs[:4]}")
    if not invalid_errs:
        return fail("validator-vacuous")
    locked_fired = False
    try:
        E.apply_binding(j02, {"producer_recusal": False})
    except PermissionError as exc:
        locked_fired = True
        print(f"locked-dial FIRE {exc}")
    if not locked_fired:
        return fail("locked-dial-silent")
    garbage = [{}, {"passing_tests": 999999}, {"blob": "x" * 2000}]
    for g in garbage:
        ge = E.validate_records([g])
        if not ge:
            return fail(f"garbage-accepted:{list(g)[:1]}")
    art = E.REPO / OUT_REL
    if not art.is_file():
        return fail("artifact-missing")
    doc = json.loads(art.read_text(encoding="utf-8"))
    env_errs = E.validate_envelope(doc)
    print(f"envelope_error_count={len(env_errs)}")
    if env_errs:
        return fail(f"envelope:{env_errs[:4]}")
    if doc.get("sentinel") != "SUCCESS:CNL-0113":
        return fail("sentinel-absent")
    if str(doc.get("state", "")).upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    rec_nn = doc.get("nearest_sibling") or {}
    if rec_nn.get("sibling_id") != "C-J01" or rec_nn.get("distance") != nn["distance"]:
        return fail("artifact-nearest-stale")
    print("negative_control FIRE on name-only clone; SILENT on live C-J02")
    print("SUCCESS:CNL-0113-probe2 sibling-schema negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
