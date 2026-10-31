"""Precedence, explicit-null, and defaults-block deletion for the nine fields.

IMP-0436: a unit key present -- including JSON null, 0, False, or [] -- wins
over the catalog defaults block. An absent key falls through. Deleting the
defaults block is caught by V-DEFAULTS with --require-complete left off.
"""

from __future__ import annotations

import copy

import catalog as cat
import validate as val

NINE = cat.OVERRIDEABLE_FIELDS

DISTINCT = {
    "assignment": {
        "basis": "test-override",
        "model": "override-model",
        "role": "override-role",
        "vendor": "override-vendor",
    },
    "tool_permissions": ["Read", "test-only"],
    "execution_substrate": "worktree-isolated",
    "timeout_seconds": 99,
    "output_schema": "command-center/schema/work-unit.schema.json",
    "tests_required": ["override-test"],
    "reviewer_requirement": "override-reviewer",
    "retry_policy": "no-retry",
    "failure_classification": ["override-class"],
}


def _stripped(item: dict) -> dict:
    out = copy.deepcopy(item)
    for field in NINE:
        out.pop(field, None)
    return out


def test_live_catalog_has_103_items_and_zero_overrides():
    catalog = cat.load()
    assert len(cat.items(catalog)) == 103
    assert cat.items_overriding(catalog) == []
    assert cat.defaults_block_problems(catalog) == []
    defaults = cat.catalog_defaults(catalog)
    assert defaults is not None
    for field in NINE:
        assert field in defaults


def test_precedence_per_field_against_live_defaults():
    catalog = cat.load()
    defaults = cat.catalog_defaults(catalog)
    sample = _stripped(cat.items(catalog)[0])
    for field in NINE:
        item = copy.deepcopy(sample)
        item[field] = copy.deepcopy(DISTINCT[field])
        view = cat.resolve_field(item, defaults, field)
        assert view["provenance"] == cat.PROVENANCE_OVERRIDE
        assert view["value"] == DISTINCT[field]
        for other in NINE:
            if other == field:
                continue
            other_view = cat.resolve_field(item, defaults, other)
            assert other_view["provenance"] == cat.PROVENANCE_DEFAULT
            assert other_view["value"] == defaults[other]


def test_explicit_null_does_not_fall_through():
    catalog = cat.load()
    defaults = cat.catalog_defaults(catalog)
    item = _stripped(cat.items(catalog)[0])
    item["timeout_seconds"] = None
    view = cat.resolve_field(item, defaults, "timeout_seconds")
    assert view["provenance"] == cat.PROVENANCE_OVERRIDE
    assert view["value"] is None
    naive = item.get("timeout_seconds") or defaults.get("timeout_seconds")
    assert naive == defaults["timeout_seconds"]
    assert view["value"] != naive


def test_zero_and_empty_list_are_overrides():
    catalog = cat.load()
    defaults = cat.catalog_defaults(catalog)
    item = _stripped(cat.items(catalog)[0])
    item["timeout_seconds"] = 0
    item["tool_permissions"] = []
    assert cat.resolve_field(item, defaults, "timeout_seconds") == {
        "field": "timeout_seconds",
        "value": 0,
        "provenance": cat.PROVENANCE_OVERRIDE,
    }
    assert cat.resolve_field(item, defaults, "tool_permissions") == {
        "field": "tool_permissions",
        "value": [],
        "provenance": cat.PROVENANCE_OVERRIDE,
    }


def test_three_unit_resolved_dump_counts():
    catalog = cat.load()
    defaults = cat.catalog_defaults(catalog)
    pool = cat.items(catalog)
    all_defaults = _stripped(pool[0])
    three = _stripped(pool[1])
    three["timeout_seconds"] = 99
    three["execution_substrate"] = "worktree-isolated"
    three["retry_policy"] = "no-retry"
    nine = _stripped(pool[2])
    for field in NINE:
        nine[field] = copy.deepcopy(DISTINCT[field])
    views = [
        cat.resolve_item(all_defaults, defaults),
        cat.resolve_item(three, defaults),
        cat.resolve_item(nine, defaults),
    ]
    assert views[0]["override_count"] == 0 and views[0]["default_count"] == 9
    assert views[1]["override_count"] == 3 and views[1]["default_count"] == 6
    assert views[2]["override_count"] == 9 and views[2]["default_count"] == 0
    assert all(v["unset_count"] == 0 for v in views)


def test_deleted_defaults_block_is_v_defaults_with_require_complete_off():
    live = cat.load()
    good, _ = val.validate(live, require_complete=False)
    assert not any(v["check"] == "V-DEFAULTS" for v in good)
    deleted = copy.deepcopy(live)
    del deleted["defaults"]
    bad, _ = val.validate(deleted, require_complete=False)
    assert any(
        v["check"] == "V-DEFAULTS" and "missing or not an object" in v["detail"]
        for v in bad
    )
    orphan = _stripped(cat.items(live)[0])
    unset_view = cat.resolve_item(orphan, cat.catalog_defaults(deleted))
    assert unset_view["unset_count"] == 9


def test_resolve_contract_field_uses_item_token():
    catalog = cat.load()
    defaults = cat.catalog_defaults(catalog)
    item = _stripped(cat.items(catalog)[0])
    omitted = cat.resolve_contract_field(item, defaults, "timeout_seconds")
    assert omitted["provenance"] == cat.PROVENANCE_DEFAULT
    item["timeout_seconds"] = 4242
    present = cat.resolve_contract_field(item, defaults, "timeout_seconds")
    assert present["provenance"] == cat.PROVENANCE_ITEM
    assert present["value"] == 4242
