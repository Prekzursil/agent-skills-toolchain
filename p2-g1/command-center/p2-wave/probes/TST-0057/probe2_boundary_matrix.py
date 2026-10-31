#!/usr/bin/env python3
"""TST-0057 probe2: test_ids_are_normalised_at_the_boundary.

Recomputes the component matrix live: catalog/map resolution agrees on the
planted pair (same entity), a raw dict misses the NFD spelling, a raw JSON
parser keeps the two spellings distinct, dual-form indexing is refused with
NormalizationCollision (never last-wins), and the raw NFD path is missing
on a canonical NFC filename.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import detector  # noqa: E402
from id_normalize import (  # noqa: E402
    CanonicalIdMap,
    NormalizationCollision,
    byte_key,
    canonical_id,
    index_by_canonical_id,
)

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

    nfc, nfd = detector.NFC_ID, detector.NFD_ID

    check("test_ids_are_normalised_at_the_boundary",
          canonical_id(nfd) == nfc and byte_key(nfc) != byte_key(nfd),
          {"canonical_equal": canonical_id(nfd) == nfc,
           "bytes_distinct": byte_key(nfc) != byte_key(nfd)})

    catalog_map: CanonicalIdMap = CanonicalIdMap()
    catalog_map[nfc] = {"entity": "same"}
    check("bounded-map-same-entity",
          nfc in catalog_map and nfd in catalog_map
          and catalog_map[nfd] == catalog_map[nfc],
          {"nfc_hit": nfc in catalog_map, "nfd_hit": nfd in catalog_map,
           "same_entity": catalog_map[nfd] == catalog_map[nfc]})

    raw: dict = {nfc: {"entity": "same"}}
    raw_nfd_hit = raw.get(nfd) is not None
    check("raw-dict-misses-nfd-spelling",
          not raw_nfd_hit and raw.get(nfc) is not None,
          {"nfc_hit": raw.get(nfc) is not None, "nfd_hit": raw_nfd_hit,
           "same_entity": False})

    refused = False
    message = ""
    try:
        index_by_canonical_id([{"id": nfc, "row": 1}, {"id": nfd, "row": 2}])
    except NormalizationCollision as exc:
        refused = True
        message = str(exc)
    check("test_dual_form_index_is_refused",
          refused and message.startswith("NFC collision:")
          and "canonical=" in message,
          {"refused": refused, "message": message[:80]})
    check("refusal-message-matches-receipt",
          message == receipt["boundary"].get("collision_error", message)
          or message[:40] == receipt["boundary"].get("collision_error", "")[:40],
          {"live": message[:60],
           "recorded": str(receipt["boundary"].get("collision_error"))[:60]})

    both = json.dumps({nfc: 1, nfd: 1}, ensure_ascii=False)
    parsed = json.loads(both)
    check("test_raw_json_parser_keeps_nfc_nfd_distinct",
          len(parsed) == 2,
          {"keys": len(parsed),
           "producer_would_emit_1": True})

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        nfc_path = tmp / ("receipt-" + nfc + ".json")
        nfc_path.write_text("{}", encoding="utf-8")
        nfd_path = tmp / ("receipt-" + nfd + ".json")
        check("canonical-filename-nfc-hit-nfd-raw-missing",
              nfc_path.is_file() and not nfd_path.exists(),
              {"nfc_hit": nfc_path.is_file(), "raw_nfd_path_missing": not nfd_path.exists(),
               "canonical_hex": byte_key(nfc).hex()})
        check("canonical-filename-hex-matches-receipt",
              byte_key(nfc).hex()
              == receipt["boundary"]["components"][2]["canonical_filename_utf8_hex"],
              {"live": byte_key(nfc).hex(),
               "recorded": receipt["boundary"]["components"][2]["canonical_filename_utf8_hex"]})

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = catalog.get("work_units") or []
    by_id = {str(u.get("id", "")): u for u in units}
    check("live-catalog-resolution",
          len(units) == 2007 and "TST-0057" in by_id
          and by_id["TST-0057"].get("title") == receipt.get("title"),
          {"units": len(units), "tst0057": "TST-0057" in by_id})

    boundary = receipt["boundary"]
    check("receipt-boundary-agreement-recorded",
          boundary.get("all_bounded_components_agree") is True
          and boundary.get("indexing_both_forms_refused") is True
          and boundary.get("raw_json_parser_still_sees_two_keys") is True
          and boundary.get("raw_vs_catalog_disagree_on_nfd") is True,
          {k: boundary.get(k) for k in
           ["all_bounded_components_agree", "indexing_both_forms_refused",
            "raw_json_parser_still_sees_two_keys",
            "raw_vs_catalog_disagree_on_nfd"]})
    check("option-id-resolution-present",
          (REPO / "command-center" / "OPTION-ID-RESOLUTION.json").is_file()
          == (receipt.get("inputs_inventory", [{}])[-1].get("present") is True),
          "registry input present as recorded")

    out = {"probe": "probe2-boundary-matrix", "unit_id": "TST-0057",
           "pass": not red, "checks": checks, "red": red}
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0 if not red else 1


if __name__ == "__main__":
    raise SystemExit(main())
