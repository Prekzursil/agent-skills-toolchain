#!/usr/bin/env python3
"""Named probe 2: recall by name and by skill; empty vs index_error; no popularity.

Reviewer requirement: the index covers plugins[].skills[], not only descriptions.
Negative control: a query with no matches is kind=empty, distinct from index_error.
Gaming control: inflating downloads/stars does not move ranking.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools/marketplace/tests"))

import test_search_recall as rec  # noqa: E402
from marketplace.search import SearchIndex  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0102.json"


def _check_receipt() -> None:
    if not ART.is_file() or ART.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0102-probe2 receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0102":
        raise SystemExit(f"FAILED:IMP-0102-probe2 unit_id {doc.get('unit_id')}")
    if "SUCCESS:IMP-0102" not in text:
        raise SystemExit("FAILED:IMP-0102-probe2 sentinel absent")


def main() -> int:
    _check_receipt()
    rec.test_known_package_is_findable_by_name_and_by_skill()
    rec.test_empty_result_distinct_from_index_error()
    rec.test_popularity_fields_do_not_move_ranking()
    index = rec._index()
    by_name = index.search("canonical-hello")
    by_skill = index.search("hello-operator")
    skill_only = index.search("binary-diff-oracle")
    council = index.search("council")
    empty = index.search("zzzxnotaterminthecorpuszzzz")
    missing = rec.search_path(rec.MISSING, "hello")
    payload = {
        "probe": "probe2-recall-empty-skills",
        "unit_id": "IMP-0102",
        "pass": True,
        "findable_by_name": by_name.hits[0].stable_key,
        "findable_by_skill": list(by_skill.keys()),
        "skill_only_hit": skill_only.hits[0].stable_key,
        "council_via_skills_md": "council-pack" in council.keys(),
        "empty_kind": empty.kind,
        "index_error_kind": missing.kind,
        "empty_distinct_from_error": empty.kind != missing.kind,
        "popularity_term": 0.0,
        "skills_indexed": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "name={0} skill_only={1} empty={2} error={3}".format(
            payload["findable_by_name"],
            payload["skill_only_hit"],
            payload["empty_kind"],
            payload["index_error_kind"],
        )
    )
    print("SUCCESS:IMP-0102-probe2 recall, skills[] coverage, empty vs error")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
