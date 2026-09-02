#!/usr/bin/env python3
"""Probe 2: both-states content-changing rename + lowercase-keyed copy must fail.

Independent of probe 1 (fresh destination, different source blob). Also records
the write-then-delete drop that a case-insensitive dest exhibits if sync is
not case-aware — the failure class this unit exists to catch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from sync import (  # noqa: E402
    BLOB_B,
    NEW_REL,
    run_content_change,
    run_lowercase_copy_must_fail,
    run_naive_drop,
    sha256_bytes,
)

OUT = HERE / "probe2-both-states.raw.json"


def main() -> int:
    content = run_content_change()
    negative = run_lowercase_copy_must_fail()
    drop = run_naive_drop()
    ok = bool(content["ok"] and negative["ok"] and drop["ok"])
    payload = {
        "probe": "probe2-both-states-and-negative",
        "unit_id": "TST-0196",
        "content_changing_rename": {
            "ok": content["ok"],
            "listing": content["check"]["listing"],
            "dest_sha256": content["check"]["dest_sha256"],
            "source_sha256": sha256_bytes(BLOB_B),
            "old_content_absent": content["old_content_absent"],
            "exact_one_new_casing": content["check"]["exact_one_new_casing"],
        },
        "lowercase_keyed_copy": {
            "ok_must_fail_pass_criteria": negative["ok"],
            "listing": negative["listing"],
            "copied_keys": negative["copied_keys"],
            "pass_criteria_failed": negative["pass_criteria_failed"],
            "new_casing_absent": negative["new_casing_absent"],
            "expected_rel": NEW_REL,
        },
        "naive_write_then_delete_drop": {
            "ok_must_drop": drop["ok"],
            "listing": drop["listing"],
            "after_write_listing": drop["after_write_listing"],
            "dropped": drop["dropped"],
        },
        "pass": ok,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        "content_ok={c} lowercase_copy_fails_criteria={n} naive_drop={d}".format(
            c=content["ok"],
            n=negative["ok"],
            d=drop["ok"],
        )
    )
    if not content["ok"]:
        print("FAILED:TST-0196-probe2 content-changing rename did not carry")
        return 1
    if not negative["ok"]:
        print("FAILED:TST-0196-probe2 lowercase-keyed copy did not fail the casing check")
        return 1
    if not drop["ok"]:
        print("FAILED:TST-0196-probe2 naive write-then-delete did not drop")
        return 1
    print("SUCCESS:TST-0196-probe2 both-states and negative lowercase-keyed copy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
