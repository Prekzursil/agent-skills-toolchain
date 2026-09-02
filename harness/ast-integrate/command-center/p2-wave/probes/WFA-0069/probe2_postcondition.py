#!/usr/bin/env python3
"""Probe 2: independent postcondition + re-run of both-states.

Evidence B: artifact exists, exceeds a size floor, and parses against the
local DispositionRecord schema. Also re-runs the both-states control before
signing PASS. Exit code zero of the emitter is not consulted.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from controls import run_both_states  # noqa: E402
from registry import EXPECTED_N  # noqa: E402
from smoke import ADOPT, UNKNOWN, digest_file, reset_bounds  # noqa: E402

OUT = "command-center/wfa/WFA-0069-adopt-as-is-executable-test.json"
SCHEMA = "command-center/p2-wave/probes/WFA-0069/disposition.schema.json"
SIZE_FLOOR = 8192
SENTINEL = "SUCCESS:WFA-0069"
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
]


def main() -> int:
    reset_bounds()
    with tempfile.TemporaryDirectory(prefix="wfa0069-p2-") as tmp:
        both = run_both_states(Path(tmp))
    if not both["ok"]:
        print("FAILED:WFA-0069-probe2 both-states re-run did not pass")
        return 1

    path = REPO / OUT
    if not path.is_file():
        print(f"FAILED:WFA-0069-probe2 artifact missing {OUT}")
        return 1
    sha, size = digest_file(path)
    if size < SIZE_FLOOR:
        print(f"FAILED:WFA-0069-probe2 size floor bytes={size} floor={SIZE_FLOOR}")
        return 1
    try:
        text = path.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"FAILED:WFA-0069-probe2 unparseable {type(exc).__name__}")
        return 1
    if SENTINEL not in text:
        print("FAILED:WFA-0069-probe2 sentinel-absent")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:WFA-0069-probe2 artifact not an object")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0069-probe2 self-declared {doc.get('state')}")
        return 1

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:WFA-0069-probe2 schema errors")
        for e in errs[:8]:
            print(" ", list(e.path), e.message)
        return 1
    for g in GARBAGE:
        if not list(jsonschema.Draft7Validator(schema).iter_errors(g)):
            print("FAILED:WFA-0069-probe2 schema accepted garbage")
            return 1

    records = doc.get("records") or []
    if len(records) != EXPECTED_N:
        print(f"FAILED:WFA-0069-probe2 records {len(records)} != {EXPECTED_N}")
        return 1
    for rec in records:
        if rec.get("smoke_run", {}).get("constructed") is False:
            if rec.get("disposition") != UNKNOWN:
                print(f"FAILED:WFA-0069-probe2 unconstructable still ADOPT {rec.get('candidate_id')}")
                return 1
        rec_path = REPO / str(rec.get("receipt_path") or "")
        if not rec_path.is_file() or rec_path.stat().st_size <= 0:
            print(f"FAILED:WFA-0069-probe2 missing receipt {rec.get('receipt_path')}")
            return 1
        live_sha, live_n = digest_file(rec_path)
        if rec.get("receipt_sha256") != live_sha or rec.get("receipt_bytes") != live_n:
            print(f"FAILED:WFA-0069-probe2 receipt hash mismatch {rec.get('candidate_id')}")
            return 1
        try:
            json.loads(rec_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            print(f"FAILED:WFA-0069-probe2 receipt unparseable {rec.get('candidate_id')}")
            return 1
        if rec.get("disposition") == ADOPT:
            body = json.loads(rec_path.read_text(encoding="utf-8"))
            if body.get("terminal") != "PASS" or body.get("constructed") is not True:
                print(f"FAILED:WFA-0069-probe2 ADOPT without passing receipt {rec.get('candidate_id')}")
                return 1

    print(
        json.dumps(
            {
                "artifact": OUT,
                "bytes": size,
                "sha256": sha,
                "records": len(records),
                "both_states_rerun": True,
                "schema_parse": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0069-probe2 postcondition and both-states re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
