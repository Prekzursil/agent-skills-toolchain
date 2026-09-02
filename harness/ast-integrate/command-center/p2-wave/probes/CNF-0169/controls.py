#!/usr/bin/env python3
"""Catalog-required detector controls for CNF-0169.

Known-present, known-broken (delete one manifest id), duplicate-id across two
registry slices, and empty-input total divergence.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import differ as D  # noqa: E402

HEALTHY_IDS = ["CNF-0001", "TST-0001", "IMP-0001"]
PLANTED_PRESENT = "CNF-0001"
DELETED_MANIFEST = "IMP-0001"
COLLIDE = "CNF-0099"
EMPTY_PEER = "catalog"


def healthy_sets() -> dict[str, set[str]]:
    return {name: set(HEALTHY_IDS) for name in D.SOURCES}


def known_present() -> dict[str, Any]:
    pairs = D.ten_pairwise(healthy_sets(), keep_ids=True)
    in_diff = D.disagreeing_ids(pairs)
    silent = PLANTED_PRESENT not in in_diff and all(
        row["symmetric_count"] == 0 for row in pairs
    )
    return {
        "id": "known-present",
        "planted_id": PLANTED_PRESENT,
        "in_all_five": True,
        "appears_in_any_difference": PLANTED_PRESENT in in_diff,
        "all_pairs_empty": all(row["symmetric_count"] == 0 for row in pairs),
        "silent_on_good_state": silent,
        "pass": silent,
    }


def known_broken_delete_manifest() -> dict[str, Any]:
    before_sets = healthy_sets()
    after_sets = copy.deepcopy(before_sets)
    after_sets["artifacts"].discard(DELETED_MANIFEST)
    before = D.ten_pairwise(before_sets, keep_ids=True)
    after = D.ten_pairwise(after_sets, keep_ids=True)
    before_ids = D.disagreeing_ids(before)
    after_ids = D.disagreeing_ids(after)
    grew = after_ids - before_ids
    untouched = []
    grew_pairs = []
    for b, a in zip(before, after):
        if a["pair"] != b["pair"]:
            raise RuntimeError("pair order drifted")
        if a["symmetric_count"] == b["symmetric_count"]:
            untouched.append(a["pair"])
        elif a["symmetric_count"] == b["symmetric_count"] + 1:
            grew_pairs.append(a["pair"])
        else:
            grew_pairs.append(f"{a['pair']}:delta={a['symmetric_count']-b['symmetric_count']}")
    # Exactly one *id* appears in differences that did not before.
    one_id = grew == {DELETED_MANIFEST} and len(after_ids) == len(before_ids) + 1
    # Pairs that do not include artifacts stay empty; the four that do grow by 1.
    artifacts_pairs = {p for p in grew_pairs if "artifacts" in p}
    other_grew = [p for p in grew_pairs if "artifacts" not in p]
    fired = one_id and not other_grew and len(artifacts_pairs) == 4
    return {
        "id": "known-broken-delete-manifest",
        "deleted_id": DELETED_MANIFEST,
        "disagreeing_ids_before": sorted(before_ids),
        "disagreeing_ids_after": sorted(after_ids),
        "grew_ids": sorted(grew),
        "grew_pairs": grew_pairs,
        "untouched_pairs": untouched,
        "exactly_one_id_difference": one_id,
        "fired_on_bad_state": fired,
        "pass": fired,
    }


def duplicate_id_control() -> dict[str, Any]:
    slice_a = ["CNF-0001", COLLIDE, "TST-0001"]
    slice_b = [COLLIDE, "IMP-0001"]
    hits = D.colliding_across(slice_a, slice_b)
    # Intra-list duplicate in a single registry.
    intra = D.duplicates_in_list(["CNF-0001", COLLIDE, COLLIDE])
    fired = COLLIDE in hits and COLLIDE in intra
    return {
        "id": "duplicate-id",
        "failure_class": "duplicate-catalog",
        "colliding_id": COLLIDE,
        "across_two_slices": hits,
        "intra_registry": intra,
        "fired_on_bad_state": fired,
        "pass": fired,
    }


def empty_input_control() -> dict[str, Any]:
    populated = healthy_sets()
    empty = {name: set(HEALTHY_IDS) for name in D.SOURCES}
    empty["claims"] = set()
    populated_pairs = D.ten_pairwise(populated, keep_ids=True)
    empty_pairs = D.ten_pairwise(empty, keep_ids=True)
    row = D.pair_row(empty_pairs, "claims", EMPTY_PEER)
    # catalog is right of claims|catalog
    if row["left"] == "claims":
        catalog_minus_claims = row["right_minus_left"]["count"]
        claims_minus_catalog = row["left_minus_right"]["count"]
    else:
        catalog_minus_claims = row["left_minus_right"]["count"]
        claims_minus_catalog = row["right_minus_left"]["count"]
    false_agreement = all(p["symmetric_count"] == 0 for p in empty_pairs)
    total_div = (
        catalog_minus_claims == len(HEALTHY_IDS)
        and claims_minus_catalog == 0
        and not false_agreement
    )
    return {
        "id": "empty-input",
        "empty_source": "claims",
        "peer": EMPTY_PEER,
        "peer_minus_empty": catalog_minus_claims,
        "empty_minus_peer": claims_minus_catalog,
        "false_agreement": false_agreement,
        "healthy_all_empty_diffs": all(p["symmetric_count"] == 0 for p in populated_pairs),
        "reports_total_divergence": total_div,
        "fired_on_bad_state": total_div,
        "silent_on_good_state": all(p["symmetric_count"] == 0 for p in populated_pairs),
        "pass": total_div,
    }


def missing_artifact_control() -> dict[str, Any]:
    """Manifest row whose path is not on disk is a defect."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="cnf0169-man-") as tmp:
        repo = Path(tmp)
        (repo / "keep.json").write_text("{}", encoding="utf-8")
        man_good = {
            "artifacts": [
                {"path": "keep.json", "present": True, "unit_id": "CNF-0001"},
            ]
        }
        man_bad = {
            "artifacts": [
                {"path": "keep.json", "present": True, "unit_id": "CNF-0001"},
                {"path": "gone.json", "present": True, "unit_id": "CNF-0002"},
            ]
        }
        good = D.manifest_missing_artifacts(man_good, repo)
        bad = D.manifest_missing_artifacts(man_bad, repo)
        fired = len(good) == 0 and len(bad) == 1 and bad[0]["path"] == "gone.json"
        silent = len(good) == 0
    return {
        "id": "manifest-entry-without-artifact",
        "silent_on_good_state": silent,
        "fired_on_bad_state": fired,
        "pass": fired,
    }


def dangling_cite_control() -> dict[str, Any]:
    claims = [
        {"id": "CNF-0001", "test_id": "TST-0001"},
        {"id": "CNF-0002", "test_id": "TST-9999"},
    ]
    tests = [{"id": "TST-0001"}]
    cids, _, cites = D.extract_claim_ids({"claims": claims})
    tids, _ = D.extract_test_ids({"tests": tests})
    dangling = D.dangling_test_cites(cites, set(tids))
    good = D.dangling_test_cites(
        [{"claim_id": "CNF-0001", "test_id": "TST-0001"}],
        {"TST-0001"},
    )
    fired = (
        [d["test_id"] for d in dangling] == ["TST-9999"]
        and good == []
        and "CNF-0001" in cids
    )
    return {
        "id": "claim-cites-absent-test",
        "dangling": dangling,
        "silent_on_good_state": good == [],
        "fired_on_bad_state": fired,
        "pass": fired,
    }


def run_all() -> dict[str, Any]:
    rows = [
        known_present(),
        known_broken_delete_manifest(),
        duplicate_id_control(),
        empty_input_control(),
        missing_artifact_control(),
        dangling_cite_control(),
    ]
    return {
        "pass": all(r.get("pass") for r in rows),
        "controls": rows,
    }


def assert_controls() -> dict[str, Any]:
    report = run_all()
    if not report["pass"]:
        failed = [r["id"] for r in report["controls"] if not r.get("pass")]
        raise AssertionError(f"CNF-0169 controls failed: {failed}")
    return report
