#!/usr/bin/env python3
"""Probe 1: tampered blob is named and rejected; census does not change.

Evidence (1): a bundle with a tampered blob is rejected, naming the entry.
Evidence (2): index/blob census before and after is identical — zero entries
changed. A partial import that then rejects is still a compromise.

NEGATIVE CONTROL: the original valid bundle imports fully in the same run.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.offline import (  # noqa: E402
    empty_registry,
    export_offline_bundle,
    import_offline_bundle,
    mutate_tar_member,
    registry_census,
)
from tools.marketplace.storage import registry_dir  # noqa: E402

UNIT = "IMP-0109"
HELLO = "hello-skill@1.0.0"
LIB = "hello-lib@1.0.0"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    src = registry_dir(REPO)
    archive = export_offline_bundle(src, [HELLO, LIB])
    tampered = mutate_tar_member(
        archive,
        "blobs/hello-skill-1.0.0.json",
        b'{"name":"hello-skill","version":"1.0.0","pwned":true}',
    )
    with tempfile.TemporaryDirectory(prefix="imp0109-p1-") as td:
        root = Path(td)
        bad = empty_registry(root / "bad")
        good = empty_registry(root / "good")
        before = registry_census(bad)
        refused = import_offline_bundle(bad, tampered)
        after = registry_census(bad)
        accepted = import_offline_bundle(good, archive)
        good_census = registry_census(good)

    if refused.ok:
        return fail("tampered bundle was accepted")
    codes = {e.get("code") for e in refused.errors}
    if "TAMPERED_BLOB" not in codes:
        return fail(f"expected TAMPERED_BLOB, got {refused.errors}")
    if refused.named_entry != HELLO:
        return fail(f"named_entry={refused.named_entry!r} want={HELLO}")
    if before != after:
        return fail(f"census changed on reject before={before} after={after}")
    if after["package_count"] != 0 or after["ids"] != []:
        return fail(f"partial import leaked entries {after}")
    if not accepted.ok:
        return fail(f"negative control valid import failed {accepted.errors}")
    if sorted(accepted.imported_ids) != sorted([HELLO, LIB]):
        return fail(f"valid imported_ids={accepted.imported_ids}")
    if good_census["package_count"] != 2:
        return fail(f"valid census count={good_census['package_count']}")

    out = {
        "pass": True,
        "probe": "probe1-tampered-census",
        "unit_id": UNIT,
        "named_entry": refused.named_entry,
        "tamper_codes": sorted(codes),
        "census_unchanged": before == after,
        "rejected_package_count": after["package_count"],
        "valid_imported_ids": accepted.imported_ids,
        "valid_package_count": good_census["package_count"],
        "computed_not_asserted": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"named_entry={refused.named_entry} census_unchanged=True "
        f"valid_imported={accepted.imported_ids}"
    )
    print(f"SUCCESS:{UNIT}-probe1 tampered blob named and refused; census frozen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
