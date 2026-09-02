#!/usr/bin/env python3
"""Probe 2: non-text PNG zTXt inflate; text sweep is structurally blind."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import lib_adv0040 as L  # noqa: E402

UNIT = "ADV-0040"
ART = REPO / L.OUT_REL
SCHEMA = REPO / L.SCHEMA_REL
SENTINEL = (
    "SUCCESS:ADV-0040 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0040 <reason>."
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    plants = L.run_nontext_plants()
    print("channel=" + plants["channel"])
    print("method=" + plants["method"])
    print("found_n=" + str(plants["found_n"]))
    print("recall=" + str(plants["recall"]))
    print(
        "text_sweep_hits_on_png_bytes="
        + str(plants["text_sweep_hits_on_png_bytes"])
    )
    print(
        "text_sweep_blind_to_screenshot="
        + str(plants["text_sweep_blind_to_screenshot"])
    )
    print("clean_image_silent=" + str(plants["clean_image_silent"]))
    print("removed_verified=" + str(plants["removed_verified"]))
    print("ocr_engine=" + str(plants["ocr_engine"]))
    print("value_reproduced=" + str(plants["value_reproduced"]))
    print("pass=" + str(plants["pass"]))
    if not plants["pass"]:
        return fail("non-text planted-PII control did not pass")
    if not plants["text_sweep_blind_to_screenshot"]:
        return fail("text sweep saw PII in PNG bytes; channel is not distinct")
    if plants["recall"] != 1.0:
        return fail("non-text recall is not 1.0")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        return fail("schema " + errs[0].message)
    stored = doc.get("nontext_plants") or {}
    if stored.get("text_sweep_blind_to_screenshot") is not True:
        return fail("artifact does not record text-sweep blindness")
    if stored.get("removed_verified") is not True:
        return fail("artifact non-text plants not verified removed")
    live_images = L.scan_corpus_nontext()
    stored_img = doc.get("corpus_nontext") or {}
    try:
        stored_n = int(stored_img["image_files"])
    except (KeyError, TypeError, ValueError):
        return fail("artifact corpus_nontext.image_files missing")
    live_n = int(live_images["image_files"])
    if stored_n != live_n:
        return fail(f"corpus image_files count mismatch stored={stored_n} live={live_n}")
    print("corpus_image_files=" + str(live_images["image_files"]))
    leaks = L.artifact_leaks_values(doc)
    if leaks:
        return fail("artifact leaked " + ",".join(leaks))
    named = doc.get("named_probes") or []
    cmds = [str(p.get("command") or "") for p in named if isinstance(p, dict)]
    if not any("probe2_nontext_metadata.py" in c for c in cmds):
        return fail("probe2 command not recorded")
    print("leaks=0")
    print("SUCCESS:ADV-0040-probe2 png-ztxt inflate vs text-sweep blindness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
