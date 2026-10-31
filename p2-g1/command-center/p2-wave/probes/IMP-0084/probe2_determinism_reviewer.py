#!/usr/bin/env python3
"""IMP-0084 probe2 (independent reviewer pass): lockfile determinism
(byte-identical regeneration from the same index), the reviewer's OWN
second mutation class (first-byte XOR - distinct from probe1's suffix
mutation), stale-resolver warning, and missing-entry refusal pre-write.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scenario  # noqa: E402
from marketplace.lockfile import (  # noqa: E402
    DigestMismatch,
    MissingLockfileEntry,
    filesystem_census,
    generate_lockfile,
    install_verified,
    load_lockfile,
)


def main() -> int:
    checks = {}

    index = scenario.build_index()
    checks["regenerate_byte_identical"] = (
        scenario.build_lockfile() == generate_lockfile(list(reversed(index))))
    rows = load_lockfile(scenario.build_lockfile())["packages"]
    checks["rows_sorted"] = rows == sorted(rows, key=lambda r: (r["name"], r["version"]))

    root, lock = scenario.fresh_root()
    before = filesystem_census(root)
    refused = None
    try:
        install_verified(lock, name="beta", dest=root,
                         fetch=scenario.fetch_xor_mutated)
    except DigestMismatch as exc:
        refused = exc
    checks["reviewer_xor_mutation_refused"] = refused is not None
    checks["refusal_before_write_xor"] = before == filesystem_census(root)

    doc = load_lockfile(lock)
    doc["resolver_version"] = "0"
    stale = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    got = install_verified(stale, name="beta", dest=root,
                           fetch=scenario.fetch_unmutated)
    checks["stale_resolver_warns"] = (
        len(got.warnings) == 1 and "stale resolver version" in got.warnings[0])

    before2 = filesystem_census(root)
    try:
        install_verified(lock, name="gamma", dest=root,
                         fetch=scenario.fetch_unmutated)
        checks["missing_entry_refused"] = False
    except MissingLockfileEntry:
        checks["missing_entry_refused"] = True
    checks["missing_entry_wrote_nothing"] = before2 == filesystem_census(root)

    print(json.dumps({
        "probe": "probe2-determinism-reviewer",
        "unit_id": "IMP-0084",
        "checks": checks,
        "pass": all(checks.values()),
    }, sort_keys=True))
    if not all(checks.values()):
        print("FAILED:IMP-0084-probe2 %s" % [k for k, v in checks.items() if not v])
        return 1
    print("SUCCESS:IMP-0084-probe2 lockfile regeneration byte-identical; reviewer XOR mutation refused pre-write; stale resolver warns; missing entry refuses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
