#!/usr/bin/env python3
"""Probe 2: independent reviewer race + quiescent BASELINE + rollback + nine classes."""
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
    print(f"FAILED:CC-0010-probe2 {msg}")
    return 1


def main() -> int:
    payload = L.probe2_payload()
    print(L.dumps(payload))
    if not payload.get("ok"):
        return fail("combined reviewer/baseline/rollback control failed")
    race = payload["independent_race"]
    if race.get("verdict") != "SAMPLE" or not race.get("ok"):
        return fail(f"independent race {race}")
    base = payload["quiescent_baseline"]
    if base.get("verdict") != "BASELINE" or not base.get("ok"):
        return fail(f"quiescent baseline {base}")
    if base.get("independent_signal_count") != 2:
        return fail("BASELINE without two independent quiescence signals")
    if base.get("working_tree_measurements") != "SAMPLE":
        return fail("working-tree measurements were not tagged SAMPLE")
    if list(base.get("class_ids") or []) != list(L.NINE_CLASSES):
        return fail(f"class ids {base.get('class_ids')}")
    rb = payload["rollback_rehearsal"]
    if not rb.get("ok") or rb.get("digests_reproduced") is not True:
        return fail(f"rollback rehearsal {rb}")

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
        "probe",
        "unit_id",
        "independent_race",
        "quiescent_baseline",
        "rollback_rehearsal",
        "nine_classes",
        "ok",
    ):
        if stored_doc.get(key) != payload.get(key):
            return fail(f"artifact drift on {key}")

    live = doc.get("live_freeze") or {}
    if live.get("verdict") == "BASELINE" and not (doc.get("live_freeze") or {}).get("quiescence", {}).get(
        "is_git_work_tree"
    ):
        return fail("live freeze claimed BASELINE on a non-git worktree")
    pin = (live.get("program_anchor") or {}).get("pin")
    if pin != L.PROGRAM_ANCHOR_PREFIX:
        return fail(f"program pin {pin}")
    print(
        "SUCCESS:CC-0010-probe2 reviewer-race SAMPLE "
        f"baseline={base.get('verdict')} rollback={rb.get('digests_reproduced')} "
        f"classes={len(base.get('class_ids') or [])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
