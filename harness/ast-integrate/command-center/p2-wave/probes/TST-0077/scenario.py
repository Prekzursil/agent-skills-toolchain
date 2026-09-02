#!/usr/bin/env python3
"""Live TST-0077 scenario: reconstruct, migrate, compare, idempotency, no-path."""
from __future__ import annotations

from typing import Any

from engine import (
    AMBIGUOUS,
    CURRENT,
    LEGACY,
    NO_PATH,
    classify,
    comparison_report,
    extract_user_data,
    is_current,
    migrate,
    migrate_idempotent,
    overlay_user_data,
    round_trip,
    trees_equal,
)
from reconstruct import reconstruct_all


def _row_result(rec: dict[str, Any], layout: dict[str, Any]) -> dict[str, Any]:
    templates = rec["templates"]
    clean = rec["clean_install"]
    tree = layout["tree"]
    user = extract_user_data(tree, clean)
    expected = overlay_user_data(clean, user)
    result = migrate(tree, templates)
    migrated = result["tree"]
    cmp_ = comparison_report(tree, migrated, expected)
    ident = migrate_idempotent(tree, templates)
    return {
        "id": layout["id"],
        "fingerprint": layout["fingerprint"],
        "has_migration_path": layout["has_migration_path"],
        "reconstruction_method": layout["reconstruction_method"],
        "git_head": layout.get("git_head"),
        "source_note": layout["source_note"],
        "classify_before": result["before"],
        "classify_after": result["after"],
        "steps_run": result["steps_run"],
        "migrate_status": result["status"],
        "reported": result.get("reported"),
        "skipped": result.get("skipped"),
        "byte_equivalent": cmp_["byte_equivalent"],
        "comparison": cmp_,
        "idempotent": ident["idempotent"],
        "after_is_current": is_current(migrated) if layout["has_migration_path"] else None,
        "user_data": {
            "skill_extra_lines": user["skill_extra_lines"],
            "disabled_mcp": user["disabled_mcp"],
            "mcp_server_ids": sorted((user["mcp_servers"] or {}).keys()),
            "user_settings": user["user_settings"],
            "hooks": (user["hooks_manifest"] or {}).get("hooks"),
        },
    }


def run_scenario() -> dict[str, Any]:
    rec = reconstruct_all()
    templates = rec["templates"]
    clean = rec["clean_install"]

    clean_class = classify(clean)
    current_zero_legacy = clean_class["kind"] == CURRENT and not clean_class["fingerprints"]

    migrated_rows = [_row_result(rec, layout) for layout in rec["layouts_with_path"]]
    nopath_rows = [_row_result(rec, layout) for layout in rec["layouts_without_path"]]

    t1_ok = all(
        r["classify_before"]["kind"] == LEGACY
        and r["byte_equivalent"]
        and r["after_is_current"]
        and r["migrate_status"] == CURRENT
        for r in migrated_rows
    )
    t2_ok = all(r["idempotent"] for r in migrated_rows)

    unknown = next(r for r in nopath_rows if r["id"] == "legacy-flat-ini")
    hybrid = next(r for r in nopath_rows if r["id"] == "hybrid-mcp-and-pre-dispatch")
    unknown_tree = rec["layouts_without_path"][0]["tree"]
    skip_mutant = migrate(unknown_tree, templates, skip_unknown=True)

    t3_unknown_reported = (
        unknown["migrate_status"] == NO_PATH
        and unknown["reported"] is True
        and unknown["skipped"] is False
        and trees_equal(unknown_tree, rec["layouts_without_path"][0]["tree"])
    )
    t3_hybrid_reported = (
        hybrid["migrate_status"] == AMBIGUOUS
        and hybrid["reported"] is True
        and hybrid["skipped"] is False
    )
    t3_skip_mutant_is_wrong = (
        skip_mutant.get("skipped") is True and skip_mutant.get("reported") is False
    )
    t3_ok = t3_unknown_reported and t3_hybrid_reported and t3_skip_mutant_is_wrong

    rt_ok = True
    rt_rows = []
    for layout in rec["layouts_with_path"]:
        good = round_trip(layout["tree"], templates, broken_v1_inverse=False)
        rt_rows.append({"id": layout["id"], "restored": good["restored"], "broken": False})
        rt_ok = rt_ok and good["restored"]
    copied = next(
        layout
        for layout in rec["layouts_with_path"]
        if layout["id"] == "copied-skills-pre-marketplace"
    )
    broken = round_trip(copied["tree"], templates, broken_v1_inverse=True)
    broken_fires = broken["restored"] is False

    passed = t1_ok and t2_ok and t3_ok and current_zero_legacy and rt_ok and broken_fires
    which_exist = [r["id"] for r in migrated_rows]
    which_no_path = [
        {"id": r["id"], "status": r["migrate_status"], "reported": r["reported"]}
        for r in nopath_rows
    ]
    return {
        "pass": passed,
        "git": rec["git"],
        "reconstruction_method": rec["reconstruction_method"],
        "source_files": rec["source_files"],
        "user_overlay": rec["user_overlay"],
        "current_layout_matches_zero_legacy_fingerprints": current_zero_legacy,
        "historical_layouts_with_path": which_exist,
        "historical_layouts_without_path": which_no_path,
        "answer": {
            "which_historical_layouts_exist": which_exist,
            "which_have_no_migration_path": [r["id"] for r in nopath_rows],
            "reconstruction_method": rec["reconstruction_method"],
            "git_head": rec["git"].get("head"),
        },
        "tests": {
            "test_migration_from_each_reconstructed_layout": {
                "pass": t1_ok,
                "layouts": [
                    {
                        "id": r["id"],
                        "byte_equivalent": r["byte_equivalent"],
                        "after_is_current": r["after_is_current"],
                        "steps_run": r["steps_run"],
                        "mismatch": {
                            "only_in_migrated": r["comparison"]["only_in_migrated"],
                            "only_in_expected": r["comparison"]["only_in_expected"],
                            "sha_mismatch_paths": r["comparison"]["sha_mismatch_paths"],
                        },
                    }
                    for r in migrated_rows
                ],
            },
            "test_migration_is_idempotent": {
                "pass": t2_ok,
                "per_layout": [
                    {"id": r["id"], "idempotent": r["idempotent"]} for r in migrated_rows
                ],
            },
            "test_a_layout_with_no_migration_is_reported_not_skipped": {
                "pass": t3_ok,
                "unknown_reported_not_skipped": t3_unknown_reported,
                "hybrid_reported_ambiguous": t3_hybrid_reported,
                "skip_mutant_would_hide_unknown": t3_skip_mutant_is_wrong,
                "skip_mutant": {
                    "status": skip_mutant.get("status"),
                    "skipped": skip_mutant.get("skipped"),
                    "reported": skip_mutant.get("reported"),
                },
            },
        },
        "round_trip": {"pass": rt_ok, "rows": rt_rows},
        "negative_control_wrong_inverse": {
            "pass": broken_fires,
            "restored": broken["restored"],
            "note": "A deliberately wrong inverse (drop skills) must fail round-trip.",
        },
        "layout_rows": migrated_rows,
        "nopath_rows": nopath_rows,
    }
