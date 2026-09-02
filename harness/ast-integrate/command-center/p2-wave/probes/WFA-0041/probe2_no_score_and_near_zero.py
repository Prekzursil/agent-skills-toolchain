#!/usr/bin/env python3
"""Probe 2: no manufactured scores; near-zero frozen first; independent locator.

Mechanically different from probe 1: re-runs run_records.locate on every
claimed fixture and asserts the live artifact's expectation block was bound
before extraction (import of expectation.py, not a post-hoc rewrite).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from classify import HONEST_NULL, manufactured_score  # noqa: E402
from expectation import (  # noqa: E402
    CATALOG_EXPECTED_N,
    NEAR_ZERO_CEILING,
    NEAR_ZERO_EXPECTED,
    NEAR_ZERO_RATIONALE,
)
from extract import live_extract, load_fixture_corpus  # noqa: E402
from run_records import locate  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0041-extract-benchmark-evidence.json"


def _by_id(rows: list[dict], cid: str) -> dict:
    for row in rows:
        if row.get("id") == cid:
            return row
    raise SystemExit(f"FAILED:WFA-0041-probe2 missing {cid}")


def main() -> int:
    print(f"pre_stated_near_zero_expected={NEAR_ZERO_EXPECTED}")
    print(f"pre_stated_near_zero_ceiling={NEAR_ZERO_CEILING}")
    print(f"pre_stated_catalog_expected_n={CATALOG_EXPECTED_N}")
    print(f"threshold_rationale={NEAR_ZERO_RATIONALE[:80]}")
    if not NEAR_ZERO_EXPECTED:
        print("FAILED:WFA-0041-probe2 near-zero was not pre-stated")
        return 1

    corp = load_fixture_corpus()
    honest = _by_id(corp["rows"], "cand.fixture.honest-null")
    tempt = _by_id(corp["rows"], "cand.fixture.score-tempt")
    claimed = _by_id(corp["rows"], "cand.fixture.claimed-no-record")
    citable = _by_id(corp["rows"], "cand.fixture.citable")

    reloc_claimed = locate(
        {"benchmark": "fixtures/run-records/MISSING-never-ran.json"},
        [HERE, HERE / "fixtures"],
    )
    reloc_citable = locate(
        {"benchmark": "fixtures/run-records/citable-run.json"},
        [HERE, HERE / "fixtures"],
    )

    live = live_extract(REPO)
    live_scores = [r["id"] for r in live["rows"] if manufactured_score(r)]
    live_citable = live["counts"]["CITABLE"]

    if not ART.is_file():
        print("FAILED:WFA-0041-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    exp = doc.get("expectation_preregistered") or {}
    rows = doc.get("rows") or []
    art_scores = [r.get("id") for r in rows if manufactured_score(r)]

    report = {
        "honest_status": honest.get("status"),
        "tempt_status": tempt.get("status"),
        "honest_benchmark": honest.get("benchmark"),
        "tempt_benchmark": tempt.get("benchmark"),
        "reloc_claimed_found": reloc_claimed["found"],
        "reloc_citable_found": reloc_citable["found"],
        "live_citable": live_citable,
        "live_scores": live_scores,
        "art_scores": art_scores,
        "expectation_in_artifact": exp.get("near_zero_expected"),
        "near_zero_live": live_citable <= NEAR_ZERO_CEILING,
    }
    print(json.dumps(report, sort_keys=True, default=str))

    if honest.get("status") != HONEST_NULL or honest.get("benchmark") is not None:
        print("FAILED:WFA-0041-probe2 honest-null was not an empty column")
        return 1
    if tempt.get("status") != HONEST_NULL:
        print("FAILED:WFA-0041-probe2 score-tempt was not HONEST-NULL")
        return 1
    if manufactured_score(honest) or manufactured_score(tempt):
        print("FAILED:WFA-0041-probe2 fixture manufactured a score")
        return 1
    if reloc_claimed["found"] is not False:
        print("FAILED:WFA-0041-probe2 independent locator found the missing record")
        return 1
    if reloc_citable["found"] is not True:
        print("FAILED:WFA-0041-probe2 independent locator missed the planted record")
        return 1
    if live_scores or art_scores:
        print("FAILED:WFA-0041-probe2 manufactured scores", live_scores, art_scores)
        return 1
    if exp.get("near_zero_expected") is not True:
        print("FAILED:WFA-0041-probe2 artifact missing pre-registered expectation")
        return 1
    if exp.get("near_zero_ceiling") != NEAR_ZERO_CEILING:
        print("FAILED:WFA-0041-probe2 ceiling rewritten after the fact")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0041-probe2 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:WFA-0041" not in ART.read_text(encoding="utf-8"):
        print("FAILED:WFA-0041-probe2 sentinel absent")
        return 1
    for row in rows:
        if row.get("status") == HONEST_NULL and row.get("benchmark") not in (None, {}):
            print("FAILED:WFA-0041-probe2 honest-null column not empty", row)
            return 1
    if live_citable > NEAR_ZERO_CEILING and exp.get("near_zero_expected") is True:
        # Ceiling miss is allowed to stay SUCCESS only if we do not relabel it
        # as a lane failure; still fail if the artifact calls it a failure.
        if doc.get("state") != "SUCCESS":
            print("FAILED:WFA-0041-probe2 near-zero miss reinterpreted as failure")
            return 1
    print(
        "SUCCESS:WFA-0041-probe2 no-score empty-column near-zero-preregistered "
        f"live_citable={live_citable}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
