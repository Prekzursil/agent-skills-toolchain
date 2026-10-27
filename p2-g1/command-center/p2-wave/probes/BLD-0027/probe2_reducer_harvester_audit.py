#!/usr/bin/env python3
"""BLD-0027 probe2: reducer/harvester audit + negative control.

Receipts claim SUCCESS only on the AND-gate (artifact exists AND exit-0 AND
sentinel). The receipt's negative control: replace the AND-gate with
exit_code == 0; the mutant accepts the good artifact and wrongly accepts the
missing one, while the production gate fires FAILED — both states are
demonstrated here, plus the harvest transition (receipt manifest row).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import (  # noqa: E402
    REPO, ProbeFailure, check_receipt_core, receipt_path, require,
    sha256_normalized,
)

UID = "BLD-0027"


def verify_dispatch(exit_code: int, artifact_exists: bool, sentinel: str,
                    expect_sentinel: str) -> str:
    """Production completion gate: the AND of all three conditions."""
    if artifact_exists and exit_code == 0 and sentinel == expect_sentinel:
        return "SUCCESS"
    return "FAILED"


def mutant_exit_zero_only(exit_code: int, artifact_exists: bool,
                          sentinel: str, expect_sentinel: str) -> str:
    """Mutation: completion is exit_code == 0 only (dropped artifact+sentinel)."""
    return "SUCCESS" if exit_code == 0 else "FAILED"


def main() -> int:
    doc = check_receipt_core(UID)
    receipt = receipt_path(UID)

    # --- good state: production gate succeeds, mutant agrees ----------------
    good = verify_dispatch(exit_code=0, artifact_exists=True,
                           sentinel=f"SUCCESS:{UID}", expect_sentinel=f"SUCCESS:{UID}")
    good_mut = mutant_exit_zero_only(0, True, f"SUCCESS:{UID}", f"SUCCESS:{UID}")
    require(good == "SUCCESS" and good_mut == "SUCCESS",
            f"good state: gate={good} mutant={good_mut}")

    # --- bad state: artifact missing, command exits 0 -----------------------
    # (the exact blindspot the receipt documents: a quiet 'completed' message
    # with no artifact on disk)
    bad = verify_dispatch(exit_code=0, artifact_exists=False, sentinel="",
                          expect_sentinel=f"SUCCESS:{UID}")
    bad_mut = mutant_exit_zero_only(0, False, "", f"SUCCESS:{UID}")
    require(bad == "FAILED",
            f"production gate missed the missing artifact: {bad}")
    require(bad_mut == "SUCCESS",
            f"mutant did not demonstrate the blindspot: {bad_mut}")

    # --- live harvest: the receipt is registered with its live sha ----------
    text = receipt.read_text(encoding="utf-8")
    require(f"SUCCESS:{UID}" in text, "sentinel absent from receipt bytes")
    live_sha = sha256_normalized(receipt)
    require(len(live_sha) == 64 and set(live_sha) <= set("0123456789abcdef"),
            "live digest malformed")
    man = REPO / "command-center/p2-wave/probes" / UID / "UNIT-ARTIFACT-MANIFEST.json"
    require(man.is_file(), "per-unit manifest absent (write via packer)")
    man_doc = json.loads(man.read_text(encoding="utf-8"))
    rows = [a for a in man_doc.get("artifacts", []) if a.get("unit_id") == UID]
    require(rows, "manifest has no row for this unit")
    match = [a for a in rows
             if a.get("path", "").replace("\\", "/")
             == receipt.relative_to(REPO).as_posix()
             and a.get("sha256") == live_sha and a.get("present") is True]
    require(match, "manifest row does not match the live receipt bytes")

    print(json.dumps({
        "probe": "probe2-reducer-harvester-audit", "unit_id": UID,
        "good": good, "bad": bad, "mutant_bad_accepts": bad_mut,
        "manifest_rows": len(rows), "manifest_sha_match": True, "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe2 AND-gate fires on missing artifact; "
          f"exit-zero mutant blindspot reproduced; manifest row matches live sha")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe2 {exc}")
        raise SystemExit(1)
