#!/usr/bin/env python3
"""Probe 1: pattern plus entropy sweep over text; planted-PII recall as a number."""
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
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    plants = L.run_text_plants()
    print("channel=" + plants["channel"])
    print("planted_n=" + str(plants["planted_n"]))
    print("found_n=" + str(plants["found_n"]))
    print("recall=" + str(plants["recall"]))
    print("removed_verified=" + str(plants["removed_verified"]))
    print(
        "negative_users_word_only_silent="
        + str(plants["negative_users_word_only_silent"])
    )
    print("value_reproduced=" + str(plants["value_reproduced"]))
    print("pass=" + str(plants["pass"]))
    for row in plants["planted"]:
        print(
            f"plant {row['id']} category={row['category']} found={row['found']} "
            f"entropy={row['entropy']} span_len={row['span_len']}"
        )
    if not plants["pass"]:
        return fail("text planted-PII control did not pass")
    if plants["recall"] != 1.0:
        return fail("text recall is not 1.0")
    if plants["value_reproduced"] is not False:
        return fail("probe reproduced a plant value")

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
    recall = doc.get("recall") or {}
    rate = recall.get("planted_pii_recall")
    if not isinstance(rate, (int, float)):
        return fail("planted-PII recall is not a number")
    print("artifact_planted_pii_recall=" + str(rate))
    stored = doc.get("text_plants") or {}
    if stored.get("removed_verified") is not True:
        return fail("artifact text plants not verified removed")
    if stored.get("value_reproduced") is not False:
        return fail("artifact reproduced a text plant value")
    leaks = L.artifact_leaks_values(doc)
    if leaks:
        return fail("artifact leaked " + ",".join(leaks))
    named = doc.get("named_probes") or []
    if len(named) < 2:
        return fail("named probes missing")
    cmds = [str(p.get("command") or "") for p in named if isinstance(p, dict)]
    if not any("probe1_text_pattern_entropy.py" in c for c in cmds):
        return fail("probe1 command not recorded")
    print("leaks=0")
    print("SUCCESS:ADV-0040-probe1 text pattern+entropy planted recall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
