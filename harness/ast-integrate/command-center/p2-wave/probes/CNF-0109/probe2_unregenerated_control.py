#!/usr/bin/env python3
"""Named probe 2: unregenerated-SBOM control (mechanically different from probe 1).

Start from a wheel that matches the lockfile-derived SBOM, then add one dist to
the wheel without regenerating the SBOM. Artifact inspection must see the plant;
a lockfile re-read (the circular method) must miss it.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    PLANTED,
    closure_from_wheel,
    diff_sets,
    generate_sbom_from_lockfile,
    key,
    parse_lockfile,
    parse_sbom,
    plant_into_wheel,
    write_lockfile,
    write_wheel,
)

ART = REPO / "command-center/confirmation/CNF-0109-sbom-completeness.json"
PLANTED_KEY = key(*PLANTED)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cnf0109-p2-") as tmp:
        root = Path(tmp)
        wheel = write_wheel(
            root / "cnf0109_plugin-1.0.0-py3-none-any.whl", include_planted=False
        )
        lock = write_lockfile(root / "declared-lock.txt")
        sbom = generate_sbom_from_lockfile(lock, root / "sbom.cdx.json")
        sbom_set = parse_sbom(sbom)
        lock_set = parse_lockfile(lock)
        sbom_mtime = sbom.stat().st_mtime_ns
        sbom_bytes = sbom.read_bytes()

        before_clos = closure_from_wheel(wheel)
        before = diff_sets(before_clos.components, sbom_set)
        if PLANTED_KEY in before.artifact_only:
            print("FAILED:CNF-0109-probe2 planted already absent-from-sbom before plant")
            return 1
        if PLANTED_KEY in before_clos.components:
            print("FAILED:CNF-0109-probe2 planted already in wheel before plant")
            return 1

        plant_into_wheel(wheel)
        if sbom.stat().st_mtime_ns != sbom_mtime or sbom.read_bytes() != sbom_bytes:
            print("FAILED:CNF-0109-probe2 SBOM was regenerated (control invalid)")
            return 1

        after_clos = closure_from_wheel(wheel)
        after = diff_sets(after_clos.components, parse_sbom(sbom))
        circular = diff_sets(lock_set, parse_sbom(sbom))

    if PLANTED_KEY not in after_clos.components:
        print("FAILED:CNF-0109-probe2 planted not in post-plant artifact closure")
        return 1
    if PLANTED_KEY not in after.artifact_only:
        print("FAILED:CNF-0109-probe2 comparison missed unregenerated plant")
        return 1
    if PLANTED_KEY in circular.artifact_only:
        print("FAILED:CNF-0109-probe2 lockfile method unexpectedly saw the plant")
        return 1
    if PLANTED_KEY in lock_set:
        print("FAILED:CNF-0109-probe2 plant leaked into the declared lockfile")
        return 1
    # both-states: artifact method fires; circular lockfile method stays silent
    fired_on_artifact = PLANTED_KEY in after.artifact_only
    silent_on_circular = PLANTED_KEY not in circular.artifact_only
    if not (fired_on_artifact and silent_on_circular):
        print("FAILED:CNF-0109-probe2 both-states control")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0109-probe2 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ctrl = doc.get("unregenerated_sbom_control") or {}
    if ctrl.get("detected") is not True:
        print("FAILED:CNF-0109-probe2 artifact did not record control detection")
        return 1
    planted = ctrl.get("planted_component") or {}
    if key(str(planted.get("name") or ""), str(planted.get("version") or "")) != PLANTED_KEY:
        print("FAILED:CNF-0109-probe2 planted_component mismatch", planted)
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0109-probe2 self-declared", doc.get("state"))
        return 1

    payload = {
        "before_absent": before.ships_but_absent,
        "after_absent": after.ships_but_absent,
        "circular_absent": circular.ships_but_absent,
        "fired_on_artifact": fired_on_artifact,
        "silent_on_circular_lockfile_method": silent_on_circular,
        "sbom_untouched": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"control_detected=True circular_misses_plant=True "
        f"planted={PLANTED[0]}@{PLANTED[1]}"
    )
    print("SUCCESS:CNF-0109-probe2 unregenerated-SBOM control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
