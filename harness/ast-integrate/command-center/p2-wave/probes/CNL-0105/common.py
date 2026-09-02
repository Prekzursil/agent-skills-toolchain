#!/usr/bin/env python3
"""CNL-0105 shared paths, 20-key reconstruction, typed-delta apply."""
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = (
    "command-center/design/council/"
    "CNL-0105-anonymous-peer-review-preset-with-an-author-rebuttal-round.md"
)
SCHEMA_REL = "command-center/schema/council-preset.schema.json"
FIXTURES = HERE / "fixtures" / "records.json"

# CNL-0101 names editable_dials and default_binding. The other 18 names are
# reconstructed from CouncilSpec section names + preset overlay fields because
# 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree.
CATALOG_CITED_KEYS = ("editable_dials", "default_binding")
PRESET_KEYS: tuple[str, ...] = (
    "id",
    "name",
    "family",
    "base_spec",
    "base_spec_version",
    "delta",
    "default_binding",
    "editable_dials",
    "protocol_bindings",
    "roles",
    "voting",
    "stopping",
    "anonymity",
    "recruitment",
    "rebuttal",
    "evidence",
    "integrity",
    "outcomes",
    "budgets",
    "meta",
)
assert len(PRESET_KEYS) == 20
DELTA_SECTIONS = (
    "protocol_bindings",
    "roles",
    "voting",
    "stopping",
    "anonymity",
    "recruitment",
    "rebuttal",
    "evidence",
    "integrity",
    "outcomes",
    "budgets",
)


class Reject(ValueError):
    """Preset or operator overlay rejected."""


def load_records() -> dict:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def materialize_preset(raw: dict) -> dict:
    """Flatten delta onto the 20-key preset record (still a delta, not a fork)."""
    delta = raw.get("delta") or {}
    out = {k: copy.deepcopy(raw[k]) for k in (
        "id", "name", "family", "base_spec", "base_spec_version",
        "delta", "default_binding", "editable_dials", "meta",
    )}
    for section in DELTA_SECTIONS:
        if section in delta:
            out[section] = copy.deepcopy(delta[section])
        elif section in raw:
            out[section] = copy.deepcopy(raw[section])
        else:
            raise Reject(f"preset {raw.get('id')} missing delta section {section}")
    missing = [k for k in PRESET_KEYS if k not in out]
    if missing:
        raise Reject(f"preset missing keys {missing}")
    extra = [k for k in out if k not in PRESET_KEYS]
    if extra:
        raise Reject(f"preset extra keys {extra}")
    return out


def apply_operator_overlay(preset: dict, overlay: dict) -> dict:
    """Operator edits may touch only editable_dials. Silent non-editable override is REJECTED."""
    allowed = set(preset.get("editable_dials") or [])
    for dotted, _value in overlay.items():
        if dotted not in allowed:
            raise Reject(
                f"silent override of non-editable dial {dotted!r} rejected "
                f"(editable_dials={sorted(allowed)})"
            )
    updated = copy.deepcopy(preset)
    for dotted, value in overlay.items():
        parts = dotted.split(".")
        cursor = updated
        for p in parts[:-1]:
            cursor = cursor[p]
        cursor[parts[-1]] = value
        dcur = updated["delta"]
        for p in parts[:-1]:
            dcur = dcur[p]
        dcur[parts[-1]] = value
    return updated


def resolve_against_base(preset: dict, base: dict) -> dict:
    """Resolved CouncilSpec view: base then delta. Preset is a delta, not a fork."""
    resolved = copy.deepcopy(base)
    delta = preset.get("delta") or {}
    for section, value in delta.items():
        resolved[section] = copy.deepcopy(value)
    resolved["preset_id"] = preset["id"]
    resolved["base_spec"] = preset["base_spec"]
    resolved["base_spec_version"] = preset["base_spec_version"]
    if preset["base_spec_version"] != base.get("version"):
        resolved["migration"] = "needs-migration"
    else:
        resolved["migration"] = "current"
    return resolved
