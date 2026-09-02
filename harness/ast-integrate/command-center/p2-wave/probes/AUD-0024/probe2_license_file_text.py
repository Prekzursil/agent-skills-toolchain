#!/usr/bin/env python3
"""Probe 2: LICENSE file text classified independently of package metadata.

A fixture whose metadata says MIT and whose LICENSE file is AGPL must be
flagged as a declared-versus-actual conflict, not silently resolved to either.
A matching MIT/MIT fixture must stay silent.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402
import inventory as I  # noqa: E402

UNIT = "AUD-0024"


def _fail(msg: str) -> int:
    print(f"FAILED:AUD-0024-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aud0024-p2-") as tmp:
        ctl = I.control_mit_agpl_conflict(Path(tmp))
        blob_only = C.classify_license_blob(I.AGPL_BLOB)
        mit_only = C.classify_license_blob(I.MIT_BLOB)

    live = I.build_inventory()
    silent_winner = ctl["bad"]["resolved_spdx"] in {"MIT", "AGPL-3.0-only"}
    ok = (
        ctl["both_states"] is True
        and ctl["fired_on_bad_state"] is True
        and ctl["silent_on_good_state"] is True
        and ctl["bad"]["conflict"] is True
        and ctl["bad"]["resolved_spdx"] == C.CONFLICT
        and not silent_winner
        and blob_only["spdx"] == "AGPL-3.0-only"
        and mit_only["spdx"] == "MIT"
        and live["legal_advice"] is False
    )
    payload = {
        "pass": bool(ok),
        "probe": "probe2-license-file-text",
        "unit_id": UNIT,
        "reviewer_id": "AUD-0024-probe2-license-file-text",
        "control": ctl,
        "agpl_blob_spdx": blob_only["spdx"],
        "mit_blob_spdx": mit_only["spdx"],
        "live_license_file_absent": live["counts"]["license_file_absent"],
        "live_conflicts": live["counts"]["conflicts"],
        "live_packages": live["counts"]["packages"],
        "silently_resolved_to_either": silent_winner,
        "legal_advice": False,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        return _fail(
            f"both_states={ctl.get('both_states')} bad={ctl.get('bad')} "
            f"silent_winner={silent_winner} agpl={blob_only.get('spdx')}"
        )
    print(
        "SUCCESS:AUD-0024-probe2 LICENSE-file rail classifies AGPL independently; "
        "MIT-metadata/AGPL-file is a conflict not resolved to either"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
