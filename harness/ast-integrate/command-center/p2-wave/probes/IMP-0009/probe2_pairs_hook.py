#!/usr/bin/env python3
"""Named probe 2: independent object_pairs_hook extraction.

Does not use the linter's walk to decide whether both keys were in the source.
A plain dict load last-wins exact duplicates and therefore measures nothing for
that class. Case-distinct Name/name is shown to collapse under casefold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "IMP-0009.json"
FIX = REPO / "tools" / "plugin" / "tests" / "fixtures"
PLANTED = FIX / "name-collision.json"
DUP = FIX / "duplicate-keys.json"


def pairs_load(text: str):
    return json.loads(text, object_pairs_hook=lambda pairs: pairs)


def root_keys(pairs) -> list[str]:
    return [k for k, _v in pairs]


def casefold_collapse(pairs) -> tuple[dict, list]:
    kept: dict[str, tuple[str, object]] = {}
    lost: list[dict] = []
    for key, value in pairs:
        folded = key.casefold()
        if folded in kept and kept[folded][0] != key:
            prev_key, prev_val = kept[folded]
            lost.append(
                {
                    "kept_key": prev_key,
                    "kept_value": prev_val,
                    "dropped_key": key,
                    "dropped_value": value,
                }
            )
        kept[folded] = (key, value)
    return kept, lost


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0009-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0009-probe2 receipt unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0009-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0009" not in text:
        print("FAILED:IMP-0009-probe2 sentinel absent")
        return 1

    planted_raw = PLANTED.read_text(encoding="utf-8")
    planted_pairs = pairs_load(planted_raw)
    planted_keys = root_keys(planted_pairs)
    if "Name" not in planted_keys or "name" not in planted_keys:
        print(f"FAILED:IMP-0009-probe2 pairs-hook missed Name/name: {planted_keys}")
        return 1
    # Python dict is case-sensitive, so this is NOT the loss path. The loss
    # path is a case-insensitive consumer; simulate it with casefold.
    collapsed, lost = casefold_collapse(planted_pairs)
    if len(lost) != 1 or len(collapsed) != 2:
        print(f"FAILED:IMP-0009-probe2 casefold collapse lost={lost} kept={collapsed}")
        return 1

    dup_raw = DUP.read_text(encoding="utf-8")
    dup_pairs = pairs_load(dup_raw)
    dup_keys = root_keys(dup_pairs)
    naive = json.loads(dup_raw)
    if dup_keys.count("name") != 2:
        print(f"FAILED:IMP-0009-probe2 pairs-hook did not keep duplicate name: {dup_keys}")
        return 1
    if list(naive.keys()).count("name") != 1:
        print("FAILED:IMP-0009-probe2 naive dict unexpectedly kept duplicates")
        return 1
    if naive.get("name") != "last-wins-under-dict-load":
        print(f"FAILED:IMP-0009-probe2 last-wins missing: {naive}")
        return 1

    reviewer = doc.get("reviewer") or {}
    notes = json.dumps(reviewer) + text
    if "object_pairs_hook" not in notes:
        print("FAILED:IMP-0009-probe2 receipt does not name object_pairs_hook loader")
        return 1

    payload = {
        "casefold_dropped": lost,
        "duplicate_naive_keys": list(naive.keys()),
        "duplicate_pairs_name_count": dup_keys.count("name"),
        "naive_dict_destroys_duplicates": True,
        "pairs_hook_name_and_Name": True,
        "pass": True,
        "planted_keys": planted_keys,
        "probe": "probe2-pairs-hook",
        "unit_id": "IMP-0009",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "pairs_hook_preserved_Name_and_name=True "
        "casefold_lost_one=True "
        "naive_dict_duplicate_count=1"
    )
    print("SUCCESS:IMP-0009-probe2 independent pairs-hook extraction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
