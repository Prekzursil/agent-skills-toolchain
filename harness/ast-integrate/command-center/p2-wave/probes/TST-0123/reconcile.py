"""Bidirectional set difference: registry ids vs collected ids.

Counts are computed from two sets. The collected set is parsed from the
runner listing, never from a source grep.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from collect_runner import (
    collect_live,
    collect_tree_stdlib,
    format_listing,
    parse_listing,
)
from registry import LIVE_REGISTRY, load_registry

HERE = Path(__file__).resolve().parent
FIXTURE_SUITE = HERE / "fixtures" / "suite"
PLANTED_ORPHAN_ID = "test_core.py::TestCore::test_planted_orphan_never_collected"
ALPHA_ID = "test_core.py::TestCore::test_alpha"
BETA_ID = "test_core.py::TestCore::test_beta"


def difference(registry_ids: list[str] | set[str], collected_ids: list[str] | set[str]) -> dict[str, Any]:
    reg = set(registry_ids)
    col = set(collected_ids)
    registry_only = sorted(reg - col)
    collected_only = sorted(col - reg)
    both = sorted(reg & col)
    return {
        "registry_count": len(reg),
        "collected_count": len(col),
        "intersection_count": len(both),
        "registry_only": {"count": len(registry_only), "ids": registry_only},
        "collected_only": {"count": len(collected_only), "ids": collected_only},
        "reconciled": len(registry_only) == 0 and len(collected_only) == 0,
    }


def reconcile_from_listing(listing: str, registry_ids: list[str] | set[str]) -> dict[str, Any]:
    collected = parse_listing(listing)
    diff = difference(registry_ids, collected)
    diff["collected_ids"] = collected
    diff["listing_sha_prefix"] = str(len(listing))
    return diff


def collect_and_reconcile(suite: Path, registry_path: Path) -> dict[str, Any]:
    blob = collect_tree_stdlib(suite, id_root=suite)
    listing = format_listing(blob)
    collected_from_text = parse_listing(listing)
    if collected_from_text != blob["collected"]:
        raise RuntimeError("listing parser disagreed with collector blob")
    reg = load_registry(registry_path)
    diff = difference(reg["ids"], collected_from_text)
    return {
        "registry": {k: v for k, v in reg.items() if k != "ids"} | {"ids": reg["ids"]},
        "listing": listing,
        "collected_ids": collected_from_text,
        "collection_errors": blob["errors"],
        "runner": blob["runner"],
        **diff,
    }


def live_reconcile() -> dict[str, Any]:
    blob = collect_live()
    listing = format_listing(blob)
    collected = parse_listing(listing)
    reg = load_registry(LIVE_REGISTRY)
    diff = difference(reg["ids"], collected)
    return {
        "registry": {
            "present": reg["present"],
            "path": "command-center/TEST-REGISTRY.json",
            "granularity": reg["granularity"],
            "raw_entry_count": reg["raw_entry_count"],
            "count_only_suites": reg["count_only_suites"],
            "function_names": reg["function_names"],
            "ids": reg["ids"],
        },
        "listing": listing,
        "collected_ids": collected,
        "collection_errors": blob["errors"],
        "runner": blob["runner"],
        "pytest": blob.get("pytest"),
        "live_roots": blob.get("live_roots"),
        **diff,
    }
