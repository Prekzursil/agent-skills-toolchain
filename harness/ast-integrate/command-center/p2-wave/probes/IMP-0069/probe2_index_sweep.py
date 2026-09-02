#!/usr/bin/env python3
"""IMP-0069 probe 2: independent sweep over the CURRENT index.

Mechanically different from probe 1: does not call validate_name, does not
read planted_collisions.json for the pass/fail loop, and tests a confusable
pair (Greek omicron vs Latin o) that is absent from the implementer's
fixture set. Live names that fail the grammar are reported, not enforced.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.independent_sweep import (  # noqa: E402
    HELDOUT_GREEK,
    HELDOUT_LATIN,
    independent_skeleton,
    sweep,
)

PLANTED_PATH = REPO / "tools/marketplace/fixtures/planted_collisions.json"
RECEIPT = REPO / "command-center/receipts/IMP-0069.json"
REAL = "agent-skills-toolchain"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0069-probe2 {msg}")
    return 1


def main() -> int:
    planted = json.loads(PLANTED_PATH.read_text(encoding="utf-8"))
    planted_blob = json.dumps(planted, ensure_ascii=False)
    if HELDOUT_GREEK in planted_blob or "omega-lib" in planted_blob:
        return fail("held-out pair leaked into implementer fixture set")
    if HELDOUT_GREEK.casefold() == HELDOUT_LATIN.casefold():
        return fail("held-out pair is a casefold collision, not confusable")
    if independent_skeleton(HELDOUT_GREEK) != independent_skeleton(HELDOUT_LATIN):
        return fail("held-out Greek omicron did not skeleton to Latin o")

    report = sweep()
    names = report["index"]["names"]
    if REAL not in names:
        return fail(f"current index missing {REAL}: {names}")
    if report["misfit_count"] != 0:
        return fail(f"live misfits {report['misfits']}")
    if not report["zero_live_rejected"]:
        return fail("a live name was enforced-rejected")
    if not report["heldout_confusable"]["skeletons_equal"]:
        return fail("held-out skeletons unequal")
    if not report["heldout_confusable"]["casefolds_differ"]:
        return fail("held-out casefolds unexpectedly equal")

    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt state {doc.get('state')}")
    if "SUCCESS:IMP-0069" not in text:
        return fail("sentinel-absent")

    out = {
        "probe": "probe2-index-sweep",
        "unit_id": "IMP-0069",
        "index_path": report["index"]["path"],
        "canonical_present": report["index"]["canonical_present"],
        "live_names": names,
        "misfit_count": report["misfit_count"],
        "heldout": report["heldout_confusable"]["note"],
        "heldout_collides": True,
        "independence": "marketplace.independent_sweep (no validate_name)",
        "pass": True,
    }
    print(json.dumps(out, ensure_ascii=False))
    print(
        f"index={out['index_path']} canonical={out['canonical_present']} "
        f"live={names} misfits={out['misfit_count']}"
    )
    print("SUCCESS:IMP-0069-probe2 independent current-index sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
