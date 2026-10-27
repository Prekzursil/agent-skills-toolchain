#!/usr/bin/env python3
"""Probe 2: corrupt trust store + disable network, re-attempt install.

Mechanically different from probe 1. A verifier that skips verification when
the key source is unreachable fails open. apply_install never reads the store
and still accepts unsigned packages.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_degraded_trust  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0028-signature-verification-bypass.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def catalog_sentinel() -> str:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "ADV-0028":
            return str(unit.get("completion_sentinel") or "")
    return ""


def main() -> int:
    live = run_degraded_trust()
    print(
        json.dumps(
            {
                "probe": "probe2-degraded-trust-store",
                "unit_id": "ADV-0028",
                "trust_store_corrupted": live["trust_store_corrupted"],
                "trust_store_unread_by_installer": live[
                    "trust_store_unread_by_installer"
                ],
                "network_blocked": live["network_blocked"],
                "egress_attempts_during_install": live["egress_attempts_during_install"],
                "unsigned_accepted_while_degraded": live[
                    "unsigned_accepted_while_degraded"
                ],
                "truncated_accepted_while_degraded": live[
                    "truncated_accepted_while_degraded"
                ],
                "fail_open": live["fail_open"],
                "signature_api_present": live["source_scan"]["signature_api_present"],
            },
            indent=1,
            sort_keys=True,
        )
    )
    if not live["trust_store_corrupted"]:
        print("FAILED:ADV-0028-probe2 trust store was not corrupted")
        return 1
    if not live["trust_store_unread_by_installer"]:
        print("FAILED:ADV-0028-probe2 installer mutated or parsed the trust store")
        return 1
    if live["egress_attempts_during_install"]:
        print("FAILED:ADV-0028-probe2 installer attempted network during install")
        return 1
    if not live["fail_open"]:
        print("FAILED:ADV-0028-probe2 degraded environment refused unsigned install")
        return 1
    if live["source_scan"]["signature_api_present"]:
        print("FAILED:ADV-0028-probe2 unexpected signature API in installer source")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ADV-0028-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:ADV-0028-probe2 artifact unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:ADV-0028-probe2 self-declared {doc.get('state')}")
        return 1
    sentinel = catalog_sentinel()
    if not sentinel or sentinel not in text:
        print("FAILED:ADV-0028-probe2 sentinel absent")
        return 1
    rec = doc.get("probe2") or {}
    if rec.get("fail_open") is not True:
        print("FAILED:ADV-0028-probe2 artifact missing fail_open=true")
        return 1
    if rec.get("unsigned_accepted_while_degraded") is not True:
        print("FAILED:ADV-0028-probe2 artifact drift on unsigned degraded accept")
        return 1
    print("SUCCESS:ADV-0028-probe2 fail-open under corrupt trust store and blocked net")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
