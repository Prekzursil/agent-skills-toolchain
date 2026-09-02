#!/usr/bin/env python3
"""Probe 2: redaction both-states + schema-document discrimination.

A payload with a planted canary secret and an absolute home path must be
rejected or scrubbed. A clean payload of the same shape must be accepted.
A scanner that cannot see the unredacted canary measures nothing.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import runtime as R  # noqa: E402
from clauses import CLAUSE_STRINGS, SENTINEL  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0096-probe2 {msg}")
    return 1


def main() -> int:
    if not R.CONTRACT_PATH.is_file():
        return fail("contract missing")
    text = R.CONTRACT_PATH.read_text(encoding="utf-8")
    missing = [c for c in CLAUSE_STRINGS if c not in text]
    if missing:
        return fail(f"contract missing clauses {missing[:2]}")
    if SENTINEL not in text:
        return fail("sentinel absent")

    doc = R.load_contract()
    try:
        jsonschema.Draft202012Validator.check_schema(doc)
    except Exception as exc:
        return fail(f"check_schema {type(exc).__name__}: {exc}")
    v = jsonschema.Draft202012Validator(doc)
    garbage = (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    )
    for g in garbage:
        if not list(v.iter_errors(g)):
            return fail("schema-document-vacuous")

    def def_validator(name: str):
        wrapped = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"#/$defs/{name}",
            "$defs": doc["$defs"],
        }
        return jsonschema.Draft202012Validator(wrapped)

    pv = def_validator("telemetry_policy")
    good_policy = R.policy(enabled=True, local_recording=True)
    if list(pv.iter_errors(good_policy)):
        return fail(f"good policy rejected {list(pv.iter_errors(good_policy))[:1]}")
    if not list(pv.iter_errors({})):
        return fail("policy schema accepted empty object")

    lv = def_validator("decision_log")
    opt_in = R.load_decision_log(R.FIXTURES / "opt-in.json")
    log_errs = list(lv.iter_errors(opt_in))
    if log_errs:
        return fail(f"opt-in fixture rejected by $defs/decision_log: {log_errs[0].message}")

    clean = R.sample_event(probe_id="probe2", error_class="NONE")
    prepared = R.prepare_event(copy.deepcopy(clean))
    if list(v.iter_errors(prepared)):
        return fail("clean event failed schema after prepare")
    if R.leak_scan(json.dumps(prepared)):
        return fail("clean event flagged as leak")

    dirty = copy.deepcopy(clean)
    dirty["prompt"] = (
        f"run with token={R.CANARY} cwd={R.HOME_UNIX} win={R.HOME_WIN}"
    )
    dirty["secret"] = R.CANARY
    dirty["home"] = R.HOME_UNIX
    unredacted = json.dumps(dirty)
    detector_on_dirty = R.leak_scan(unredacted)
    if "canary-secret" not in detector_on_dirty:
        return fail("detector silent on unredacted canary; measures nothing")
    if "home-unix" not in detector_on_dirty and "abs-path" not in detector_on_dirty:
        return fail("detector silent on unredacted home path")

    scrubbed = R.prepare_event(copy.deepcopy(dirty))
    out_blob = json.dumps(scrubbed)
    leftover = R.leak_scan(out_blob)
    if leftover:
        return fail(f"scrubbed event still leaks {leftover}")
    if R.CANARY in out_blob or R.HOME_UNIX in out_blob or R.HOME_WIN in out_blob:
        return fail("planted values survived allow-list strip")
    if "prompt" in scrubbed or "secret" in scrubbed or "home" in scrubbed:
        return fail("forbidden keys survived")

    stuffed = copy.deepcopy(clean)
    stuffed["error_class"] = R.CANARY
    rejected = False
    try:
        R.prepare_event(stuffed)
    except PermissionError:
        rejected = True
    if not rejected:
        return fail("canary stuffed into error_class was accepted")

    none = R.load_decision_log(R.FIXTURES / "no-opt-in.json")
    emit_clean = R.emit(
        copy.deepcopy(clean),
        R.policy(enabled=True, local_recording=False),
        none,
        endpoint=None,
    )
    if emit_clean.get("status") != "LOCAL-ONLY" or emit_clean.get("event") is None:
        return fail(f"clean emit without opt-in status={emit_clean.get('status')}")

    emit_dirty = R.emit(
        copy.deepcopy(dirty),
        R.policy(enabled=True, local_recording=False),
        none,
        endpoint=None,
    )
    if emit_dirty.get("status") not in {"LOCAL-ONLY", "REJECTED"}:
        return fail(f"dirty emit status={emit_dirty.get('status')}")
    if emit_dirty.get("event") is not None:
        if R.leak_scan(json.dumps(emit_dirty["event"])):
            return fail("dirty emit event leaked")

    print(
        json.dumps(
            {
                "probe": "probe2-redaction",
                "unit_id": "ARC-0096",
                "schema_discriminates_garbage": True,
                "detector_on_unredacted": detector_on_dirty,
                "clean_accepted": True,
                "extra_fields_scrubbed": True,
                "stuffed_canary_rejected": rejected,
                "dirty_emit_status": emit_dirty.get("status"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(
        f"detector_on_dirty={detector_on_dirty} stuffed_rejected={rejected} "
        f"clean_ok=True leftover={leftover}"
    )
    print("SUCCESS:ARC-0096-probe2 redaction both-states and schema discrimination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
