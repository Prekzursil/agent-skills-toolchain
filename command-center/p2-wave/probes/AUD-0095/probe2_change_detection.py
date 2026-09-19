#!/usr/bin/env python3
"""Probe 2: change-detection check with both-states control.

Mechanically different from probe 1 (which only hashes). Modifies one frozen
file in a scratch copy without a version bump and requires RED; bumps the
version with a matching migration and requires GREEN. A non-frozen decoy must
stay silent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import OUT_REL, REPO, SENTINEL, UNIT  # noqa: E402
from detector import run_both_states  # noqa: E402
from inventory import enumerate_freeze_set  # noqa: E402

ART = REPO / OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    rows = enumerate_freeze_set(REPO)["inventory"]
    both = run_both_states(REPO, rows)
    print(
        json.dumps(
            {
                "probe": "probe2-change-detection",
                "pass": both["pass"],
                "target_path": both["target_path"],
                "unversioned_edit_red": both["unversioned_edit_red"],
                "version_bump_green": both["version_bump_green"],
                "non_frozen_silent": both["non_frozen_silent"],
                "verbatim_unversioned": both["verbatim_unversioned"],
                "verbatim_migrated": both["verbatim_migrated"],
                "verbatim_silent": both["verbatim_silent"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not both["unversioned_edit_red"]:
        return fail("unversioned frozen-file edit did not turn the check red")
    if not both["version_bump_green"]:
        return fail("version bump plus migration did not turn the check green")
    if not both["non_frozen_silent"]:
        return fail("non-frozen decoy mutation was not silent")
    if not both["pass"]:
        return fail("both-states failed")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    # Same artifact-level scoping as probe1: BLOCKED-on-review is a unit
    # state; FAILED/SEVERED/TIMEOUT mean the artifact claim itself failed.
    if str(doc.get("state") or "").upper() in {"FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    domain = (doc.get("extensions") or {}).get("domain") or {}
    recorded = domain.get("both_states") or doc.get("both_states") or {}
    det = domain.get("freeze_detector") or doc.get("freeze_detector") or {}
    if recorded.get("unversioned_edit_red") is not True:
        return fail("artifact both_states.unversioned_edit_red not true")
    if recorded.get("version_bump_green") is not True:
        return fail("artifact both_states.version_bump_green not true")
    if recorded.get("non_frozen_silent") is not True:
        return fail("artifact both_states.non_frozen_silent not true")
    if det.get("tested") is not True:
        return fail("artifact freeze_detector.tested not true")
    print(
        f"SUCCESS:{UNIT}-probe2 both-states unversioned-red bump-green non-frozen-silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
