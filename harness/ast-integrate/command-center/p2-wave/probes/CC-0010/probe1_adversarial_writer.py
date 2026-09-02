#!/usr/bin/env python3
"""Probe 1: freeze while a writer mutates a tracked file must emit SAMPLE, never BASELINE."""
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
    print(f"FAILED:CC-0010-probe1 {msg}")
    return 1


def main() -> int:
    payload = L.probe1_payload()
    print(L.dumps(payload))
    if not payload.get("ok"):
        return fail(f"adversarial control {payload.get('adversarial')}")
    adv = payload["adversarial"]
    if adv.get("verdict") != "SAMPLE":
        return fail(f"writer freeze verdict {adv.get('verdict')} (must be SAMPLE)")
    if adv.get("refused_baseline") is not True:
        return fail("writer freeze did not refuse BASELINE")
    if not adv.get("classes_complete"):
        return fail("adversarial freeze missing nine snapshot classes")
    if payload.get("nine_classes") != list(L.NINE_CLASSES):
        return fail("nine class names drifted")
    if payload.get("program_pin") != L.PROGRAM_ANCHOR_PREFIX:
        return fail("program pin drifted")

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
    if not list(jsonschema.Draft7Validator(schema).iter_errors({})):
        return fail("schema accepts empty object")

    stored = None
    for p in doc.get("named_probes") or []:
        if p.get("id") == "probe1":
            stored = p.get("raw_output")
            break
    if not stored:
        return fail("named probe1 raw_output missing")
    stored_doc = json.loads(stored)
    for key in ("probe", "unit_id", "adversarial", "nine_classes", "program_pin", "ok"):
        if stored_doc.get(key) != payload.get(key):
            return fail(f"artifact drift on {key}")
    print(
        "SUCCESS:CC-0010-probe1 adversarial-writer "
        f"verdict={adv.get('verdict')} refused_baseline={adv.get('refused_baseline')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
