"""Run the five catalog shapes plus the sixth reviewer shape."""
from __future__ import annotations

from pathlib import Path

from shapes import SIXTH_ID, SHAPE_IDS, ShapeTree, build_all
from walkers import (
    hardened_passes_shape,
    iter_files,
    naive_breaks_shape,
    posix_live_walk,
)


def materialize(work: Path) -> dict[str, ShapeTree]:
    return build_all(work)


def row_for(tree: ShapeTree) -> dict:
    oracle_paths = iter_files(tree.root)
    oracle = len(oracle_paths)
    naive_breaks, naive_why, naive = naive_breaks_shape(
        tree.shape_id, tree.root, oracle
    )
    hard_ok, hard_why, hardened = hardened_passes_shape(
        tree.shape_id, tree.root, oracle
    )
    posix = posix_live_walk(tree.root)
    return {
        "shape_id": tree.shape_id,
        "title": tree.title,
        "notes": tree.notes,
        "path_used": str(tree.root),
        "hazard_paths": [str(p) for p in tree.hazard_paths],
        "exact_files": [tree.rel(p) for p in tree.files],
        "oracle_count": oracle,
        "oracle_names": [p.relative_to(tree.root).as_posix() for p in oracle_paths],
        "extra": tree.extra,
        "posix_live": posix.as_dict(),
        "naive": {
            **naive.as_dict(),
            "breaks_shape": naive_breaks,
            "why": naive_why,
        },
        "hardened": {
            **hardened.as_dict(),
            "passes_shape": hard_ok,
            "why": hard_why,
        },
        "both_states": naive_breaks and hard_ok,
        "verbatim_naive_error_or_pass": naive.error or naive_why,
        "verbatim_hardened_error_or_pass": hardened.error or hard_why,
    }


def run_matrix(work: Path) -> dict:
    trees = materialize(work)
    catalog_rows = [row_for(trees[sid]) for sid in SHAPE_IDS]
    sixth = row_for(trees[SIXTH_ID])
    known_broken_ok = all(r["naive"]["breaks_shape"] for r in catalog_rows)
    both_states_ok = all(r["both_states"] for r in catalog_rows)
    silent_zero = next(
        r for r in catalog_rows if r["shape_id"] == "b-reserved-device"
    )
    case_row = next(
        r for r in catalog_rows if r["shape_id"] == "c-case-collision"
    )
    return {
        "catalog_shapes": catalog_rows,
        "sixth_shape": sixth,
        "known_broken_control": {
            "pass": known_broken_ok,
            "detail": (
                "each of the five catalog shapes breaks its naive implementation"
            ),
        },
        "both_states": {
            "pass": both_states_ok,
            "detail": "hardened passes all five; naive fails all five",
        },
        "silent_zero_control": {
            "pass": (
                silent_zero["naive"]["swallowed_to_zero"] is True
                and silent_zero["naive"]["count"] == 0
                and silent_zero["oracle_count"] > 0
                and silent_zero["hardened"]["swallowed_to_zero"] is False
                and silent_zero["hardened"]["count"]
                == silent_zero["oracle_count"]
            ),
            "naive_count": silent_zero["naive"]["count"],
            "hardened_count": silent_zero["hardened"]["count"],
            "oracle_count": silent_zero["oracle_count"],
            "naive_error": silent_zero["naive"]["error"],
            "detail": (
                "A reserved-name crash swallowed by the naive walker becomes "
                "count 0 while files exist; hardened keeps the oracle count."
            ),
        },
        "case_collision_control": {
            "pass": (
                case_row["extra"].get("case_distinct_siblings_present") is True
                and case_row["naive"]["count"] < case_row["oracle_count"]
                and any(
                    c.get("kind") == "case"
                    for c in case_row["hardened"]["collisions"]
                )
            ),
            "naive_count": case_row["naive"]["count"],
            "hardened_count": case_row["hardened"]["count"],
            "oracle_count": case_row["oracle_count"],
            "hardened_collisions": case_row["hardened"]["collisions"],
        },
        "reviewer_sixth": {
            "shape_id": sixth["shape_id"],
            "title": sixth["title"],
            "path_used": sixth["path_used"],
            "naive_breaks": sixth["naive"]["breaks_shape"],
            "hardened_passes": sixth["hardened"]["passes_shape"],
            "breaks_anything": sixth["naive"]["breaks_shape"],
            "verbatim": sixth["verbatim_naive_error_or_pass"],
        },
    }
