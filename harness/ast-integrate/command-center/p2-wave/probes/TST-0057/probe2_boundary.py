#!/usr/bin/env python3
"""Named probe 2: ids are normalised at the boundary (adversarial overclaim).

Independent of probe 1: recomputes the three-component agreement matrix and
refuses a SUCCESS receipt that claims mixed-resolver safety without the
raw-dict negative control, or that treats a missing OPTION-ID-RESOLUTION
file as a populated registry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(TOOLS))

import boundary as B  # noqa: E402
import catalog as cat  # noqa: E402
import id_normalize as inn  # noqa: E402

ART = REPO / "command-center/receipts/TST-0057.json"
OUT = HERE / "probe2-boundary.raw.json"
SENTINEL = "SUCCESS:TST-0057"


def check_artifact(matrix: dict) -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"artifact self-declared {doc.get('state')}"
    bound = doc.get("boundary") or {}
    if bound.get("all_bounded_components_agree") is not True:
        return "receipt omits bounded-component agreement"
    if bound.get("raw_vs_catalog_disagree_on_nfd") is not True:
        return "receipt dropped the raw-dict negative control"
    if bound.get("indexing_both_forms_refused") is not True:
        return "receipt does not record collision-refusal"
    census = doc.get("census") or {}
    option = census.get("option_id_resolution") or {}
    live_present = (REPO / "command-center/OPTION-ID-RESOLUTION.json").is_file()
    if bool(option.get("present")) != live_present:
        return "receipt option_id_resolution.present does not match disk"
    if option.get("present") is True and "invented" in str(doc.get("answer") or "").lower():
        return "overclaim: invented option registry"
    if matrix["all_bounded_components_agree"] is not True:
        return "live boundary recompute disagrees with success claim"
    return None


def main() -> int:
    matrix = B.run_boundary()
    OUT.write_text(
        json.dumps(matrix, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    if not matrix["all_bounded_components_agree"]:
        print("FAILED:TST-0057-probe2 bounded components disagree")
        print(json.dumps(matrix["components"], ensure_ascii=True)[:2000])
        return 1
    if not matrix["raw_vs_catalog_disagree_on_nfd"]:
        print("FAILED:TST-0057-probe2 raw dict also hit NFD; negative control dead")
        return 1
    if not matrix["indexing_both_forms_refused"]:
        print("FAILED:TST-0057-probe2 dual-form index was last-wins, not refused")
        return 1
    if not matrix["unbounded_raw_dict"]["nfc_hit"]:
        print("FAILED:TST-0057-probe2 raw dict missed NFC key")
        return 1
    if matrix["unbounded_raw_dict"]["nfd_hit"]:
        print("FAILED:TST-0057-probe2 raw dict must MISS NFD (byte identity)")
        return 1
    if not matrix["raw_json_parser_still_sees_two_keys"]:
        print("FAILED:TST-0057-probe2 json.loads merged NFC/NFD keys; environment shifted")
        return 1

    live = cat.load()
    units = cat.work_units_by_id(live)
    if "TST-0057" not in units:
        print("FAILED:TST-0057-probe2 live work_units_by_id missed TST-0057")
        return 1
    nfd_ascii = inn.nfd_form("TST-0057")
    if nfd_ascii != "TST-0057" or units.get(nfd_ascii) is not units.get("TST-0057"):
        print("FAILED:TST-0057-probe2 ASCII identity broken at work_units boundary")
        return 1

    art = check_artifact(matrix)
    if art:
        print(f"FAILED:TST-0057-probe2 {art}")
        return 1

    print(
        json.dumps(
            {
                "bounded_agree": True,
                "raw_nfd_miss": True,
                "dual_form_refused": True,
                "json_raw_two_keys": True,
                "components": [c["id"] for c in matrix["components"]],
            },
            ensure_ascii=True,
        )
    )
    print(
        "SUCCESS:TST-0057-probe2 boundary NFC; catalog/json/fs agree; "
        "raw-dict negative control live"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
