#!/usr/bin/env python3
"""Probe 2: MCP enabled/disabled curation survives; already-current is a no-op.

Catalog tests:
  test_upgrade_preserves_enabled_disabled_curation
  test_upgrade_is_idempotent_when_already_current

Negative control: a wipe-on-schema-change mutant must fire; healthy upgrade stays silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from suite import (  # noqa: E402
    test_upgrade_is_idempotent_when_already_current,
    test_upgrade_preserves_enabled_disabled_curation,
    wipe_control,
)

UNIT = "TST-0071"
ART = REPO / "command-center/receipts/TST-0071.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def check_receipt() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if doc.get("unit_id") != UNIT:
        return f"unit_id={doc.get('unit_id')}"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {doc.get('state')}"
    if "SUCCESS:TST-0071" not in text:
        return "sentinel-absent"
    checks = {
        c.get("id"): c.get("result") for c in (doc.get("tests") or []) if isinstance(c, dict)
    }
    if checks.get("test_upgrade_preserves_enabled_disabled_curation") != "PASS":
        return f"receipt curation={checks.get('test_upgrade_preserves_enabled_disabled_curation')}"
    if checks.get("test_upgrade_is_idempotent_when_already_current") != "PASS":
        return f"receipt idempotent={checks.get('test_upgrade_is_idempotent_when_already_current')}"
    controls = doc.get("negative_controls") or []
    if not controls:
        return "receipt negative_controls empty"
    ctl = controls[0] if isinstance(controls[0], dict) else {}
    if not ctl.get("fired_on_bad_state") or not ctl.get("silent_on_good_state"):
        return f"receipt control both-states failed {ctl}"
    return None


def main() -> int:
    curation = test_upgrade_preserves_enabled_disabled_curation()
    if curation["result"] != "PASS":
        return fail(curation["detail"])
    idemp = test_upgrade_is_idempotent_when_already_current()
    if idemp["result"] != "PASS":
        return fail(idemp["detail"])
    control = wipe_control()
    if not control["ok"]:
        return fail(control["detail"])
    if not control["fired_on_bad_state"]:
        return fail("wipe mutant was silent (detector blind)")
    if not control["silent_on_good_state"]:
        return fail("healthy upgrade was not silent")
    err = check_receipt()
    if err:
        return fail(err)
    print(
        json.dumps(
            {
                "probe": "probe2-curation-and-idempotent",
                "unit_id": UNIT,
                "curation_preserved": True,
                "idempotent_when_current": True,
                "wipe_fired": True,
                "healthy_silent": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0071-probe2 curation preserved, idempotent current, wipe control fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
