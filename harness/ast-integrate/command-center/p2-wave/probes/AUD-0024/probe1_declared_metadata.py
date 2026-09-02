#!/usr/bin/env python3
"""Probe 1: declared license field in package metadata.

Reads the license key from package.json / METADATA independently of any
LICENSE file. The MIT/AGPL fixture must still report declared=MIT (the
metadata rail), never AGPL.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402
import inventory as I  # noqa: E402
import schema_local as SL  # noqa: E402

UNIT = "AUD-0024"


def _fail(msg: str) -> int:
    print(f"FAILED:AUD-0024-probe1 {msg}")
    return 1


def schema_discriminates() -> dict:
    schema_path = REPO / I.SCHEMA_REL
    garbage = {"totally": "unrelated", "n": 999999}
    garb_errs = SL.iter_errors(garbage)
    empty_errs = SL.iter_errors({})
    return {
        "schema_exists": schema_path.is_file(),
        "garbage_rejected": len(garb_errs) > 0,
        "empty_rejected": len(empty_errs) > 0,
        "garbage_error_count": len(garb_errs),
        "empty_error_count": len(empty_errs),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aud0024-p1-") as tmp:
        ctl = I.control_mit_agpl_conflict(Path(tmp))
        declared_only = I.write_fixture(
            Path(tmp) / "declared-only",
            declared="MIT",
            license_text=I.AGPL_BLOB,
        )
        rec = {
            "name": "declared-only",
            "version": "0",
            "ecosystem": "fixture",
            "source": "probe1",
            "installed": False,
            "root": declared_only,
            "declared_raw": "MIT",
            "classifiers": [],
        }
        declared = I.declared_from_record(rec)

    live = I.build_inventory()
    schema = schema_discriminates()
    missing_declared_field = [
        r["name"]
        for r in live["packages"]
        if "declared_spdx" not in r or "declared_raw" not in r
    ]
    ok = (
        ctl["bad"]["declared_spdx"] == "MIT"
        and ctl["bad"]["actual_spdx"] == "AGPL-3.0-only"
        and declared["spdx"] == "MIT"
        and schema["garbage_rejected"]
        and schema["empty_rejected"]
        and schema["schema_exists"]
        and len(live["packages"]) >= 1
        and not missing_declared_field
        and live["legal_advice"] is False
    )
    payload = {
        "pass": bool(ok),
        "probe": "probe1-declared-metadata",
        "unit_id": UNIT,
        "declared_rail_on_conflict_fixture": declared["spdx"],
        "conflict_fixture": ctl["bad"],
        "live_package_count": live["counts"]["packages"],
        "live_declared_license_absent": sum(
            1 for r in live["packages"] if r["declared_spdx"] == C.LICENSE_ABSENT
        ),
        "schema": schema,
        "aud0022": live["aud0022"],
        "closure_method": live["closure_method"],
        "legal_advice": False,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        return _fail(
            f"declared={declared.get('spdx')} schema={schema} "
            f"packages={live['counts']['packages']} missing={missing_declared_field[:8]}"
        )
    print(
        "SUCCESS:AUD-0024-probe1 declared metadata rail reports MIT on the "
        "MIT/AGPL fixture and does not silently take the LICENSE file"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
