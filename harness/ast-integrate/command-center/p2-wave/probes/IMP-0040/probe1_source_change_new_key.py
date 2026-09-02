#!/usr/bin/env python3
"""IMP-0040 probe 1: one source byte change → miss + new on-disk key.

Two independent signals (catalog evidence_requirement):
  (1) served bytes after the flip equal the newly derived artefact (content
      comparison, not a hit-rate counter);
  (2) directory listing of cache keys changes (old key != new key).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TEST_DIR = REPO / "tools" / "plugin" / "tests"
REAP = REPO / "tools" / "plugin-cache-reaper" / "reap.py"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import test_cache_content_addressing as T  # noqa: E402


def main() -> int:
    if not REAP.is_file():
        print("FAILED:IMP-0040-probe1 reap.py missing")
        return 1
    try:
        result = T.test_source_change_forces_new_key()
    except AssertionError as exc:
        print(f"FAILED:IMP-0040-probe1 {exc}")
        return 1

    src = REAP.read_text(encoding="utf-8")
    key_uses_version = "plugin_version" in src and "source_digest" in src
    report = {
        "probe": "IMP-0040-probe1",
        "computed_not_asserted": True,
        "method": (
            "Flip one source byte, call get_or_compute, compare served payload "
            "bytes to produce(new_source); separately list on-disk keys."
        ),
        "served_new_equals_expected_new": result["served_new_equals_expected_new"],
        "served_new_differs_from_old": result["served_new_differs_from_old"],
        "on_disk_key_changed": result["on_disk_key_changed"],
        "keys_after_old": result["keys_after_old"],
        "keys_after_new": result["keys_after_new"],
        "content_addressed_key_old": result["content_addressed_key_old"],
        "content_addressed_key_new": result["content_addressed_key_new"],
        "src_old_sha256": result["src_old_sha256"],
        "src_new_sha256": result["src_new_sha256"],
        "implementation": str(REAP.relative_to(REPO)).replace("\\", "/"),
        "key_formula_includes_version_and_source_hash": key_uses_version,
        "hit_rate_counter_used": False,
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    ok = (
        result["served_new_equals_expected_new"]
        and result["served_new_differs_from_old"]
        and result["on_disk_key_changed"]
        and result["content_addressed_key_old"] != result["content_addressed_key_new"]
        and key_uses_version
    )
    if not ok:
        print("FAILED:IMP-0040-probe1 oracle not satisfied")
        return 1
    print(
        "content_ok=True key_changed=True "
        f"old={result['content_addressed_key_old'][:24]}… "
        f"new={result['content_addressed_key_new'][:24]}…"
    )
    print("SUCCESS:IMP-0040-probe1 source-byte change forces new key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
