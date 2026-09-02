#!/usr/bin/env python3
"""Probe 1: broken install, same-version fix, reinstall observes FIXED.

Also re-runs per-file key mutation and explicit invalidation — the three
catalog tests_required for TST-0080.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0080.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = "SUCCESS:TST-0080"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0080-probe1 {msg}")
    return 1


def main() -> int:
    reinstall = S.test_fixed_package_is_observed_after_reinstall()
    per_file = S.test_cache_key_changes_when_any_shipped_byte_changes()
    invalidate = S.test_explicit_cache_invalidation_works()
    printable = {
        "reinstall": {k: reinstall[k] for k in sorted(reinstall) if k != "pass"},
        "per_file": {k: per_file[k] for k in sorted(per_file) if k != "pass"},
        "invalidate": {k: invalidate[k] for k in sorted(invalidate) if k != "pass"},
    }
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])
    if not reinstall.get("pass"):
        return fail("fixed package was not observed after reinstall")
    if not per_file.get("pass") or not per_file.get("all_files_change_key"):
        return fail("a shipped-byte mutation did not change the cache key")
    if not invalidate.get("pass"):
        return fail("explicit invalidation did not drop and rebuild the cas entry")
    print(
        f"reinstall broken={reinstall['first']['behavior']} "
        f"fixed={reinstall['second']['behavior']} "
        f"keys_differ={reinstall['keys_differ']} "
        f"files={per_file['file_count']} "
        f"invalidated={invalidate['dropped']['count']}"
    )
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if SENTINEL not in text:
            return fail("catalog sentinel absent from artifact")
        if doc.get("fixed_package_observed_after_reinstall") is not True:
            return fail("artifact fixed_package_observed_after_reinstall is not true")
        if doc.get("cache_key_changes_on_any_shipped_byte") is not True:
            return fail("artifact cache_key_changes_on_any_shipped_byte is not true")
        if doc.get("explicit_invalidation_works") is not True:
            return fail("artifact explicit_invalidation_works is not true")
        deriv = doc.get("cache_key_derivation") or {}
        if not deriv.get("file") or not deriv.get("line") or not deriv.get("quote"):
            return fail("artifact cache_key_derivation missing file:line quote")
        if "derive_cache_key" not in str(deriv.get("symbol") or "") and (
            "derive_cache_key" not in str(deriv.get("quote") or "")
        ):
            return fail("artifact derivation quote does not name derive_cache_key")
    print("SUCCESS:TST-0080-probe1 fixed package observed after reinstall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
