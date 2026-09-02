#!/usr/bin/env python3
"""Never-selected capability detector specified by RES-0106.

A popular-query regression suite cannot see a capability that exists but is
never chosen. This detector joins three data sources:

  1. capability catalog (id, selectable, never_select_reason)
  2. golden query set (query_id -> expected_capability_ids)
  3. selection log produced by running those queries (or a production window)

It fires only when a *selectable* capability is an expected gold label and
still never appears in the selection log. Capabilities marked selectable=false
are the false-alarm case (they SHOULD never be selected).
"""
from __future__ import annotations

from typing import Any, Iterable


def _ids(rows: Iterable[dict], key: str) -> set[str]:
    out: set[str] = set()
    for row in rows:
        for item in row.get(key) or []:
            if isinstance(item, str) and item:
                out.add(item)
    return out


def run_detector(
    catalog: list[dict[str, Any]],
    golden_queries: list[dict[str, Any]],
    selection_log: list[dict[str, Any]],
) -> dict[str, Any]:
    selectable = {
        str(c["id"])
        for c in catalog
        if c.get("selectable") is True and c.get("id")
    }
    never_by_design = {
        str(c["id"]): str(c.get("never_select_reason") or "never-select-by-design")
        for c in catalog
        if c.get("selectable") is False and c.get("id")
    }
    expected = _ids(golden_queries, "expected_capability_ids")
    selected = _ids(selection_log, "selected_capability_ids")

    routing_defect = sorted((expected & selectable) - selected)
    corpus_gap = sorted(selectable - expected)
    leaked = sorted(set(never_by_design) & set(routing_defect))

    return {
        "reads": [
            "capability_catalog",
            "golden_query_set",
            "selection_log",
        ],
        "selectable_count": len(selectable),
        "never_by_design_ids": sorted(never_by_design),
        "never_by_design_reasons": never_by_design,
        "gold_expected_ids": sorted(expected),
        "selected_ids": sorted(selected),
        "never_selected_routing_defect": routing_defect,
        "corpus_gap_unlabeled_selectable": corpus_gap,
        "false_alarm_leak": leaked,
        "fires": bool(routing_defect),
    }


def naive_catalog_minus_selected(
    catalog: list[dict[str, Any]],
    selection_log: list[dict[str, Any]],
) -> list[str]:
    """Broken cousin: treats every catalog member as must-be-selected.

    This is the false-alarm generator: a should-never-select capability
    (kill-switch, decoy, deprecated-kept-for-rollback) shows up as a 'defect'.
    """
    catalog_ids = {str(c["id"]) for c in catalog if c.get("id")}
    selected = _ids(selection_log, "selected_capability_ids")
    return sorted(catalog_ids - selected)
