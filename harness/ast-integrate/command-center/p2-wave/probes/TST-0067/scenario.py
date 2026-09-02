#!/usr/bin/env python3
"""Shared measurements and receipt gate for TST-0067 named probes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/receipts/TST-0067.json"
SENTINEL = "SUCCESS:TST-0067"

from harness import (  # noqa: E402
    CONFIG_KEY,
    ENV_KEY,
    NEW,
    OLD,
    PROJECT_WRITE,
    ROOT_WRITE,
    measure_detector_control,
    measure_persistent_miss_and_session_hit,
    measure_wrong_scope_inert,
)


def require_receipt() -> dict[str, Any]:
    if not ART.is_file() or ART.stat().st_size <= 0:
        raise SystemExit("FAILED:TST-0067 receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:TST-0067 receipt not an object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:TST-0067 self-declared {st}")
    if SENTINEL not in text:
        raise SystemExit("FAILED:TST-0067 sentinel absent")
    if doc.get("unit_id") != "TST-0067":
        raise SystemExit(f"FAILED:TST-0067 unit_id {doc.get('unit_id')}")
    tests = doc.get("tests") or []
    ids = {t.get("id") for t in tests if isinstance(t, dict)}
    required = {
        "test_child_process_observes_the_new_value_in_the_same_session",
        "test_a_write_at_the_wrong_scope_is_detected_as_inert",
        "test_probe_reads_from_the_consumer_not_from_the_setter",
    }
    missing = sorted(required - ids)
    if missing:
        raise SystemExit(f"FAILED:TST-0067 tests missing {missing}")
    return doc


def pairs_from_receipt(doc: dict[str, Any]) -> dict[str, Any]:
    ev = doc.get("consumer_observation_pairs") or {}
    if not isinstance(ev, dict):
        raise SystemExit("FAILED:TST-0067 receipt pairs missing")
    return ev
