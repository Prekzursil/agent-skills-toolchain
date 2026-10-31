#!/usr/bin/env python3
"""TST-0057 probe1: test_detector_finds_a_planted_nfd_id + live census slice.

The detector must recover the planted NFC/NFD pair inside an ASCII id
population, produce no false group on ASCII ids, and the receipt census
must be internally consistent (15099 ids, 489 namespaces, 0 non-ASCII,
0 collision groups) with a live recomputed slice over the work-unit catalog.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector  # noqa: E402
from id_normalize import canonical_id, collision_groups  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0057.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def main() -> int:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    checks = []
    red = []

    def check(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        if not ok:
            red.append(name)

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    live_ids = [str(u.get("id", "")) for u in catalog.get("work_units") or []]

    planted = detector.detect_planted(live_ids)
    check("test_detector_finds_a_planted_nfd_id",
          planted["planted_hit"] is True and planted["group_count"] == 1,
          {"group_count": planted["group_count"],
           "planted_hit": planted["planted_hit"]})
    pair = planted["groups"][0] if planted["groups"] else {}
    recorded_pair = receipt["detector"]["pair"]
    check("planted-bytes-match-receipt",
          pair.get("utf8_hex") == [recorded_pair["nfc_utf8_hex"],
                                   recorded_pair["nfd_utf8_hex"]],
          {"live": pair.get("utf8_hex"),
           "recorded": [recorded_pair["nfc_utf8_hex"],
                        recorded_pair["nfd_utf8_hex"]]})
    check("canonical-form-is-nfc",
          canonical_id(detector.NFD_ID) == detector.NFC_ID,
          "NFD folds to NFC at the boundary")

    ascii_only = detector.detect(live_ids)
    check("ascii-population-no-false-group",
          ascii_only["group_count"] == 0 and ascii_only["planted_hit"] is False,
          {"groups": ascii_only["group_count"], "population": len(live_ids)})

    census = receipt["census"]
    namespaces = census.get("namespaces") or []
    total = sum(int(ns.get("id_count", 0)) for ns in namespaces)
    non_ascii = sum(int(ns.get("non_ascii_count", 0)) for ns in namespaces)
    check("census-internal-consistency",
          total == census.get("live_census_total", total)
          and len(namespaces) == 489
          and total == 15099
          and non_ascii == 0
          and census.get("live_nfc_collision_count") == 0,
          {"namespaces": len(namespaces), "total": total,
           "non_ascii": non_ascii,
           "recorded_collisions": census.get("live_nfc_collision_count")})

    live_slice_groups = collision_groups(live_ids)
    live_non_ascii = [i for i in live_ids if not i.isascii()]
    check("live-catalog-slice-recomputed",
          len(live_ids) == 2007 and not live_slice_groups and not live_non_ascii,
          {"ids": len(live_ids), "groups": len(live_slice_groups),
           "non_ascii": len(live_non_ascii)})
    check("census-excludes-probe-fixtures",
          any("p2-wave" in str(x) for x in census.get("excluded", [])),
          census.get("excluded"))

    out = {"probe": "probe1-census-detector", "unit_id": "TST-0057",
           "pass": not red, "checks": checks, "red": red}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
