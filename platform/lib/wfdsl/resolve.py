"""Optional resolution of a catalog-level ``defaults`` block into a work unit.

The contract is deliberately asymmetric, and that asymmetry is the point:

* **raw mode** (the contract): every unit carries all 19 fields itself. A catalog whose
  units lean on ``defaults`` FAILS. Deleting the ``defaults`` block from a conformant catalog
  changes nothing.
* **resolved mode** (an explicit, opt-in convenience): a MISSING field may be filled from
  ``defaults`` so a partially-authored draft can be checked before it is completed. The
  resolver records exactly which fields it filled, so a "resolved" pass can never be mistaken
  for a raw pass.

``defaults`` in the live catalog uses the key ``assignment`` where a unit uses
``assigned_model_vendor_role``; that alias is handled explicitly rather than silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

#: catalog `defaults` key -> work-unit field name
DEFAULTS_ALIASES: dict[str, str] = {
    "assignment": "assigned_model_vendor_role",
}

MANDATED_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "phase",
    "question_or_target",
    "inputs",
    "dependencies",
    "assigned_model_vendor_role",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_path",
    "output_schema",
    "evidence_requirement",
    "tests_required",
    "reviewer_requirement",
    "completion_sentinel",
    "retry_policy",
    "failure_classification",
    "owner_approval_required",
)

#: fields that may NEVER be defaulted: they identify the unit or state its specific intent
NEVER_DEFAULTABLE: frozenset[str] = frozenset(
    {"id", "title", "phase", "question_or_target", "inputs", "dependencies", "output_path", "completion_sentinel"}
)


@dataclass
class Resolution:
    unit: dict[str, Any]
    filled: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)

    @property
    def used_defaults(self) -> bool:
        return bool(self.filled)


def normalise_defaults(defaults: Mapping[str, Any] | None) -> dict[str, Any]:
    """Map catalog ``defaults`` keys onto work-unit field names."""
    if not defaults:
        return {}
    out: dict[str, Any] = {}
    for key, value in defaults.items():
        out[DEFAULTS_ALIASES.get(key, key)] = value
    return out


def resolve_unit(unit: Mapping[str, Any], defaults: Mapping[str, Any] | None) -> Resolution:
    """Fill only MISSING, defaultable fields. Never overwrite a per-unit value."""
    merged = dict(unit)
    res = Resolution(unit=merged)
    norm = normalise_defaults(defaults)
    for fieldname in MANDATED_FIELDS:
        if fieldname in merged:
            continue
        if fieldname not in norm:
            continue
        if fieldname in NEVER_DEFAULTABLE:
            res.refused.append(fieldname)
            continue
        merged[fieldname] = norm[fieldname]
        res.filled.append(fieldname)
    return res


def missing_fields(unit: Mapping[str, Any]) -> list[str]:
    """Which of the 19 mandated fields this unit does not carry itself."""
    return [f for f in MANDATED_FIELDS if f not in unit]


def defaults_are_load_bearing(catalog: Mapping[str, Any]) -> dict[str, Any]:
    """Measure whether removing ``defaults`` would break any unit.

    Returns a report; ``load_bearing`` is True only if at least one unit is missing a field
    that ``defaults`` supplies - i.e. only if the block is doing contract work it must not do.
    """
    units = catalog.get("work_units") or []
    norm = normalise_defaults(catalog.get("defaults"))
    dependents: dict[str, list[str]] = {}
    for u in units:
        for f in missing_fields(u):
            if f in norm:
                dependents.setdefault(f, []).append(str(u.get("id")))
    return {
        "units": len(units),
        "defaults_present": bool(catalog.get("defaults")),
        "defaults_fields": sorted(norm),
        "load_bearing": bool(dependents),
        "fields_units_depend_on": {k: len(v) for k, v in dependents.items()},
        "sample": {k: v[:8] for k, v in dependents.items()},
    }
