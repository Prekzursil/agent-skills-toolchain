"""Prove NFC/NFD ids do not split across components after the boundary.

Three live-shaped consumers:
  catalog  tools/command-center/catalog.py:by_id / work_units_by_id
  json     object-key index after json.dumps/json.loads
  fs       receipt-style filename lookup on this Linux box (ext4: NFC != NFD)

Without canonical_id, raw dict / ext4 miss the NFD spelling while an NFC
fold treats them as one entity — the mixed-resolver hazard. After the
boundary every consumer uses canonical_id, and indexing both forms at
once raises NormalizationCollision instead of last-wins.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import catalog as cat  # noqa: E402
import id_normalize as inn  # noqa: E402
from detector import planted_pair  # noqa: E402

ENTITY = {"kind": "planted-entity", "unit": "TST-0057"}


def _raw_dict_component(nfc: str, nfd: str) -> dict[str, Any]:
    store = {nfc: ENTITY}
    return {
        "id": "raw-dict",
        "nfc_hit": nfc in store,
        "nfd_hit": nfd in store,
        "same_entity": store.get(nfc) is store.get(nfd) and nfc in store and nfd in store,
    }


def _catalog_component(nfc: str, nfd: str) -> dict[str, Any]:
    idx = cat.by_id({"items": [{"id": nfc, "title": "planted"}]})
    nfc_row = idx.get(nfc)
    nfd_row = idx.get(nfd)
    live = cat.load()
    live_units = cat.work_units_by_id(live)
    live_items = cat.by_id(live)
    return {
        "id": "catalog.by_id",
        "nfc_hit": nfc_row is not None,
        "nfd_hit": nfd_row is not None,
        "same_entity": nfc_row is nfd_row and nfc_row is not None,
        "live_tst0057": "TST-0057" in live_units,
        "live_item_count": len(live_items),
        "live_unit_count": len(live_units),
    }


def _json_component(nfc: str, nfd: str) -> dict[str, Any]:
    produced = {inn.canonical_id(nfd): ENTITY}
    loaded = json.loads(json.dumps(produced, ensure_ascii=True))
    idx = inn.CanonicalIdMap(loaded)
    raw_both = json.loads(json.dumps({nfc: 1, nfd: 2}, ensure_ascii=True))
    return {
        "id": "json-object-keys",
        "nfc_hit": nfc in idx,
        "nfd_hit": nfd in idx,
        "same_entity": idx.get(nfc) is idx.get(nfd) and nfc in idx,
        "producer_key_count": len(loaded),
        "raw_parser_key_count_when_both_emitted": len(raw_both),
        "raw_parser_treats_as_distinct": len(raw_both) == 2,
    }


def _fs_component(nfc: str, nfd: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tst0057-id-") as tmp:
        root = Path(tmp)
        canon_name = inn.canonical_id(nfc)
        (root / canon_name).write_text("entity\n", encoding="utf-8")
        nfc_path = root / inn.canonical_id(nfc)
        nfd_query = root / inn.canonical_id(nfd)
        raw_nfd = root / nfd
        return {
            "id": "filesystem-ext4",
            "nfc_hit": nfc_path.is_file(),
            "nfd_hit": nfd_query.is_file(),
            "same_entity": nfc_path.resolve() == nfd_query.resolve() and nfc_path.is_file(),
            "raw_nfd_path_missing": not raw_nfd.is_file(),
            "canonical_filename_utf8_hex": inn.byte_key(canon_name).hex(),
        }


def _collision_refused(nfc: str, nfd: str) -> dict[str, Any]:
    try:
        inn.index_by_canonical_id([{"id": nfc}, {"id": nfd, "other": True}])
        refused = False
        error = ""
    except inn.NormalizationCollision as exc:
        refused = True
        error = str(exc)
    return {"refused": refused, "error": error}


def run_boundary() -> dict[str, Any]:
    pair = planted_pair()
    nfc, nfd = pair["nfc"], pair["nfd"]
    raw = _raw_dict_component(nfc, nfd)
    catalog_c = _catalog_component(nfc, nfd)
    json_c = _json_component(nfc, nfd)
    fs_c = _fs_component(nfc, nfd)
    bounded = [catalog_c, json_c, fs_c]
    agree = all(c["nfc_hit"] and c["nfd_hit"] and c["same_entity"] for c in bounded)
    mixed = raw["nfd_hit"] != catalog_c["nfd_hit"]
    refused = _collision_refused(nfc, nfd)
    return {
        "pair": pair,
        "unbounded_raw_dict": raw,
        "components": bounded,
        "all_bounded_components_agree": agree,
        "raw_vs_catalog_disagree_on_nfd": mixed,
        "indexing_both_forms_refused": refused["refused"],
        "collision_error": refused["error"],
        "raw_json_parser_still_sees_two_keys": json_c["raw_parser_treats_as_distinct"],
    }
