#!/usr/bin/env python3
"""TST-0179 probe2 -- emitter subset proof + lenient-parser detector control.

Two independent signals: (a) a schema-diff proving the emitter's field set is a
subset of the strict parser's accepted set across generated manifests, and
(b) the known-broken lenient parser demonstrably ACCEPTS the unknown field
(proving the strict parser's rejection is a real, distinguishing behavior).
Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import manifest_domain as MD  # noqa: E402

UNIT = "TST-0179"


def main() -> int:
    rng = random.Random(179179)
    accepted = set(MD.ACCEPTED_TOP_LEVEL)
    subset_holds = True
    emitted_fields_seen: set[str] = set()
    for _ in range(200):
        fields = {}
        for f in sorted(accepted):
            if rng.random() < 0.4:
                fields[f] = rng.choice(["x", 1, True, {}, []])
        text = MD.emit(fields)  # emitter raises on any non-accepted field
        emitted_fields_seen |= set(fields)
        try:
            MD.parse_strict(text)
        except MD.StrictManifestError:
            subset_holds = False

    # an emitter forced toward a foreign field must refuse (never emits it)
    refused = False
    try:
        MD.emit({"name": "x", "analytics": 1})
    except MD.StrictManifestError:
        refused = True

    poisoned = json.dumps({"name": "x", "telemetry": {"e": 1}})
    lenient_accepted_unknown = None
    try:
        lenient_accepted_unknown = MD.parse_lenient(poisoned)
    except Exception:
        lenient_accepted_unknown = "raised"

    payload = {
        "probe": "probe2-emitter-subset",
        "unit_id": UNIT,
        "pass": subset_holds and refused and isinstance(lenient_accepted_unknown, dict),
        "schema_diff": {
            "emitter_field_universe": sorted(emitted_fields_seen),
            "accepted_set": sorted(accepted),
            "subset_holds_over_200_generated_manifests": subset_holds,
            "emitter_refuses_foreign_field": refused,
        },
        "detector_control": {
            "known_broken": "parse_lenient (plain json.loads, no allowlist)",
            "lenient_accepts_unknown_field": isinstance(lenient_accepted_unknown, dict),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 subset=True emitter-refuses=True lenient-accepts=True" % UNIT)
        return 0
    print("FAILED:%s-probe2 subset=%s refused=%s lenient=%r"
          % (UNIT, subset_holds, refused, lenient_accepted_unknown))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
