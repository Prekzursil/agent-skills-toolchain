#!/usr/bin/env python3
"""Probe 2: every NON-owned path present before is still present byte-identical.

Instrument: sha256 of files not in the owned set. Independent of probe 1's
existence census. A HOME rmtree zeros owned paths (probe 1 would pass) and
destroys this hash census (this probe must fail that counterfactual).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.census import non_owned_inventory, owned_remaining  # noqa: E402
from plugin.scenario import seed_home  # noqa: E402
from plugin.uninstall import uninstall  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0027-p2-") as tmp:
        root = Path(tmp)
        honest = root / "honest"
        scorched = root / "scorched"
        seed = seed_home(honest)
        shutil.copytree(honest, scorched)
        before = non_owned_inventory(honest, seed.projection, include_user_data=True)
        if not before:
            print("FAILED:IMP-0027-probe2 no non-owned files were seeded")
            return 1
        uninstall(honest, seed.projection, purge_user_data=False)
        after = non_owned_inventory(honest, seed.projection, include_user_data=True)

        missing = [rel for rel in before if rel not in after]
        changed = [
            rel for rel, digest in before.items() if after.get(rel) != digest
        ]
        if missing or changed:
            print(f"FAILED:IMP-0027-probe2 missing={missing} changed={changed}")
            return 1

        shutil.rmtree(scorched)
        scorched.mkdir()
        leftover_scorch = owned_remaining(scorched, seed.projection)
        after_scorch = non_owned_inventory(
            scorched, seed.projection, include_user_data=True
        )
        if leftover_scorch:
            print(f"FAILED:IMP-0027-probe2 scorched leftover unexpected {leftover_scorch}")
            return 1
        if after_scorch == before:
            print("FAILED:IMP-0027-probe2 scorched-earth incorrectly matched foreign hashes")
            return 1
        if after_scorch:
            print(f"FAILED:IMP-0027-probe2 scorched tree not empty {after_scorch}")
            return 1

        doc = {
            "pass": True,
            "probe": "probe2-foreign-bytes",
            "unit_id": "IMP-0027",
            "non_owned_checked": sorted(before),
            "byte_identical": True,
            "scorched_earth_owned_empty": leftover_scorch == [],
            "scorched_earth_foreign_destroyed": after_scorch != before,
            "instrument": "sha256 of non-owned files (include user data)",
        }
        print(json.dumps(doc, sort_keys=True))
        print(
            f"non_owned={len(before)} byte_identical=True "
            f"scorched_earth_fails_identity=True"
        )
        print(
            "SUCCESS:IMP-0027-probe2 non-owned paths byte-identical; "
            "scorched-earth negative control fires"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
