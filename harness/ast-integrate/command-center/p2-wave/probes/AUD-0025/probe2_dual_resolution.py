#!/usr/bin/env python3
"""Probe 2: two resolver seeds (lowest vs highest) over the fixture index.

Control: an exact pin must resolve identically on both seeds. If it does not,
the resolution probe is contaminated and this probe fails.
A planted floating constraint must differ across seeds or the detector is inert.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

ART = L.REPO / L.OUT_REL
SCHEMA = L.REPO / L.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0025-probe2 {msg}")
    return 1


def main() -> int:
    payload = L.probe2_payload()
    print(L.dumps(payload))
    ctl = payload["resolution_control"]
    if ctl["contaminated"]:
        return fail("exact pin differed across seeds; resolver contaminated")
    if not ctl["exact_identical_across_seeds"]:
        return fail(f"exact pin control {ctl.get('exact_row')}")
    if not ctl["float_differs_across_seeds"]:
        return fail(f"float control did not discriminate {ctl.get('float_row')}")
    if not ctl["ok"]:
        return fail("resolution control not ok")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if L.SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")

    stored = None
    for p in doc.get("named_probes") or []:
        if p.get("id") == "probe2":
            stored = p.get("raw_output")
            break
    if not stored:
        return fail("named probe2 raw_output missing")
    stored_doc = json.loads(stored)
    for key in (
        "floating_in_practice_count",
        "floating_names",
        "resolution_control",
        "live_dual",
        "seeds",
        "index",
    ):
        if stored_doc.get(key) != payload.get(key):
            return fail(f"artifact drift on {key}")
    census = doc.get("census") or {}
    if census.get("floating_in_practice_count") != payload["floating_in_practice_count"]:
        return fail("headline floating_in_practice_count drift")
    # Independent recount of live dual-seed floats.
    live_float = sum(1 for r in payload["live_dual"] if r.get("floats_in_practice") is True)
    if live_float != payload["floating_in_practice_count"]:
        return fail(f"recount {live_float} != {payload['floating_in_practice_count']}")
    print(
        "SUCCESS:AUD-0025-probe2 dual-seed "
        f"float={payload['floating_in_practice_count']} "
        f"exact_same={ctl['exact_identical_across_seeds']} "
        f"float_differs={ctl['float_differs_across_seeds']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
