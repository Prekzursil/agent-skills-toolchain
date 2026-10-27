#!/usr/bin/env python3
"""IMP-0093 supporting utility: regenerate the derived SPDX identifier
index (tools/marketplace/data/spdx-identifiers.json) from the pinned
official list. The index is a DERIVED artifact; this script is its
single generator, and probe1_spdx_list.py re-derives in-memory to prove
the on-disk index has not drifted from the pinned list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from marketplace import spdx  # noqa: E402

OUT = REPO / "tools" / "marketplace" / "data" / "spdx-identifiers.json"


def derive() -> dict:
    doc = spdx.load_pinned()
    ids = sorted(
        set(doc.get("licenseIds") or []) | set(doc.get("deprecatedLicenseIds") or [])
    )
    return {
        "name": "marketplace SPDX identifier index",
        "provenance": {
            "generated_by": "command-center/p2-wave/probes/IMP-0093/write_receipts.py (IMP-0093)",
            "derived_from": "tools/marketplace/data/spdx-license-list-3.25.0.json (pinned official SPDX 3.25.0 snapshot)",
            "licenseListVersion": doc.get("licenseListVersion"),
        },
        "licenseIds": ids,
    }


def main() -> int:
    derived = derive()
    OUT.write_text(
        json.dumps(derived, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "derived": str(OUT.relative_to(REPO).as_posix()),
                "licenseIds": len(derived["licenseIds"]),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0093-write-receipts derived SPDX index regenerated from pinned list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
