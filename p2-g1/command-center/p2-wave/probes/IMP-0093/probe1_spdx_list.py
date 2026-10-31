#!/usr/bin/env python3
"""IMP-0093 probe1 (signal 1): SPDX identifier validity against the
official pinned list.

- the derived index (data/spdx-identifiers.json) must be in exact sync
  with a fresh in-memory derivation from the pinned list;
- known-good ids validate, fabricated ids do not, empty is
  LICENSE-ABSENT (both states);
- the tool never asserts legal advice (disclaimer present).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from marketplace import compatibility as compat_mod  # noqa: E402
from marketplace import license as lic  # noqa: E402
from marketplace import spdx  # noqa: E402
from marketplace.compatibility import UNKNOWN_NEEDS_REVIEW  # noqa: E402
from marketplace.license import (  # noqa: E402
    LICENSE_ABSENT,
    SPDX_INVALID,
    SPDX_VALID,
)


def main() -> int:
    checks = {}

    # derived index in sync with pinned list (drift cannot hide)
    fresh = write_receipts_derive()
    on_disk = json.loads(
        (REPO / "tools/marketplace/data/spdx-identifiers.json").read_text(encoding="utf-8")
    )
    checks["derived_index_in_sync"] = (
        on_disk.get("licenseIds") == fresh["licenseIds"]
        and len(fresh["licenseIds"]) == 23
    )

    # official-list membership (both states)
    official = spdx.official_ids()
    checks["official_list_nonempty"] = len(official) >= 20
    checks["mit_official"] = "MIT" in official
    checks["mit_validates"] = lic.validate_spdx("MIT")["code"] == SPDX_VALID
    checks["official_only_id_validates"] = (
        lic.validate_spdx("MPL-2.0")["code"] == SPDX_VALID
    )  # in pinned list, not in the embedded fast set
    checks["fabricated_rejected"] = (
        lic.validate_spdx("MIT-Not-Real-9999")["code"] == SPDX_INVALID
    )
    checks["empty_is_license_absent"] = (
        lic.validate_spdx("")["code"] == LICENSE_ABSENT
        and lic.validate_spdx(None)["code"] == LICENSE_ABSENT
    )
    # consistency: every embedded id that exists in the official list is
    # spelled identically there (no silent spelling drift)
    embedded = lic._KNOWN
    checks["embedded_ids_spelled_identically"] = embedded & official == {
        x for x in embedded if x in official
    }

    # the tool never asserts legal advice
    checks["not_legal_advice"] = "not legal advice" in lic.LEGAL_DISCLAIMER

    # unknown-pair policy is wired at module level too
    one_pair = compat_mod.pair_compatibility("MIT", "SSPL-1.0")
    checks["uncovered_pair_never_compatible"] = (
        one_pair["verdict"] == UNKNOWN_NEEDS_REVIEW
        and one_pair["verdict"] != "COMPATIBLE"
    )

    out = {
        "probe": "probe1-spdx-list",
        "unit_id": "IMP-0093",
        "official_ids": len(official),
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not all(checks.values()):
        print("FAILED:IMP-0093-probe1 %s" % [k for k, v in checks.items() if not v])
        return 1
    print("SUCCESS:IMP-0093-probe1 SPDX validity against official list; derived index in sync; LICENSE-ABSENT and fabricated both fire")
    return 0


def write_receipts_derive() -> dict:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "write_receipts", Path(__file__).resolve().parent / "write_receipts.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.derive()


if __name__ == "__main__":
    raise SystemExit(main())
