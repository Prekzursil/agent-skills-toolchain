#!/usr/bin/env python3
"""Probe 2: unversioned taxonomy edit fails the guard (detector control).

Both-states:
  * unmodified taxonomy+lock is silent (ok=True)
  * adding a capability without a version bump fires unversioned-taxonomy-edit
  * the same add with a version bump is allowed
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center"))

from foundry.capability.taxonomy import (  # noqa: E402
    UnversionedTaxonomyEdit,
    check_guard,
    load_lock,
    load_taxonomy,
    mutate_add_capability,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0177-probe2 {msg}")
    return 1


def main() -> int:
    tax = load_taxonomy()
    lock = load_lock()

    good = check_guard(tax, lock)
    if not good["ok"]:
        return fail(f"false-positive-on-unmodified code={good.get('code')}")

    bad_tax = mutate_add_capability(
        tax,
        family_id="research/evidence",
        capability_id="planted-unversioned-capability",
        bump_version=False,
    )
    if bad_tax["version"] != tax["version"]:
        return fail("mutant-version-changed-unexpectedly")
    if bad_tax["capability_count"] != tax["capability_count"] + 1:
        return fail("mutant-count")
    bad = check_guard(bad_tax, lock)
    if bad["ok"]:
        return fail("detector-silent-on-unversioned-add")
    if bad["code"] != UnversionedTaxonomyEdit.code:
        return fail(f"wrong-code={bad['code']}")

    raised = False
    try:
        check_guard(bad_tax, lock, raise_on_fail=True)
    except UnversionedTaxonomyEdit:
        raised = True
    if not raised:
        return fail("raise_on_fail-did-not-fire")

    bumped = mutate_add_capability(
        tax,
        family_id="research/evidence",
        capability_id="planted-unversioned-capability",
        bump_version=True,
    )
    if bumped["version"] == tax["version"]:
        return fail("version-bump-missing")
    versioned = check_guard(bumped, lock)
    if not versioned["ok"]:
        return fail("versioned-add-rejected")

    # Same-version, same set: still silent (identity control).
    identity = check_guard(tax, lock)
    if not identity["ok"]:
        return fail("identity-false-positive")

    out = {
        "probe": "probe2-unversioned-guard",
        "unit_id": "IMP-0177",
        "pass": True,
        "fired_on_bad": True,
        "silent_on_good": True,
        "versioned_add_allowed": True,
        "code": bad["code"],
        "live_version": tax["version"],
        "bad_version": bad_tax["version"],
        "bumped_version": bumped["version"],
        "sealed_count": lock["capability_count"],
        "bad_count": bad_tax["capability_count"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"fired_on_bad=True silent_on_good=True versioned_ok=True "
        f"code={bad['code']} {tax['version']}->{bumped['version']}"
    )
    print("SUCCESS:IMP-0177-probe2 unversioned taxonomy edit fails the guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
