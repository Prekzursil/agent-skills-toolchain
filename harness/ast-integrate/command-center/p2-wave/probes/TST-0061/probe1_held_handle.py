#!/usr/bin/env python3
"""Named probe 1: held-handle update is atomic or loudly refused; rollback
leaves no partial tree. Naive sequential replace is the red detector control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from measure import (  # noqa: E402
    detector_control_naive_uninstall_partial,
    detector_control_naive_update_mixes,
    rename_then_write_completes,
    test_rollback_with_held_handle_leaves_no_partial_tree,
    test_update_with_held_handle_is_atomic_or_loudly_refused,
)

ART = REPO / "command-center/receipts/TST-0061.json"
SENTINEL = "SUCCESS:TST-0061"


def _check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size < 200:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    uid = doc.get("unit_id") or doc.get("id")
    if uid != "TST-0061":
        return f"unit_id {uid}"
    if SENTINEL not in text:
        return "sentinel absent"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {st}"
    return None


def main() -> int:
    err = _check_receipt()
    if err:
        print(f"FAILED:TST-0061-probe1 {err}")
        return 1

    update = test_update_with_held_handle_is_atomic_or_loudly_refused()
    rollback = test_rollback_with_held_handle_leaves_no_partial_tree()
    naive = detector_control_naive_update_mixes()
    naive_un = detector_control_naive_uninstall_partial()
    rename = rename_then_write_completes()

    if update["result"] != "PASS":
        print("FAILED:TST-0061-probe1 update held-handle")
        print(json.dumps(update, indent=2, default=str)[:4000])
        return 1
    if rollback["result"] != "PASS" or rollback.get("partial_tree"):
        print("FAILED:TST-0061-probe1 rollback partial tree")
        print(json.dumps(rollback, indent=2, default=str)[:4000])
        return 1
    if not naive.get("fired_on_bad_state"):
        print("FAILED:TST-0061-probe1 naive control did not go red")
        print(json.dumps(naive, indent=2, default=str)[:4000])
        return 1
    if not naive_un.get("fired_on_bad_state"):
        print("FAILED:TST-0061-probe1 naive uninstall control did not go red")
        print(json.dumps(naive_un, indent=2, default=str)[:4000])
        return 1
    if rename["result"] != "PASS":
        print("FAILED:TST-0061-probe1 rename-then-write")
        print(json.dumps(rename, indent=2, default=str)[:4000])
        return 1

    summary = {
        "probe": "probe1-held-handle",
        "unit_id": "TST-0061",
        "pass": True,
        "update_refused_unchanged": True,
        "rollback_no_partial_tree": True,
        "naive_update_mixed": True,
        "naive_uninstall_partial": True,
        "rename_then_write_atomic": True,
        "inventories": {
            "update_pre_count": len(update["inventory_pre"]),
            "update_post_count": len(update["inventory_post"]),
            "rollback_pre_count": len(rollback["inventory_pre"]),
            "rollback_post_count": len(rollback["inventory_post"]),
        },
        "naive_classify": naive["classify"],
        "held_kinds": ["hook", "log"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "SUCCESS:TST-0061-probe1 held-handle update refused with tree "
        "unchanged; rollback left no partial tree; naive control mixed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
