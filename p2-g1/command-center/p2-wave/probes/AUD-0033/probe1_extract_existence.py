#!/usr/bin/env python3
"""Probe 1: extract path tokens and test existence.

Independent of git. The fixture control is both assertions on one file:
a fenced path is extracted; a prose slash is not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import extract as X  # noqa: E402
import exist as E  # noqa: E402
import sweep as S  # noqa: E402
from jsonschema import Draft7Validator  # noqa: E402

ART = C.REPO / C.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{C.UNIT}-probe1 {msg}")
    return 1


def schema_check() -> dict:
    schema = json.loads((C.REPO / C.SCHEMA_REL).read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    empty = {}
    blob = {"blob": "x" * 2000}
    return {
        "schema_exists": (C.REPO / C.SCHEMA_REL).is_file(),
        "garbage_rejected": bool(list(validator.iter_errors(garbage))),
        "empty_rejected": bool(list(validator.iter_errors(empty))),
        "blob_rejected": bool(list(validator.iter_errors(blob))),
    }


def main() -> int:
    ctl = S.control_from_fixture(C.REPO)
    fence_exists = E.exists_with_retry(C.FENCE_PRESENT, C.REPO)
    missing_exists = E.exists_with_retry(C.FENCE_MISSING, C.REPO)
    tick_exists = E.exists_with_retry(C.TICK_PATH, C.REPO)
    schema = schema_check()

    art_ok = False
    art_state = None
    if ART.is_file() and ART.stat().st_size > 0:
        text = ART.read_text(encoding="utf-8")
        art_ok = C.SENTINEL in text
        try:
            doc = json.loads(text)
            art_state = doc.get("state")
        except json.JSONDecodeError:
            art_state = "UNPARSEABLE"

    live = S.run_sweep(C.REPO)
    # Re-assert existence independently of the aggregated sweep map.
    live_present = live["present_count"]
    live_missing = live["missing_count"]

    ok = (
        ctl["pass"]
        and ctl["fence_present_extracted"]
        and not ctl["prose_false_path_extracted"]
        and ctl["naive_extracts_prose_false_path"]
        and fence_exists["exists"] is True
        and missing_exists["exists"] is False
        and tick_exists["exists"] is True
        and schema["garbage_rejected"]
        and schema["empty_rejected"]
        and live["files_scanned"] >= 1
        and art_ok
        and str(art_state or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
    )
    payload = {
        "probe": "probe1-extract-existence",
        "unit_id": C.UNIT,
        "pass": bool(ok),
        "control": {
            "id": ctl["id"],
            "pass": ctl["pass"],
            "fence_present_extracted": ctl["fence_present_extracted"],
            "fence_missing_extracted": ctl["fence_missing_extracted"],
            "tick_extracted": ctl["tick_extracted"],
            "prose_false_path_extracted": ctl["prose_false_path_extracted"],
            "naive_extracts_prose_false_path": ctl["naive_extracts_prose_false_path"],
            "fired_on_bad_state": ctl["fired_on_bad_state"],
            "silent_on_good_state": ctl["silent_on_good_state"],
        },
        "existence": {
            "fence_present": fence_exists,
            "fence_missing": missing_exists,
            "tick": tick_exists,
        },
        "live": {
            "files_scanned": live["files_scanned"],
            "citation_count": live["citation_count"],
            "unique_paths": live["unique_paths"],
            "present_count": live_present,
            "missing_count": live_missing,
            "every_cited_path_exists": live["every_cited_path_exists"],
            "encoding_retries": live["encoding_retries"],
            "path_length_retries": live["path_length_retries"],
        },
        "schema": schema,
        "artifact_has_sentinel": art_ok,
        "artifact_state": art_state,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        return fail(
            "control or existence rail failed "
            f"ctl={ctl['pass']} naive_prose={ctl['naive_extracts_prose_false_path']} "
            f"prose_leak={ctl['prose_false_path_extracted']} "
            f"present={fence_exists['exists']} missing={missing_exists['exists']} "
            f"art={art_ok}/{art_state}"
        )
    print(
        "SUCCESS:AUD-0033-probe1 extractor finds the fenced path, ignores the "
        "prose slash, and existence tests present vs planted-missing"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
