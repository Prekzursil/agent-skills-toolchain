"""Canonical IMP-0201 fixtures: one certified workflow, two corpora, lying summary."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.evals.baseline import (  # noqa: E402
    dump_json,
    freeze_baseline,
    make_run,
)

WORKFLOW_ID = "wf.catalog-class.discovery-only"
BASELINE_NAME = "certified-v1"
CORPUS_V1 = "corpus.v1.matched-holdout"
CORPUS_V2 = "corpus.v2.retargeted"
SPEC_V1 = "agentspec/1.0.0"
SPEC_V2 = "agentspec/1.1.0"

# Integer scores. Same-corpus later run is a real regression on three of four cases.
ROWS_CERTIFIED = [
    {"case_id": "c01-easy", "score": 80},
    {"case_id": "c02-medium", "score": 70},
    {"case_id": "c03-hard", "score": 90},
    {"case_id": "c04-holdout", "score": 60},
]
ROWS_LATER = [
    {"case_id": "c01-easy", "score": 72},
    {"case_id": "c02-medium", "score": 70},
    {"case_id": "c03-hard", "score": 78},
    {"case_id": "c04-holdout", "score": 60},
]
# Independent expected deltas: -8, 0, -12, 0. Sum -20 over 4 => mean -5.
EXPECTED_DELTAS = {
    "c01-easy": -8,
    "c02-medium": 0,
    "c03-hard": -12,
    "c04-holdout": 0,
}
EXPECTED_MEAN_NUMERATOR = -20
EXPECTED_MEAN_DENOMINATOR = 4

# A stored summary that would produce a different mean if anyone trusted it.
LYING_BASELINE_SUMMARY = {
    "n": 4,
    "mean_score": 999,
    "authoritative": False,
    "note": "deliberate lie; compare() must ignore this field",
}
LYING_RUN_SUMMARY = {
    "n": 4,
    "mean_score": 1,
    "authoritative": False,
    "note": "deliberate lie; compare() must ignore this field",
}


def certified_baseline():
    return freeze_baseline(
        workflow_id=WORKFLOW_ID,
        baseline_name=BASELINE_NAME,
        corpus_version=CORPUS_V1,
        spec_version=SPEC_V1,
        per_case_rows=ROWS_CERTIFIED,
        summary=LYING_BASELINE_SUMMARY,
    )


def later_same_corpus():
    return make_run(
        workflow_id=WORKFLOW_ID,
        corpus_version=CORPUS_V1,
        spec_version=SPEC_V1,
        per_case_rows=ROWS_LATER,
        summary=LYING_RUN_SUMMARY,
        run_id="later-same-corpus",
    )


def later_cross_corpus():
    return make_run(
        workflow_id=WORKFLOW_ID,
        corpus_version=CORPUS_V2,
        spec_version=SPEC_V1,
        per_case_rows=ROWS_LATER,
        run_id="later-cross-corpus",
    )


def later_spec_mismatch():
    return make_run(
        workflow_id=WORKFLOW_ID,
        corpus_version=CORPUS_V1,
        spec_version=SPEC_V2,
        per_case_rows=ROWS_LATER,
        run_id="later-spec-mismatch",
    )


def summary_only_baseline():
    return freeze_baseline(
        workflow_id=WORKFLOW_ID,
        baseline_name="summary-only-negative",
        corpus_version=CORPUS_V1,
        spec_version=SPEC_V1,
        per_case_rows=ROWS_CERTIFIED,
        summary={"n": 4, "mean_score": 75, "authoritative": True},
        include_rows=False,
    )


def write_fixtures(dest: Path | None = None) -> dict[str, Path]:
    dest = dest or (HERE / "fixtures")
    dest.mkdir(parents=True, exist_ok=True)
    mapping = {
        "baseline-certified.json": certified_baseline(),
        "run-same-corpus.json": later_same_corpus(),
        "run-cross-corpus.json": later_cross_corpus(),
        "run-spec-mismatch.json": later_spec_mismatch(),
        "baseline-summary-only.json": summary_only_baseline(),
    }
    paths = {}
    for name, doc in mapping.items():
        path = dest / name
        dump_json(path, doc)
        paths[name] = path
    return paths


if __name__ == "__main__":
    written = write_fixtures()
    for name, path in written.items():
        print(f"wrote {path.relative_to(REPO)} bytes={path.stat().st_size}")
    print("SUCCESS:IMP-0201 fixtures")
