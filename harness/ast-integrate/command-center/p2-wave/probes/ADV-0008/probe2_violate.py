#!/usr/bin/env python3
"""Probe 2: violate each mapped clause in a scratch copy of the SYSTEM.

Mechanically different from probe 1 (does not parse markdown, does not build
the id->test index from headings). Mutates gate flags, never the test file.
Reverting the violation must restore green or the red is harness-caused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:ADV-0008-probe2 {msg}")
    return 1


def main() -> int:
    data = H.violate_mapped_pairs()
    print(json.dumps(data, indent=2, sort_keys=True))

    if not data["tests_file_untouched"]:
        return _fail("violation harness edited the test file")
    if not data["at_least_one_killed"]:
        return _fail("all-survived usually means the suite never ran")
    if not data["revert_returns_green"]:
        return _fail("revert did not restore green; red may be harness-caused")
    if data["n_harness_broken"]:
        return _fail(f"harness-broken pairs {data['harness_broken_ids']}")
    if "CLAUSE-C1" not in data["killed_ids"]:
        return _fail("planted covered CLAUSE-C1 was not killed")
    if "CLAUSE-C2" not in data["killed_ids"]:
        return _fail("planted covered CLAUSE-C2 was not killed")
    if "CLAUSE-C4" not in data["killed_ids"]:
        return _fail("planted covered CLAUSE-C4 was not killed")
    if "CLAUSE-C3" not in data["survived_ids"]:
        return _fail("planted decorative CLAUSE-C3 must survive (uncovered)")
    if "CLAUSE-C5" not in data["missing_test_ids"]:
        return _fail("planted missing-test CLAUSE-C5 not classified")
    if "CLAUSE-C6" not in data["unmapped_ids"]:
        return _fail("planted unmapped CLAUSE-C6 not classified")
    print(
        "killed={k} survived={s} missing={m} unmapped={u} revert_green={g}".format(
            k=data["killed_ids"],
            s=data["survived_ids"],
            m=data["missing_test_ids"],
            u=data["unmapped_ids"],
            g=data["revert_returns_green"],
        )
    )
    print("SUCCESS:ADV-0008-probe2 scratch SYSTEM violation and revert control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
