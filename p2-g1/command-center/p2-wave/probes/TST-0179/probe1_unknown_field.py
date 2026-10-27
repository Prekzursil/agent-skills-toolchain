#!/usr/bin/env python3
"""TST-0179 probe1 -- strict client parser rejects an unknown top-level manifest field
with an error naming it; a clean manifest is accepted (both-states control).

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import manifest_domain as MD  # noqa: E402

UNIT = "TST-0179"


def main() -> int:
    clean = {"name": "sample-plugin", "version": "1.0.0", "hooks": {}}
    clean_text = MD.emit(clean)
    accepted = None
    try:
        accepted = MD.parse_strict(clean_text)
    except MD.StrictManifestError:
        pass

    poisoned = dict(clean)
    poisoned["telemetry"] = {"endpoint": "https://example.invalid/ingest"}
    err = None
    named_field = None
    try:
        MD.parse_strict(json.dumps(poisoned))
    except MD.StrictManifestError as e:
        err = str(e)
        named_field = e.field

    payload = {
        "probe": "probe1-unknown-field",
        "unit_id": UNIT,
        "pass": accepted is not None and err is not None and named_field == "telemetry",
        "clean_manifest_accepted": accepted is not None,
        "unknown_field_rejected": err is not None,
        "error_names_field": named_field,
        "error_text": err,
        "accepted_top_level_count": len(MD.ACCEPTED_TOP_LEVEL),
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 clean=accepted unknown=rejected field=%s" % (UNIT, named_field))
        return 0
    print("FAILED:%s-probe1 clean=%s rejected=%s named=%s"
          % (UNIT, accepted is not None, err is not None, named_field))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
