"""IMP-0436: per-unit override semantics for the nine globally-defaulted fields.

Precedence is enforced by catalog.resolve_field (unit wins; explicit JSON null
does not fall through). Deleting the defaults block must turn validate red
without requiring --require-complete.
"""

from __future__ import annotations

import copy
from typing import Any

import catalog as cat
import pytest
import validate as val

NINE = cat.OVERRIDEABLE_DEFAULT_FIELDS


def _mini_defaults() -> dict[str, Any]:
    return {
        "assignment": {"model": "opus", "vendor": "anthropic", "role": "implementer"},
        "tool_permissions": ["Read"],
        "execution_substrate": "local-windows-pwsh7",
        "timeout_seconds": 1800,
        "output_schema": "command-center/schema/receipt.schema.json",
        "tests_required": ["both-states"],
        "reviewer_requirement": "one independent reviewer",
        "retry_policy": "two strikes then pivot",
        "failure_classification": ["overclaim"],
    }


def _unit_all_defaults() -> dict[str, Any]:
    return {
        "id": "R-T01",
        "title": "all defaults",
        "phase": "t",
        "target": "t",
        "inputs": [],
        "dependencies": [],
        "output_path": "command-center/receipts/R-T01.json",
        "completion_sentinel": "SUCCESS:R-T01",
        "owner_approval_required": False,
        "program": "HARNESS",
        "section": "OUTSTANDING",
        "status": "OPEN",
        "disposition": None,
        "disposition_evidence": "",
        "effort": "S",
        "evidence": "fixture",
        "sources": [],
        "owner_gate": [],
        "security_class": "none",
        "next_smallest_action": "run fixture",
        "defer": None,
        "history": [],
    }


@pytest.mark.parametrize("field", NINE)
def test_precedence_unit_wins_per_field(field: str):
    defaults = _mini_defaults()
    item = _unit_all_defaults()
    override_values = {
        "assignment": {"model": "gpt", "vendor": "openai", "role": "refuter"},
        "tool_permissions": ["Write"],
        "execution_substrate": "linux-cloud-agent",
        "timeout_seconds": 60,
        "output_schema": "command-center/schema/other.schema.json",
        "tests_required": ["precedence"],
        "reviewer_requirement": "two independent reviewers",
        "retry_policy": "no retry",
        "failure_classification": ["detector-failure"],
    }
    item[field] = override_values[field]
    resolved = cat.resolve_field(item, defaults, field)
    assert resolved["provenance"] == "override"
    assert resolved["value"] == override_values[field]
    assert resolved["value"] != defaults[field]


@pytest.mark.parametrize("field", NINE)
def test_explicit_null_does_not_fall_through(field: str):
    defaults = _mini_defaults()
    item = _unit_all_defaults()
    item[field] = None
    resolved = cat.resolve_field(item, defaults, field)
    assert resolved["provenance"] == "explicit-null"
    assert resolved["value"] is None
    # Must NOT equal the default — that would be fall-through.
    assert resolved["value"] != defaults[field]


@pytest.mark.parametrize("field", NINE)
def test_missing_key_falls_through_to_default(field: str):
    defaults = _mini_defaults()
    item = _unit_all_defaults()
    assert field not in item
    resolved = cat.resolve_field(item, defaults, field)
    assert resolved["provenance"] == "default"
    assert resolved["value"] == defaults[field]


def test_assignment_alias_counts_as_override():
    defaults = _mini_defaults()
    item = _unit_all_defaults()
    item["assigned_model_vendor_role"] = {
        "model": "codex",
        "vendor": "openai",
        "role": "reviewer",
    }
    resolved = cat.resolve_field(item, defaults, "assignment")
    assert resolved["provenance"] == "override"
    assert resolved["value"]["model"] == "codex"


def test_resolve_unit_three_shapes():
    defaults = _mini_defaults()
    all_def = _unit_all_defaults()
    three = _unit_all_defaults()
    three["id"] = "R-T02"
    three["timeout_seconds"] = 99
    three["reviewer_requirement"] = "schema-reviewer"
    three["retry_policy"] = "once"
    all_nine = _unit_all_defaults()
    all_nine["id"] = "R-T03"
    for field in NINE:
        all_nine[field] = None if field == "timeout_seconds" else f"override-{field}"

    views = [
        cat.resolve_unit(all_def, defaults),
        cat.resolve_unit(three, defaults),
        cat.resolve_unit(all_nine, defaults),
    ]
    assert all(v["fields"][f]["provenance"] == "default" for f in NINE for v in [views[0]])
    assert views[1]["fields"]["timeout_seconds"]["provenance"] == "override"
    assert views[1]["fields"]["assignment"]["provenance"] == "default"
    assert sum(1 for f in NINE if views[1]["fields"][f]["provenance"] == "override") == 3
    assert views[2]["fields"]["timeout_seconds"]["provenance"] == "explicit-null"
    assert all(
        views[2]["fields"][f]["provenance"] in ("override", "explicit-null") for f in NINE
    )


def test_defaults_block_deletion_is_caught_without_require_complete(real):
    bad = copy.deepcopy(real)
    del bad["defaults"]
    violations, _ = val.validate(bad, require_complete=False)
    assert "V-DEFAULTS" in {v["check"] for v in violations}
    assert any("defaults" in v["detail"] for v in violations)


def test_single_default_field_deletion_caught_when_items_rely(real):
    bad = copy.deepcopy(real)
    del bad["defaults"]["timeout_seconds"]
    violations, _ = val.validate(bad, require_complete=False)
    assert "V-DEFAULTS" in {v["check"] for v in violations}
    assert any("timeout_seconds" in v["detail"] for v in violations)


def test_real_catalog_still_clean_with_v_defaults(real, real_graph):
    violations, stats = val.validate(real, graph=real_graph)
    assert violations == []
    assert stats["work_unit_fields_from_defaults"] >= 9 * stats["items"]


@pytest.fixture(scope="module")
def real() -> dict:
    return cat.load()


@pytest.fixture(scope="module")
def real_graph() -> dict:
    import json

    return json.loads(cat.graph_path().read_text(encoding="utf-8"))
