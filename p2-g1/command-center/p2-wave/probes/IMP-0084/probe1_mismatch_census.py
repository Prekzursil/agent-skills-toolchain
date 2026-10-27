#!/usr/bin/env python3
"""IMP-0084 probe1: a mutated upstream blob is refused, naming the digest
mismatch, and a filesystem census proves NOTHING was written before the
refusal. Negative control: the unmutated blob installs in the same run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scenario  # noqa: E402
from marketplace.lockfile import (  # noqa: E402
    DigestMismatch,
    filesystem_census,
    install_verified,
)


def main() -> int:
    checks = {}
    root, lock = scenario.fresh_root()

    before = filesystem_census(root)
    refused = None
    try:
        install_verified(lock, name="alpha", dest=root,
                         fetch=scenario.fetch_suffix_mutated)
    except DigestMismatch as exc:
        refused = exc
    checks["mutated_refused"] = refused is not None
    checks["refusal_names_both_digests"] = bool(
        refused
        and refused.expected_hex in str(refused)
        and refused.actual_hex in str(refused)
    )
    checks["digests_actually_differ"] = bool(
        refused and refused.expected_hex != refused.actual_hex)
    checks["census_nothing_written_before_refusal"] = (
        before == filesystem_census(root))

    got = install_verified(lock, name="alpha", dest=root,
                           fetch=scenario.fetch_unmutated)
    checks["negative_control_unmutated_installs_same_run"] = (
        Path(got.dest).is_file()
        and Path(got.dest).read_bytes() == scenario.BLOBS["alpha"])
    after = filesystem_census(root)
    checks["census_gains_exactly_one_payload"] = (
        len(after) == len(before) + 1
        and list(after)[0] == Path(got.dest).relative_to(root).as_posix())

    print(json.dumps({
        "probe": "probe1-mismatch-census",
        "unit_id": "IMP-0084",
        "checks": checks,
        "expected_hex": refused.expected_hex if refused else None,
        "actual_hex": refused.actual_hex if refused else None,
        "pass": all(checks.values()),
    }, sort_keys=True))
    if not all(checks.values()):
        print("FAILED:IMP-0084-probe1 %s" % [k for k, v in checks.items() if not v])
        return 1
    print("SUCCESS:IMP-0084-probe1 mutated upstream refused pre-write with named digest mismatch; unmutated installs in same run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
