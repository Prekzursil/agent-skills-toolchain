#!/usr/bin/env python3
"""Refresh ADV-0127's static_audit block from the LIVE clock-class census.

The artifact is a point-in-time audit of the tools/ tree; the tree drifted
(368 -> 370 rows) after the prior builder session. This re-measures the census
now and rewrites ONLY the measured block, stamping refreshed_at/refresh_note
(schema root additionalProperties=true). Audit conclusions and the behavioral
section are untouched - probe2 re-verifies those live.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
HERE = REPO / "command-center" / "p2-wave" / "probes" / "ADV-0127"

spec = importlib.util.spec_from_file_location("adv0127_clock_lib", HERE / "clock_lib.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["adv0127_clock_lib"] = mod
spec.loader.exec_module(mod)

ART = REPO / mod.OUT_REL

doc = json.loads(ART.read_text(encoding="utf-8"))
recorded_keys = sorted((doc.get("static_audit") or {}).keys())
live = mod.production_census()

missing = [k for k in recorded_keys if k not in live]
if missing:
    print(f"FAILED:refresh live census missing recorded keys {missing}")
    raise SystemExit(1)
before_fp = doc["static_audit"].get("fingerprint_sha256")
doc["static_audit"] = {k: live[k] for k in recorded_keys}
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
doc["refreshed_at"] = now
doc["refresh_note"] = (
    "static_audit re-measured live this session (clock_lib.production_census): "
    "tools/ tree drifted after the prior builder session "
    f"(fingerprint {before_fp} -> {live['fingerprint_sha256']}, "
    f"rows {doc.get('n_rows_recorded', '?')} -> {live['n_rows']}). Behavioral "
    "section untouched; both named probes re-run live against this refresh."
)
ART.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
print(f"refreshed rows={live['n_rows']} counts={json.dumps(live['counts'])}")
print(f"fingerprint {before_fp} -> {live['fingerprint_sha256']}")
print(f"SUCCESS:ADV-0127 static_audit refreshed at {now}")
