#!/usr/bin/env python3
"""Probe 2: attribution + rider obligations; A/B disagreement is UNCLASSIFIED.

Both-states: agreeing MIT is classified, not UNCLASSIFIED. Disagreement is
not resolved by preferring the file or the API.
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

apache = by_id["plant:plant-apache2"]
rider = by_id["plant:plant-rider"]
disagree = by_id["plant:plant-disagree"]
agree = by_id["plant:plant-mit-agree"]
tos = by_id["plant:plant-tos-evade"]

failures: list[str] = []

attr_kinds = {o.get("kind") for o in apache.obligations}
if "attribution-required" not in attr_kinds:
    failures.append(f"apache missing attribution obligations: {attr_kinds}")
if apache.signal_a_spdx != "Apache-2.0":
    failures.append(f"apache A={apache.signal_a_spdx}")
if apache.classification != "PERMISSIVE":
    failures.append(f"apache classification={apache.classification}")

if rider.classification != "RIDER-RESTRICTED":
    failures.append(f"rider classification={rider.classification}")
if not rider.riders:
    failures.append("rider produced no rider records")
verbatim = " ".join(r.get("verbatim") or "" for r in rider.riders)
if "Commons Clause" not in verbatim and "Sell the Software" not in verbatim:
    failures.append("rider verbatim missing Commons Clause text")
if not any(o.get("kind") == "rider-restricted" for o in rider.obligations):
    failures.append("rider missing rider-restricted obligation")
if rider.ingest_mode != "MECHANISM_ONLY":
    failures.append(f"rider ingest_mode={rider.ingest_mode}")
if rider.code_carried:
    failures.append("rider carried code")

if disagree.classification != "UNCLASSIFIED":
    failures.append(f"disagreement classification={disagree.classification}")
if disagree.signals_agree is not False:
    failures.append(f"disagreement signals_agree={disagree.signals_agree}")
if disagree.signal_a_spdx != "MIT" or disagree.signal_b_spdx != "Apache-2.0":
    failures.append(
        f"disagreement A/B={disagree.signal_a_spdx}/{disagree.signal_b_spdx}"
    )
if disagree.ingest_mode != "MECHANISM_ONLY":
    failures.append(f"disagreement ingest_mode={disagree.ingest_mode}")
if not disagree.escalated:
    failures.append("disagreement not escalated")
# Must not silently prefer A or B.
if disagree.classification in {"PERMISSIVE", "CUSTOM"}:
    failures.append("disagreement resolved by preference")

if agree.classification == "UNCLASSIFIED":
    failures.append("agreeing MIT wrongly UNCLASSIFIED")
if agree.signals_agree is not True:
    failures.append(f"agreeing MIT signals_agree={agree.signals_agree}")

if tos.classification != "REFUSED-TOS":
    failures.append(f"ToS/Tor plant classification={tos.classification}")
if tos.ingest_mode != "REFUSE":
    failures.append(f"ToS/Tor ingest_mode={tos.ingest_mode}")

payload = {
    "probe": "probe2-obligations-and-disagreement",
    "apache": apache.as_dict(),
    "rider": rider.as_dict(),
    "disagreement": disagree.as_dict(),
    "mit_agree_control": agree.as_dict(),
    "tos_tor": tos.as_dict(),
    "failures": failures,
    "ok": not failures,
}
print(json.dumps(payload, indent=2, sort_keys=True))
if failures:
    print("FAIL:" + "; ".join(failures))
    raise SystemExit(1)
print(
    "apache_obligations=True rider_verbatim=True "
    f"disagree={disagree.classification} agree={agree.classification} "
    f"tos={tos.classification}"
)
print("SUCCESS:WFA-0031-probe2 obligations, riders, and unclassified disagreement")
raise SystemExit(0)
