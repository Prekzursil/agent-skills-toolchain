#!/usr/bin/env python3
"""Probe 1: upgrade from each supported prior version with zero user-key loss.

Catalog test: test_upgrade_from_each_supported_version.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from suite import test_upgrade_from_each_supported_version  # noqa: E402
from upgrade import CURRENT_VERSION, SUPPORTED_PRIOR  # noqa: E402

UNIT = "TST-0071"
ART = REPO / "command-center/receipts/TST-0071.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def check_receipt(diffs: list[dict]) -> str | None:
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
    if checks.get("test_upgrade_from_each_supported_version") != "PASS":
        return f"receipt check each-version={checks.get('test_upgrade_from_each_supported_version')}"
    recorded = doc.get("version_diffs") or []
    if len(recorded) < 2:
        return f"receipt version_diffs={len(recorded)}"
    if any(not row.get("zero_loss") for row in recorded if isinstance(row, dict)):
        return "receipt version_diffs not all zero_loss"
    live_from = {str(d.get("from_version")) for d in diffs}
    rec_from = {str(r.get("from_version")) for r in recorded if isinstance(r, dict)}
    if live_from - rec_from:
        return f"receipt missing diffs for {sorted(live_from - rec_from)}"
    return None


def main() -> int:
    row = test_upgrade_from_each_supported_version()
    if row["result"] != "PASS":
        return fail(row["detail"])
    diffs = row["version_diffs"]
    if len(diffs) != len(SUPPORTED_PRIOR):
        return fail(f"expected {len(SUPPORTED_PRIOR)} diffs, got {len(diffs)}")
    for diff in diffs:
        if not diff.get("zero_loss"):
            return fail(f"v{diff.get('from_version')} lost {diff.get('lost_user_keys')}")
        if diff.get("to_version") != CURRENT_VERSION:
            return fail(f"landed at {diff.get('to_version')}")
        if not diff.get("relocations"):
            return fail(f"v{diff.get('from_version')} recorded no relocations")
    err = check_receipt(diffs)
    if err:
        return fail(err)
    print(
        json.dumps(
            {
                "probe": "probe1-upgrade-from-each-version",
                "unit_id": UNIT,
                "supported_prior": list(SUPPORTED_PRIOR),
                "current_version": CURRENT_VERSION,
                "zero_loss": True,
                "diff_count": len(diffs),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0071-probe1 upgrade from each supported prior version is zero-loss")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
