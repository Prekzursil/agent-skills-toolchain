#!/usr/bin/env python3
"""Probe 1: adverse inference on unlicensed sources; planted copyleft fires.

Both-states: the same gate must stay silent (not ADVERSE) on an agreeing MIT
pair, and must not treat a README MIT badge as a licence blob.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus  # noqa: E402

gate = corpus.load_gate()
by_id = {r.source_id: r for r in gate.evaluate_many(corpus.planted_sources(gate))}

unlic = by_id["plant:plant-unlicensed"]
gpl = by_id["plant:plant-gpl3"]
mit = by_id["plant:plant-mit-agree"]

failures: list[str] = []

if unlic.classification != "ADVERSE-UNLICENSED":
    failures.append(f"unlicensed classification={unlic.classification}")
if unlic.ingest_mode not in {"MECHANISM_ONLY", "REFUSE"}:
    failures.append(f"unlicensed ingest_mode={unlic.ingest_mode}")
if unlic.code_carried:
    failures.append("unlicensed carried code")
if unlic.signal_a_spdx is not None:
    failures.append(f"unlicensed signal A leaked {unlic.signal_a_spdx}")
if unlic.readme_badge_spdx != "MIT":
    failures.append(f"badge not observed: {unlic.readme_badge_spdx}")
if unlic.readme_badge_used:
    failures.append("README badge was used for classification")
if unlic.signal_b_spdx != "MIT":
    failures.append(f"API MIT not recorded on B: {unlic.signal_b_spdx}")
if not any(o.get("kind") == "adverse-inference" for o in unlic.obligations):
    failures.append("missing adverse-inference obligation")

if gpl.classification != "COPYLEFT":
    failures.append(f"planted GPL classification={gpl.classification}")
if gpl.signal_a_spdx != "GPL-3.0":
    failures.append(f"planted GPL A={gpl.signal_a_spdx}")
if gpl.ingest_mode != "MECHANISM_ONLY":
    failures.append(f"planted GPL ingest_mode={gpl.ingest_mode}")
if gpl.code_carried:
    failures.append("planted GPL carried code")
if gpl.signals_agree is not True:
    failures.append(f"planted GPL signals_agree={gpl.signals_agree}")

if mit.classification == "ADVERSE-UNLICENSED":
    failures.append("agreeing MIT pair wrongly treated as unlicensed")
if mit.classification != "PERMISSIVE":
    failures.append(f"agreeing MIT classification={mit.classification}")
if mit.signals_agree is not True:
    failures.append(f"agreeing MIT signals_agree={mit.signals_agree}")
if mit.signal_a_spdx != "MIT" or mit.signal_b_spdx != "MIT":
    failures.append(f"agreeing MIT A/B={mit.signal_a_spdx}/{mit.signal_b_spdx}")

payload = {
    "probe": "probe1-adverse-and-restrictive",
    "unlicensed": unlic.as_dict(),
    "planted_gpl": gpl.as_dict(),
    "mit_agree_control": mit.as_dict(),
    "failures": failures,
    "ok": not failures,
}
print(json.dumps(payload, indent=2, sort_keys=True))
if failures:
    print("FAIL:" + "; ".join(failures))
    raise SystemExit(1)
print(
    "adverse_on_unlicensed=True badge_ignored=True "
    f"gpl_fired={gpl.classification} mit_agree={mit.classification}"
)
print("SUCCESS:WFA-0031-probe1 adverse inference and planted restrictive licence")
raise SystemExit(0)
