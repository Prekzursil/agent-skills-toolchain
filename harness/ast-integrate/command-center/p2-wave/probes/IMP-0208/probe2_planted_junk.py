#!/usr/bin/env python3
"""Probe 2: planted junk in packed bytes must fire the inventory gate.

Both-states control:
  good  — clean packed archive: gate silent (ok=True, intersection empty)
  bad   — same archive with .git / cache / transcript / credential members
          planted into the packed bytes: gate fires, names the planted paths,
          credential scan reports a hit.

The plant bypasses the allowlist packer so a packer that merely omits junk
from the source tree cannot satisfy this probe. Oracle is packed bytes.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from fixture import build_certified_tree, planted_junk_members  # noqa: E402
from marketplace.publication import (  # noqa: E402
    OwnerGateError,
    emit_payload,
    inventory_gate,
    pack_tree,
    plant_into_archive,
    publish,
)


def main() -> int:
    planted = planted_junk_members()
    with tempfile.TemporaryDirectory(prefix="imp0208-p2-") as td:
        root = build_certified_tree(Path(td) / "src", plant_source_junk=True)
        packed = pack_tree(root)
        payload = emit_payload(root)
        good = inventory_gate(packed.archive)
        dirty_archive = plant_into_archive(packed.archive, planted)
        bad = inventory_gate(dirty_archive)

        owner_refused = False
        try:
            publish(payload, None)
        except OwnerGateError:
            owner_refused = True
        owner_ok = publish(
            payload,
            {
                "granted": True,
                "action": "marketplace-publish",
                "unit": "IMP-0208",
                "owner": "probe2-owner-fixture",
            },
        )

    planted_paths = sorted(planted)
    named = set(bad.excluded_intersection)
    cred_paths = {h.path for h in bad.credential_hits}
    fired_on_paths = all(
        p in named or p in cred_paths for p in planted_paths
    )

    report = {
        "probe": "probe2-planted-junk",
        "unit_id": "IMP-0208",
        "good_gate_ok": good.ok,
        "good_excluded_intersection": good.excluded_intersection,
        "good_credential_hit_count": len(good.credential_hits),
        "bad_gate_ok": bad.ok,
        "bad_excluded_intersection": bad.excluded_intersection,
        "bad_credential_hit_count": len(bad.credential_hits),
        "bad_credential_pattern_ids": sorted({h.pattern_id for h in bad.credential_hits}),
        "planted_paths": planted_paths,
        "detector_fired": (not bad.ok) and bool(bad.excluded_intersection or bad.credential_hits),
        "detector_named_planted_paths": fired_on_paths,
        "owner_publish_without_approval_refused": owner_refused,
        "owner_publish_with_approval_state": owner_ok.get("state"),
        "both_states": good.ok and (not bad.ok),
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if not good.ok:
        print("FAILED:IMP-0208-probe2 good-state gate fired on a clean pack")
        return 1
    if good.excluded_intersection or good.credential_hits:
        print("FAILED:IMP-0208-probe2 good-state intersection or credential hits nonempty")
        return 1
    if bad.ok:
        print("FAILED:IMP-0208-probe2 planted junk did not trip the inventory gate")
        return 1
    if not bad.excluded_intersection:
        print("FAILED:IMP-0208-probe2 gate failed closed but named no excluded paths")
        return 1
    if not bad.credential_hits:
        print("FAILED:IMP-0208-probe2 planted credential-shaped member produced zero hits")
        return 1
    if not fired_on_paths:
        print(
            "FAILED:IMP-0208-probe2 gate did not name planted paths "
            f"named={sorted(named)} creds={sorted(cred_paths)}"
        )
        return 1
    if not owner_refused:
        print("FAILED:IMP-0208-probe2 publish without owner approval was not refused")
        return 1
    if owner_ok.get("state") != "PUBLISHED":
        print("FAILED:IMP-0208-probe2 owner-approved publish did not record PUBLISHED")
        return 1
    print(
        "SUCCESS:IMP-0208-probe2 inventory gate silent on clean pack, "
        "fires and names planted junk; owner gate held"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
