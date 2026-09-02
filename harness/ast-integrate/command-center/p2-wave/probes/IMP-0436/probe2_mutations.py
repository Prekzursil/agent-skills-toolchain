#!/usr/bin/env python3
"""Named probe 2: precedence per field, explicit-null, defaults-block mutation.

Adversarial half of IMP-0436's reviewer_requirement: null must not fall
through, and deleting the defaults block must be caught with
require_complete left False (the CI-bare invocation).
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
import validate as val  # noqa: E402
from scenario import DISTINCT  # noqa: E402

NINE = cat.OVERRIDEABLE_FIELDS


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0436-probe2 {msg}")
    return 1


def main() -> int:
    live = cat.load()
    defaults = cat.catalog_defaults(live)
    if defaults is None:
        return fail("live defaults missing")
    sample = copy.deepcopy(cat.items(live)[0])
    for field in NINE:
        sample.pop(field, None)

    # Precedence per field against the LIVE defaults block.
    for field in NINE:
        item = copy.deepcopy(sample)
        item[field] = copy.deepcopy(DISTINCT[field])
        view = cat.resolve_field(item, defaults, field)
        if view["provenance"] != cat.PROVENANCE_OVERRIDE:
            return fail(f"precedence {field} provenance={view['provenance']}")
        if view["value"] != DISTINCT[field]:
            return fail(f"precedence {field} value")
        for other in NINE:
            if other == field:
                continue
            other_view = cat.resolve_field(item, defaults, other)
            if other_view["provenance"] != cat.PROVENANCE_DEFAULT:
                return fail(f"precedence {field} leaked onto {other}")
            if other_view["value"] != defaults[other]:
                return fail(f"precedence {field} mutated {other}")

    # Explicit null is not fall-through. Contrast with the `or` form.
    null_item = copy.deepcopy(sample)
    null_item["timeout_seconds"] = None
    null_view = cat.resolve_field(null_item, defaults, "timeout_seconds")
    if null_view["provenance"] != cat.PROVENANCE_OVERRIDE or null_view["value"] is not None:
        return fail(f"explicit-null view={null_view}")
    naive = null_item.get("timeout_seconds") or defaults.get("timeout_seconds")
    if naive != defaults["timeout_seconds"]:
        return fail("naive control did not fall through (instrument broken)")
    if null_view["value"] == naive:
        return fail("explicit-null fell through like `or`")

    # 0 and [] must also not fall through (truthiness trap).
    zero_item = copy.deepcopy(sample)
    zero_item["timeout_seconds"] = 0
    zero_item["tool_permissions"] = []
    z_t = cat.resolve_field(zero_item, defaults, "timeout_seconds")
    z_p = cat.resolve_field(zero_item, defaults, "tool_permissions")
    if z_t != {
        "field": "timeout_seconds",
        "value": 0,
        "provenance": cat.PROVENANCE_OVERRIDE,
    }:
        return fail(f"zero-timeout {z_t}")
    if z_p != {
        "field": "tool_permissions",
        "value": [],
        "provenance": cat.PROVENANCE_OVERRIDE,
    }:
        return fail(f"empty-permissions {z_p}")

    # Both-states on the defaults-block mutation. require_complete stays False.
    good, _ = val.validate(live, require_complete=False)
    if any(v["check"] == "V-DEFAULTS" for v in good):
        return fail("control V-DEFAULTS on unmodified catalog")

    deleted = copy.deepcopy(live)
    del deleted["defaults"]
    bad, _ = val.validate(deleted, require_complete=False)
    if not any(
        v["check"] == "V-DEFAULTS" and "missing or not an object" in v["detail"]
        for v in bad
    ):
        return fail(f"deleted defaults not caught; checks={[v['check'] for v in bad[:8]]}")

    # Same mutation must leave the nine fields UNSET, not silently defaulted.
    orphan = copy.deepcopy(sample)
    unset_view = cat.resolve_item(orphan, cat.catalog_defaults(deleted))
    if unset_view["unset_count"] != 9:
        return fail(f"deleted defaults left unset_count={unset_view['unset_count']}")

    print(
        json.dumps(
            {
                "precedence_fields": list(NINE),
                "explicit_null_provenance": null_view["provenance"],
                "explicit_null_value": null_view["value"],
                "naive_or_would_yield": naive,
                "zero_timeout_provenance": z_t["provenance"],
                "empty_permissions_provenance": z_p["provenance"],
                "control_v_defaults": 0,
                "deleted_defaults_v_defaults": sum(
                    1 for v in bad if v["check"] == "V-DEFAULTS"
                ),
                "deleted_defaults_unset_count": unset_view["unset_count"],
                "require_complete": False,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0436-probe2 precedence null defaults-deletion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
