#!/usr/bin/env python3
"""One-off ADV-01 novel mutant for IMP-0438 adversarial review.

Flips one hex nibble of provenance.register_sha256 while leaving the REGISTER.md
fixture and the rest of the catalog intact. Distinct from battery M10 (tampered
register bytes), M12 (blank digest), and M13 (deleted digest key).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import battery as b  # noqa: E402


def _corrupt_register_sha256(catalog: dict, _tmp: Path) -> dict:
    digest = str(catalog["provenance"]["register_sha256"])
    if len(digest) < 2:
        raise RuntimeError("expected a non-empty register_sha256 to corrupt")
    # Flip the first hex nibble so validate.py's 12-char mismatch display
    # shows distinct prefixes (flipping only the last nibble looks identical).
    first = digest[0].lower()
    flipped = "0" if first != "0" else "1"
    catalog["provenance"]["register_sha256"] = flipped + digest[1:]
    return {"rebuild_graph": False}


ADV_01 = {
    "id": "ADV-01",
    "name": "corrupt-register-sha256-one-nibble",
    "claimed_check": "REACH-6",
    "unprotected_if_survives": (
        "A non-empty but wrong register_sha256 is accepted while the snapshot "
        "bytes are untouched — digest mismatch silence distinct from blank/delete."
    ),
    "apply": _corrupt_register_sha256,
}


def main() -> int:
    base = b.load_slim()
    armed = b.run_one(base, ADV_01, disarm=False)
    disarmed = None
    if b.supports_disarm_flag():
        disarmed = b.run_one(base, ADV_01, disarm=True)
    report = {
        "novel_mutation_id": "ADV-01",
        "armed": {
            "caught": armed["caught"],
            "exit_code": armed["exit_code"],
            "claimed_check_in_output": armed["claimed_check_in_output"],
            "success_marker": armed["success_marker"],
            "failed_marker": armed["failed_marker"],
            "output_tail": armed["output_tail"],
        },
        "disarmed": (
            None
            if disarmed is None
            else {
                "caught": disarmed["caught"],
                "exit_code": disarmed["exit_code"],
                "output_tail": disarmed["output_tail"],
            }
        ),
    }
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if armed["caught"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
