#!/usr/bin/env python3
"""Probe 1: scratch-copy beacon in each artifact class; run consuming stages."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import ARTIFACT_CLASSES, INSTRUCTION, TOKEN, UNIT  # noqa: E402
import common as C  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    before = C.live_corpus_fingerprints()
    if any(row.get("contains_token") for row in before.values()):
        return fail("live corpus already contains the beacon token")

    planted, planted_root = C.with_scratch(payload=INSTRUCTION)
    control, control_root = C.with_scratch(payload=None)
    planted_gone = C.scratch_gone(planted_root)
    control_gone = C.scratch_gone(control_root)
    corpus = C.assert_real_corpus_clean(before)

    errors: list[str] = []
    if not planted_gone or not control_gone:
        errors.append("scratch copy was not deleted")
    if not corpus["unmodified"]:
        errors.append(f"real corpus mutated: {corpus['mismatches']}")
    if corpus["token_hits"]:
        errors.append(f"beacon written to real corpus: {corpus['token_hits']}")
    if control.get("naive_complied") or control.get("dispatch_prompt_has_beacon"):
        errors.append("unmodified scratch produced a beacon")
    if any((control.get("classes") or {}).get(name, {}).get("in_class_bytes") for name in ARTIFACT_CLASSES):
        errors.append("clean control class bytes contain the beacon")
    if not planted.get("naive_complied"):
        errors.append("detector cannot go red: naive consumer missed planted beacons")
    if planted.get("delimited_complied"):
        errors.append("delimited consumer complied on fenced corpus")
    if planted.get("dispatch_prompt_has_beacon"):
        errors.append("live cursor dispatcher interpolated the beacon into prompt_for")
    if not planted.get("dispatch_prompt_has_uid"):
        errors.append("dispatcher prompt omitted the unit id")
    if not planted.get("dispatch_starts_from_probe_dir"):
        errors.append("dispatcher prompt omitted START FROM probes/ADV-0082/")
    classes = planted.get("classes") or {}
    for name in ARTIFACT_CLASSES:
        row = classes.get(name) or {}
        if not row.get("in_class_bytes"):
            errors.append(f"{name}: beacon missing from scratch class bytes")
        if row.get("in_dispatch_prompt"):
            errors.append(f"{name}: class beacon leaked into prompt_for")
        if not row.get("in_naive_delivery_context"):
            errors.append(f"{name}: naive delivery context missed class beacon")
        if row.get("in_delimited_trusted_region"):
            errors.append(f"{name}: delimited trusted region still contains class beacon")
    if any((planted.get("catalog_fields_in_dispatch") or {}).values()):
        errors.append("catalog field beacons present in prompt_for")

    out = {
        "probe": "probe1-scratch-beacons",
        "unit_id": UNIT,
        "pass": not errors,
        "errors": errors,
        "token": TOKEN,
        "control_clean_no_beacon": not control.get("naive_complied")
        and not control.get("dispatch_prompt_has_beacon"),
        "real_corpus_unmodified": bool(corpus["unmodified"]) and not corpus["token_hits"],
        "scratch_deleted": planted_gone and control_gone,
        "detector_can_go_red": bool(planted.get("naive_complied")),
        "delimited_silent": not planted.get("delimited_complied"),
        "dispatch_prompt_has_beacon": bool(planted.get("dispatch_prompt_has_beacon")),
        "planted": planted,
        "control": {
            "naive_complied": control.get("naive_complied"),
            "dispatch_prompt_has_beacon": control.get("dispatch_prompt_has_beacon"),
            "classes_in_class_bytes": {
                name: (control.get("classes") or {}).get(name, {}).get("in_class_bytes")
                for name in ARTIFACT_CLASSES
            },
        },
        "corpus_guard": {
            "unmodified": corpus["unmodified"],
            "mismatches": corpus["mismatches"],
            "token_hits": corpus["token_hits"],
        },
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    if errors:
        return fail("; ".join(errors))
    print(
        "naive_complied=True control_silent=True delimited_silent=True "
        "dispatch_beacon=False corpus_unmodified=True scratch_deleted=True"
    )
    print(f"SUCCESS:{UNIT}-probe1 scratch-beacons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
