#!/usr/bin/env python3
"""Probe 1: clean install on a fresh Windows-layout profile; process-level fire."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402

from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    DECLARED_HOOKS,
    OUTPUT_REL,
    SCHEMA_REL,
    UNIT_ID,
)
from scenario import run_clean_install, three_states_distinguished  # noqa: E402


def main() -> int:
    art_path = REPO / OUTPUT_REL
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        print("FAILED:CNF-0096-probe1 artifact missing")
        return 1
    text = art_path.read_text(encoding="utf-8")
    if COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0096-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    if doc.get("unit_id") != UNIT_ID:
        print("FAILED:CNF-0096-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0096-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0096-p1-") as tmp_s:
        live = run_clean_install(Path(tmp_s))

    rows = live["hooks"]
    declared = [h["id"] for h in DECLARED_HOOKS]
    if [r["id"] for r in rows] != declared:
        print("FAILED:CNF-0096-probe1 declared mismatch", [r["id"] for r in rows])
        return 1
    if not three_states_distinguished(rows):
        print("FAILED:CNF-0096-probe1 states not distinguished")
        return 1
    missing = [r["id"] for r in rows if not (r["installed"] and r["loaded"] and r["fired"])]
    if missing:
        print("FAILED:CNF-0096-probe1 not installed+loaded+fired", missing)
        return 1
    if not live["profile"]["empty_at_start"]:
        print("FAILED:CNF-0096-probe1 profile not empty at start", live["profile"]["pre_install_contamination"])
        return 1
    if not live["health"]["process_healthy"]:
        print("FAILED:CNF-0096-probe1 process health not green")
        return 1
    if live["health"]["zero_hooks_fired"]:
        print("FAILED:CNF-0096-probe1 zero hooks fired")
        return 1
    for row in rows:
        side = row.get("side_effect") or {}
        if not side.get("distinct_process"):
            print("FAILED:CNF-0096-probe1 side effect not a distinct process", row["id"])
            return 1
        if int(side.get("pid") or 0) == int(side.get("parent_pid") or 0):
            print("FAILED:CNF-0096-probe1 pid==parent", row["id"])
            return 1
        if row.get("not_observed") is not None:
            print("FAILED:CNF-0096-probe1 unexpected not_observed", row)
            return 1

    art_ids = [h.get("id") for h in doc.get("hooks") or []]
    if art_ids != declared:
        print("FAILED:CNF-0096-probe1 artifact hook ids", art_ids)
        return 1
    if not all(h.get("fired") for h in doc.get("hooks") or []):
        print("FAILED:CNF-0096-probe1 artifact clean hooks not all fired")
        return 1
    if not (doc.get("removal_control") or {}).get("detected"):
        print("FAILED:CNF-0096-probe1 artifact missing removal_control.detected")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-clean-install",
                "unit_id": UNIT_ID,
                "empty_at_start": True,
                "fired": [r["id"] for r in rows],
                "process_healthy": True,
                "distinct_pids": [ (r["id"], r["side_effect"]["pid"]) for r in rows ],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0096-probe1 clean install hooks fired at process level")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
