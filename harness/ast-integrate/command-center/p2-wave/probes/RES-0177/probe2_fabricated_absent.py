#!/usr/bin/env python3
"""Probe 2: fabricated name returns nothing; directory-noise mutant is killed.

A lister that reports every directory as a plugin would claim the planted
``xyzzy-not-installed-res0177`` directory is installed. The honest enumerator
requires plugin.json and therefore returns nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import enumerate as E  # noqa: E402
import estate as EST  # noqa: E402

ART = REPO / "command-center/research/teardown/RES-0177-teardown-installed-local-plugins.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0177-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0177-probe2 self-declared", doc.get("state"))
        return 1

    bundle = EST.load_estate()
    disk = E.disk_plugins(bundle["plugins_root"])
    listing = E.listing_plugins(bundle["listing_json"], bundle["listing_text"])
    fab = E.query(bundle["fabricated"], disk, listing)
    if fab["present"] or fab["disk"] or fab["listing"]:
        print("FAILED:RES-0177-probe2 fabricated name leaked into honest enumerator", fab)
        return 1
    if bundle["noise_dir"] in disk:
        print("FAILED:RES-0177-probe2 noise directory counted as a plugin")
        return 1

    mutant = E.mutant_directory_noise(bundle["plugins_root"])
    mutant_reports_fabricated = bundle["fabricated"] in mutant
    mutant_reports_noise = bundle["noise_dir"] in mutant
    if not mutant_reports_fabricated:
        print("FAILED:RES-0177-probe2 noise mutant did not report fabricated dir; control is inert")
        return 1
    if not mutant_reports_noise:
        print("FAILED:RES-0177-probe2 noise mutant did not report noise dir; control is inert")
        return 1

    recorded = doc.get("detector_control") or {}
    if recorded.get("fabricated_absent") is not True:
        print("FAILED:RES-0177-probe2 artifact missing fabricated_absent")
        return 1
    if recorded.get("noise_mutant_killed") is not True:
        print("FAILED:RES-0177-probe2 artifact missing noise_mutant_killed")
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-fabricated-absent",
        "unit_id": "RES-0177",
        "fabricated": bundle["fabricated"],
        "honest": fab,
        "noise_dir_on_disk_enumerator": bundle["noise_dir"] in disk,
        "mutant_reports_fabricated": mutant_reports_fabricated,
        "mutant_reports_noise": mutant_reports_noise,
        "mutant_killed": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"fabricated={bundle['fabricated']} honest_present={fab['present']} "
        f"mutant_killed={mutant_reports_fabricated}"
    )
    print("SUCCESS:RES-0177-probe2 fabricated name absent; directory-noise mutant killed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
