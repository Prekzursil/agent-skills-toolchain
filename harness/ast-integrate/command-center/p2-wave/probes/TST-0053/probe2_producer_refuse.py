#!/usr/bin/env python3
"""Probe 2: producer refuses to emit case-colliding keys (both-states).

Clean document is emitted. Name+name is refused BEFORE dumps. A dumps-first
mutant still produces colliding bytes, so 'refused' is a live detector.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from case_keys import (  # noqa: E402
    CLEAN_OBJECT,
    COLLIDING_OBJECT,
    NAME_LOWER_VALUE,
    NAME_UPPER_VALUE,
    CaseKeyError,
    emit_first_mutant,
    emit_json,
    naive_dumps,
    pipeline_loads,
)

ART = REPO / "command-center/receipts/TST-0053.json"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0053-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return _fail(f"receipt self-declared {doc.get('state')}")
    if "SUCCESS:TST-0053" not in text:
        return _fail("sentinel absent")

    try:
        clean = emit_json(CLEAN_OBJECT)
    except CaseKeyError as exc:
        return _fail(f"clean document refused: {exc}")
    if '"Name"' in clean:
        return _fail("clean emit unexpectedly contains Name")
    loaded = pipeline_loads(clean)
    if loaded.get("name") != CLEAN_OBJECT["name"]:
        return _fail("clean emit did not round-trip through the pipeline reader")

    refused = False
    refuse_msg = ""
    try:
        emitted = emit_json(COLLIDING_OBJECT)
    except CaseKeyError as exc:
        refused = True
        refuse_msg = str(exc)
        emitted = None
    if not refused or emitted is not None:
        return _fail("colliding object was emitted instead of refused")
    if "Name" not in refuse_msg or "name" not in refuse_msg:
        return _fail(f"refusal did not name both keys: {refuse_msg}")

    naive = naive_dumps(COLLIDING_OBJECT)
    if f'"{NAME_UPPER_VALUE}"' not in naive or f'"{NAME_LOWER_VALUE}"' not in naive:
        return _fail("naive dumps lost a colliding value (detector plant dead)")
    if '"Name"' not in naive or '"name"' not in naive:
        return _fail("naive dumps did not emit both keys")

    nested = {"wrapper": {"Name": NAME_UPPER_VALUE, "name": NAME_LOWER_VALUE}}
    nested_refused = False
    try:
        emit_json(nested)
    except CaseKeyError:
        nested_refused = True
    if not nested_refused:
        return _fail("nested colliding object was emitted")

    mutant = emit_first_mutant(COLLIDING_OBJECT)
    if not mutant.get("emitted_colliding_bytes"):
        return _fail("emit-first mutant produced no colliding bytes (detector silent)")
    if not mutant.get("contains_Name") or not mutant.get("contains_name"):
        return _fail("emit-first mutant dropped a key")

    recorded = doc.get("producer") or {}
    if recorded.get("clean_emitted") is not True:
        return _fail("receipt producer.clean_emitted is not true")
    if recorded.get("colliding_refused") is not True:
        return _fail("receipt producer.colliding_refused is not true")

    summary = {
        "probe": "probe2-producer-refuse",
        "unit_id": "TST-0053",
        "pass": True,
        "clean_emitted": True,
        "colliding_refused": True,
        "nested_refused": nested_refused,
        "naive_emits_both": True,
        "mutant_emitted_colliding_bytes": True,
        "refusal": refuse_msg,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:TST-0053-probe2 producer refuses to emit case-colliding keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
