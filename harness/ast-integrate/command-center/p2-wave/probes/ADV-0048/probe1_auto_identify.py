#!/usr/bin/env python3
"""Named probe 1: automated license identification with raw evidence strings.

Signal: SPDX-ish fingerprint + package.json metadata. A LICENSE that is not a
known license must not be labelled MIT. Mechanically different from probe 2
(no obligation-clause extraction).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import automated_inventory, mit_control_ok  # noqa: E402

ART = REPO / (
    "command-center/adversarial/"
    "ADV-0048-license-inventory-compatibility-matrix.json"
)
UNIT = "ADV-0048"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:ADV-0048" not in blob:
        return fail("sentinel absent")

    live = automated_inventory()
    mit = mit_control_ok(live)
    if not mit["ok"]:
        return fail("MIT control or not-a-license negative", mit)

    art_comps = {
        c["id"]: c for c in (doc.get("components") or []) if isinstance(c, dict)
    }
    live_comps = {c["id"]: c for c in live["components"]}
    if set(art_comps) != set(live_comps):
        return fail("component id set mismatch", {"art": sorted(art_comps), "live": sorted(live_comps)})
    for cid, live_c in live_comps.items():
        art_c = art_comps[cid]
        for key in ("automated_spdx", "automated_family", "escalates_to_probe2"):
            if art_c.get(key) != live_c.get(key):
                return fail(f"{cid} {key} mismatch", {"art": art_c.get(key), "live": live_c.get(key)})
        if not art_c.get("evidence_string"):
            return fail(f"{cid} missing evidence_string")

    if live["unknown_rate"] > live["unknown_rate_threshold"]:
        if (doc.get("report") or {}).get("matrix_cleanliness") != "NOT-CHECKED":
            return fail("high unknown rate must force NOT-CHECKED, not clean")
        target = next(
            (
                t
                for t in (doc.get("targets") or [])
                if t.get("id") == "compatibility-matrix-clean"
            ),
            None,
        )
        if not target or target.get("verdict") != "NOT-CHECKED":
            return fail("compatibility-matrix-clean not NOT-CHECKED", target)

    cmds = [
        p.get("command")
        for p in (doc.get("named_probes") or [])
        if isinstance(p, dict)
    ]
    if not any("probe1_auto_identify.py" in str(c) for c in cmds):
        return fail("named probe1 command absent", cmds)

    out = {
        "probe": "probe1-auto-identify",
        "unit_id": UNIT,
        "pass": True,
        "mit_spdx": mit["mit"]["spdx"],
        "mit_family": mit["mit"]["family"],
        "not_a_license_family": mit["not_a_license"]["family"],
        "unknown_rate": live["unknown_rate"],
        "unknown_rate_threshold": live["unknown_rate_threshold"],
        "matrix_cleanliness": live["matrix_cleanliness"],
        "component_n": live["component_n"],
        "artifact_matches_live": True,
        "method": "fingerprint-plus-package-json-metadata",
    }
    (HERE / "probe1-auto-identify.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:ADV-0048-probe1 automated identification and MIT control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
