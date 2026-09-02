"""Three-unit resolved-view fixture for IMP-0436.

Cases the evidence requirement names:
  * all-defaults  — item sets none of the nine overridable fields
  * override-three — item sets timeout_seconds, execution_substrate, retry_policy
  * override-nine  — item sets all nine

Built from live catalog items so the dump is against the real defaults block,
not a re-typed copy of seed.DEFAULTS.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
CC = REPO / "tools" / "command-center"
if str(CC) not in sys.path:
    sys.path.insert(0, str(CC))

import catalog as cat  # noqa: E402

THREE = ("timeout_seconds", "execution_substrate", "retry_policy")

DISTINCT: dict[str, Any] = {
    "assignment": {
        "basis": "IMP-0436-override",
        "model": "override-model",
        "role": "override-role",
        "vendor": "override-vendor",
    },
    "tool_permissions": ["Read", "IMP-0436-only"],
    "execution_substrate": "worktree-isolated",
    "timeout_seconds": 99,
    "output_schema": "command-center/schema/work-unit.schema.json",
    "tests_required": ["IMP-0436-override-test"],
    "reviewer_requirement": "IMP-0436-override-reviewer",
    "retry_policy": "IMP-0436-no-retry",
    "failure_classification": ["IMP-0436-override-class"],
}


def _strip_nine(item: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(item)
    for field in cat.OVERRIDEABLE_FIELDS:
        out.pop(field, None)
    return out


def three_cases(catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    catalog = catalog if catalog is not None else cat.load()
    pool = cat.items(catalog)
    if len(pool) < 3:
        raise RuntimeError("catalog holds fewer than 3 items")
    defaults = cat.catalog_defaults(catalog)
    all_defaults = _strip_nine(pool[0])
    three = _strip_nine(pool[1])
    for field in THREE:
        three[field] = copy.deepcopy(DISTINCT[field])
    nine = _strip_nine(pool[2])
    for field in cat.OVERRIDEABLE_FIELDS:
        nine[field] = copy.deepcopy(DISTINCT[field])
    rows = [
        ("all-defaults", all_defaults),
        ("override-three", three),
        ("override-nine", nine),
    ]
    views: list[dict[str, Any]] = []
    for case, item in rows:
        view = cat.resolve_item(item, defaults)
        view["case"] = case
        views.append(view)
    return views


def live_override_census(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = catalog if catalog is not None else cat.load()
    hits = cat.items_overriding(catalog)
    return {
        "items": len(cat.items(catalog)),
        "items_overriding_any_of_nine": len(hits),
        "overriding_ids": hits,
        "defaults_block_problems": cat.defaults_block_problems(catalog),
    }
