#!/usr/bin/env python3
"""Named probe 1: resolver provenance=item|default and live 0/103 census.

Recomputes the nine-field override counts from the live catalog. An item that
sets timeout_seconds must resolve provenance=item; an item that omits it must
resolve provenance=default. The receipt must carry the same census.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
from harness import NINE, per_field_override_census  # noqa: E402

ART = REPO / "command-center" / "receipts" / "CC-0001.json"
SENTINEL = "SUCCESS:CC-0001"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0001-probe1 {msg}")
    return 1


def main() -> int:
    catalog = cat.load()
    defaults = cat.catalog_defaults(catalog)
    if defaults is None:
        return fail("live defaults block missing")
    if cat.defaults_block_problems(catalog):
        return fail(f"defaults_block_problems={cat.defaults_block_problems(catalog)}")

    census = per_field_override_census(catalog)
    if census["items"] != 103:
        return fail(f"items={census['items']} want=103")
    for field in NINE:
        row = census["fields"][field]
        if row["item"] != 0 or row["default"] != 103 or row["unset"] != 0:
            return fail(f"census {field}={row}")

    sample = copy.deepcopy(cat.items(catalog)[0])
    sample.pop("timeout_seconds", None)
    omitted = cat.resolve_contract_field(sample, defaults, "timeout_seconds")
    if omitted["provenance"] != "default":
        return fail(f"omit provenance={omitted['provenance']}")
    if omitted["value"] != defaults["timeout_seconds"]:
        return fail("omit value != defaults.timeout_seconds")

    sample["timeout_seconds"] = 4242
    present = cat.resolve_contract_field(sample, defaults, "timeout_seconds")
    if present["provenance"] != "item":
        return fail(f"present provenance={present['provenance']} want=item")
    if present["value"] != 4242:
        return fail(f"present value={present['value']}")

    # Naive truthiness `or` is the forbidden form.
    null_item = copy.deepcopy(cat.items(catalog)[0])
    for field in NINE:
        null_item.pop(field, None)
    null_item["timeout_seconds"] = None
    null_view = cat.resolve_contract_field(null_item, defaults, "timeout_seconds")
    if null_view["provenance"] != "item" or null_view["value"] is not None:
        return fail(f"explicit-null {null_view}")
    naive = null_item.get("timeout_seconds") or defaults.get("timeout_seconds")
    if naive != defaults["timeout_seconds"]:
        return fail("naive control did not fall through")
    if null_view["value"] == naive:
        return fail("explicit-null fell through like `or`")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    stored = doc.get("override_census") or {}
    after = stored.get("after") or stored.get("fields") or {}
    if not after:
        return fail("receipt override_census.after missing")
    for field in NINE:
        stored_row = after.get(field) or {}
        live_row = census["fields"][field]
        if stored_row.get("item_over_n") != live_row["item_over_n"]:
            return fail(f"receipt census drifted for {field}")

    resolver = str(doc.get("resolver") or "")
    if "catalog.py" not in resolver:
        return fail(f"receipt resolver={resolver!r}")

    print(
        json.dumps(
            {
                "items": census["items"],
                "timeout_omit_provenance": omitted["provenance"],
                "timeout_item_provenance": present["provenance"],
                "timeout_item_value": present["value"],
                "explicit_null_provenance": null_view["provenance"],
                "census": {f: census["fields"][f]["item_over_n"] for f in NINE},
                "resolver": resolver,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CC-0001-probe1 resolver item|default live-0/103")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
