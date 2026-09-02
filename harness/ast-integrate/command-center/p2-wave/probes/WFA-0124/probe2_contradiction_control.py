#!/usr/bin/env python3
"""Named probe 2: reviewer re-runs contradiction and flagship controls.

A NATIVE self-declaration that fails IR load must surface as a contradiction.
A claimed flagship without e2e must be demoted. Category-label remaining work
must be rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0124-blueprint-executability-gap.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0124-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0124":
        print("FAILED:WFA-0124-probe2 unit_id", doc.get("unit_id"))
        return 1

    controls = M.detector_controls()
    if not controls["pass"]:
        print("FAILED:WFA-0124-probe2 detector control did not pass")
        slim = {k: v for k, v in controls.items() if k != "rows"}
        print(json.dumps(slim, indent=2, default=str)[:4000])
        return 1
    if not controls["fired_on_bad_state"]:
        print("FAILED:WFA-0124-probe2 did not fire on known-broken fixtures")
        return 1
    if not controls["silent_on_good_state"]:
        print("FAILED:WFA-0124-probe2 good executable/flagship/discovery was not silent")
        return 1
    if not controls["native_contradiction_fired"]:
        print("FAILED:WFA-0124-probe2 NATIVE-unloadable contradiction not surfaced")
        return 1
    if not controls["flagship_claimed_demoted"]:
        print("FAILED:WFA-0124-probe2 claimed flagship without e2e was not demoted")
        return 1
    if not controls["vague_mutant_rejected"]:
        print("FAILED:WFA-0124-probe2 category-label remaining work was accepted")
        return 1
    if controls["mutant_declared_flagship_count"] == controls["identified_flagship_count"]:
        print("FAILED:WFA-0124-probe2 declared-flagship mutant matches identified count")
        return 1
    if not M.every_row_complete(controls["rows"]):
        print("FAILED:WFA-0124-probe2 fixture row incomplete")
        return 1

    art_dc = doc.get("detector_controls") or {}
    if art_dc.get("fixture_measured_executable_count") != controls[
        "fixture_measured_executable_count"
    ]:
        print("FAILED:WFA-0124-probe2 artifact fixture measured mismatch")
        return 1
    if list(art_dc.get("fixture_flagship_identified") or []) != list(
        controls["fixture_flagship_identified"]
    ):
        print("FAILED:WFA-0124-probe2 artifact flagship identified mismatch")
        return 1

    payload = {
        "probe": "probe2-contradiction-control",
        "unit_id": "WFA-0124",
        "pass": True,
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "fixture_measured_executable_count": controls["fixture_measured_executable_count"],
        "fixture_catalog_claim": controls["fixture_catalog_claim"],
        "fixture_flagship_identified": controls["fixture_flagship_identified"],
        "native_contradiction_fired": True,
        "flagship_claimed_demoted": True,
        "vague_mutant_rejected": True,
        "no_artifact_classified_failure": controls["no_artifact_classified_failure"],
        "load_error_classified": controls["load_error_classified"],
        "discovery_consistent": controls["discovery_consistent"],
        "reviewer": "WFA-0124-probe2-contradiction-control",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"fx_measured={controls['fixture_measured_executable_count']} "
        f"fx_claim={controls['fixture_catalog_claim']} "
        f"flagship={controls['fixture_flagship_identified']} "
        f"native_contra={controls['native_contradiction_fired']} "
        f"demoted={controls['flagship_claimed_demoted']}"
    )
    print("SUCCESS:WFA-0124-probe2 contradiction and flagship detector controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
