#!/usr/bin/env python3
"""Recall control: found/planted with a named miss list. Never a bare percentage."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
import scout as S  # noqa: E402

PLANTS = HERE / "fixtures" / "plants.json"


def load_plants(path: Path | None = None) -> dict:
    return json.loads((path or PLANTS).read_text(encoding="utf-8"))


def _hit_ids(result: dict) -> list[str]:
    return [h["id"] for h in (result.get("ranked") or [])]


def measure(
    mode: str = "live",
    corpus_root: Path | None = None,
    exclude_ids: frozenset[str] | None = None,
    plants: dict | None = None,
) -> dict:
    spec = plants if plants is not None else load_plants()
    present = spec.get("known_present") or []
    absent = spec.get("known_absent") or []
    workflows = S.load_workflows(corpus_root=corpus_root, exclude_ids=exclude_ids)

    present_rows = []
    misses: list[dict] = []
    build_when_superior: list[dict] = []
    ranked_below_rebuild: list[dict] = []

    for plant in present:
        goal = plant["goal"]
        result = S.scout(
            goal,
            workflows=workflows,
            mode=mode,
            corpus_root=corpus_root,
            exclude_ids=exclude_ids,
        )
        ids = _hit_ids(result)
        want = plant["workflow_id"]
        found = want in ids
        rank = ids.index(want) + 1 if found else None
        inferior = plant.get("inferior_rebuild_id")
        rebuild_rank = ids.index(inferior) + 1 if inferior and inferior in ids else None
        row = {
            "plant_id": plant["id"],
            "workflow_id": want,
            "source_class": plant.get("source_class"),
            "recall_token": plant.get("recall_token"),
            "goal_id": goal.get("id"),
            "found": found,
            "rank": rank,
            "ranked_ids": ids,
            "recommendation": result["recommendation"],
            "cited_existing": result.get("cited_existing"),
            "recommendation_reason": result.get("recommendation_reason"),
            "evidence_anchor": None
            if not found
            else next(
                (
                    h["evidence_anchor"]
                    for h in result["ranked"]
                    if h["id"] == want
                ),
                None,
            ),
        }
        present_rows.append(row)
        if not found:
            misses.append(
                {
                    "plant_id": plant["id"],
                    "workflow_id": want,
                    "source_class": plant.get("source_class"),
                    "recall_token": plant.get("recall_token"),
                    "ranked_ids": ids,
                    "reason": "planted-workflow-absent-from-ranked-set",
                }
            )
        if result["recommendation"] == "BUILD" and found:
            build_when_superior.append(
                {
                    "plant_id": plant["id"],
                    "workflow_id": want,
                    "cited_existing": result.get("cited_existing"),
                    "reason": "BUILD-while-superior-present",
                }
            )
        if (
            found
            and inferior
            and rebuild_rank is not None
            and rank is not None
            and rank > rebuild_rank
        ):
            ranked_below_rebuild.append(
                {
                    "plant_id": plant["id"],
                    "workflow_id": want,
                    "rank": rank,
                    "rebuild_id": inferior,
                    "rebuild_rank": rebuild_rank,
                }
            )

    absent_rows = []
    absent_nonempty: list[dict] = []
    for plant in absent:
        goal = plant["goal"]
        result = S.scout(
            goal,
            workflows=workflows,
            mode=mode,
            corpus_root=corpus_root,
            exclude_ids=exclude_ids,
        )
        ids = _hit_ids(result)
        empty = len(ids) == 0
        row = {
            "plant_id": plant["id"],
            "goal_id": goal.get("id"),
            "recall_token": plant.get("recall_token"),
            "empty_ranked_set": empty,
            "ranked_ids": ids,
            "recommendation": result["recommendation"],
        }
        absent_rows.append(row)
        if not empty:
            absent_nonempty.append(
                {
                    "plant_id": plant["id"],
                    "ranked_ids": ids,
                    "reason": "known-absent-goal-returned-hits",
                }
            )

    planted = len(present)
    found_n = sum(1 for r in present_rows if r["found"])
    return {
        "mode": mode,
        "workflows_scanned": len(workflows),
        "planted": planted,
        "found": found_n,
        "recall_fraction": f"{found_n}/{planted}",
        "miss_list": misses,
        "known_present": present_rows,
        "known_absent": absent_rows,
        "known_absent_all_empty": all(r["empty_ranked_set"] for r in absent_rows)
        if absent_rows
        else False,
        "known_absent_nonempty": absent_nonempty,
        "build_when_superior_present": build_when_superior,
        "ranked_below_rebuild": ranked_below_rebuild,
        "discriminates_present_absent": (
            found_n == planted
            and planted > 0
            and bool(absent_rows)
            and all(r["empty_ranked_set"] for r in absent_rows)
        ),
        "pass": (
            found_n == planted
            and planted > 0
            and not misses
            and bool(absent_rows)
            and all(r["empty_ranked_set"] for r in absent_rows)
            and not build_when_superior
            and not ranked_below_rebuild
        ),
    }


if __name__ == "__main__":
    doc = measure()
    print(json.dumps({k: doc[k] for k in ("recall_fraction", "miss_list", "pass", "discriminates_present_absent")}, indent=2))
    raise SystemExit(0 if doc["pass"] else 1)
