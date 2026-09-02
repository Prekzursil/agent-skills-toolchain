#!/usr/bin/env python3
"""Probe 1: known-present one-byte fire, both-states clean, hygiene plants."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402
from scenario import assert_scenario, run_scenario  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0145.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:CNF-0145-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if L.SENTINEL not in text:
        print("FAILED:CNF-0145-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != L.UNIT or doc.get("state") != "SUCCESS":
        print("FAILED:CNF-0145-probe1 unit/state", doc.get("unit_id"), doc.get("state"))
        return 1
    errs = L.validate_report(doc)
    if errs:
        print("FAILED:CNF-0145-probe1 schema", errs[:8])
        return 1
    if not L.schema_rejects_garbage():
        print("FAILED:CNF-0145-probe1 schema accepted garbage")
        return 1

    live = run_scenario()
    live_errs = assert_scenario(live)
    if live_errs:
        print("FAILED:CNF-0145-probe1 live", live_errs)
        return 1

    art_rel = (doc.get("sha256_sets") or {}).get("released") or {}
    live_rel = live["sha256_sets"]["released"]
    if art_rel.get("archive_sha256") != live_rel["archive_sha256"]:
        print("FAILED:CNF-0145-probe1 released archive sha drift")
        print(" artifact", art_rel.get("archive_sha256"))
        print(" live", live_rel["archive_sha256"])
        return 1
    if art_rel.get("member_sha256") != live_rel["member_sha256"]:
        print("FAILED:CNF-0145-probe1 released member sha set drift")
        return 1
    art_reb = (doc.get("sha256_sets") or {}).get("rebuild") or {}
    live_reb = live["sha256_sets"]["rebuild"]
    if art_reb.get("archive_sha256") != live_reb["archive_sha256"]:
        print("FAILED:CNF-0145-probe1 rebuild archive sha drift")
        return 1

    if not doc.get("controls", {}).get("known_present_one_byte", {}).get("fired"):
        print("FAILED:CNF-0145-probe1 artifact known-present silent")
        return 1
    if not live["known_present"]["fired"]:
        print("FAILED:CNF-0145-probe1 live known-present silent")
        return 1
    if not live["both_states"]["normalized_identical"]:
        print("FAILED:CNF-0145-probe1 unmutated not clean")
        return 1
    hyg = live["package_hygiene"]
    if not hyg["planted_found"] or not hyg["clean_archive"]:
        print("FAILED:CNF-0145-probe1 hygiene", hyg)
        return 1
    if SYNTHETIC_LEAK(doc) or SYNTHETIC_LEAK(hyg):
        print("FAILED:CNF-0145-probe1 synthetic credential body leaked into artifact")
        return 1

    print(
        "known_present=True both_states_clean=True hygiene_plants="
        f"{hyg['classes_found']} archive_sha={live_rel['archive_sha256'][:12]}"
    )
    print("SUCCESS:CNF-0145-probe1 mutation hygiene both-states")
    return 0


def SYNTHETIC_LEAK(obj: object) -> bool:
    blob = json.dumps(obj)
    return L.SYNTHETIC_CREDENTIAL in blob


if __name__ == "__main__":
    raise SystemExit(main())
