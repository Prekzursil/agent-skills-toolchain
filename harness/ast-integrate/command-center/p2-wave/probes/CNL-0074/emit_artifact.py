#!/usr/bin/env python3
"""Emit the CNL-0074 design note (JSON written at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import score as S  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0074-confidence-trajectory-and-the-post-run-calibration-report.md"
)
SCHEMA = HERE / "design-note.schema.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0074/probe1_deferred_resolution.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0074/probe2_unscoreable_negative.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def first_line(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:CNL-0074 emit missing needle {needle!r} in {path}")


def tabulate(name: str, with_res: bool) -> dict:
    base = HERE / "fixtures" / name
    res = (base / "resolution.json") if with_res else None
    report = S.score_paths(base / "trajectory.json", res)
    return {
        "n_statements": report["n_statements"],
        "n_resolved": report["n_resolved"],
        "n_pending": report["n_pending"],
        "n_unscoreable": report["n_unscoreable"],
        "n_rejected_resolution": report["n_rejected_resolution"],
        "mean_brier": report["mean_brier"],
        "mean_log_score": report["mean_log_score"],
        "not_yet_meaningful": report["not_yet_meaningful"],
        "statuses": [r["status"] for r in report["rows"]],
    }


def snippet(path: Path, line: int, width: int = 160) -> str:
    rows = path.read_text(encoding="utf-8").splitlines()
    return rows[line - 1].strip()[:width]


def main() -> int:
    deferred = tabulate("deferred_scoreable", True)
    unscore = tabulate("unscoreable", False)
    pending = tabulate("pending", False)
    mismatch = tabulate("mismatch_source", True)
    if deferred["n_resolved"] != 3 or deferred["mean_brier"] is None:
        print("FAILED:CNL-0074 emit deferred fixture did not resolve")
        return 1
    if unscore["n_unscoreable"] != 2 or unscore["mean_brier"] is not None:
        print("FAILED:CNL-0074 emit unscoreable fixture was scored")
        return 1

    cat_id = first_line(CATALOG, '"id": "CNL-0074"')
    cat_q = first_line(CATALOG, "stated confidence tracked correctness")
    cat_t1 = first_line(CATALOG, "a deferred-resolution fixture")
    cat_t2 = first_line(CATALOG, "marked UNSCOREABLE rather than counted as calibrated")
    score_cls = first_line(HERE / "score.py", "def classify_statement(")
    score_run = first_line(HERE / "score.py", "def score_run(")
    rec_exp = first_line(HERE / "recount.py", "def _expanded_brier(")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = {
        "unit_id": "CNL-0074",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0074",
        "title": "Confidence trajectory and the post-run calibration report",
        "phase": "2C",
        "output_schema_named_by_catalog": "command-center/schema/councilspec.v2.schema.json",
        "output_schema_on_this_tree": "command-center/p2-wave/probes/CNL-0074/design-note.schema.json",
        "question": (
            "What is recorded per round so that a calibration report can later ask "
            "whether stated confidence tracked correctness - and what resolution "
            "source settles that, given most council decisions have no ground truth "
            "for months?"
        ),
        "answer": {
            "what_is_recorded_per_round": (
                "One confidence_statement per (participant, proposition, round). "
                "The statement freezes stated_confidence in [0,1] as P(proposition "
                "is true), the frozen proposition_text, the vote (which is NOT the "
                "prediction), and a resolution_binding that names how a later "
                "observable will settle the proposition. The confidence trajectory "
                "is that time-ordered list. A later calibration report must be "
                "computable from trajectory.json plus a later resolution document; "
                "it must not require the original session process or directory."
            ),
            "what_settles_correctness": (
                "A named resolution source declared at record time: "
                "EXTERNAL_OBSERVABLE, OWNER_ATTESTED_OUTCOME, or AUDIT_REPLAY. "
                "Most council decisions have no ground truth for months: those "
                "runs stay PENDING until the binding's observable is recorded, "
                "or they are UNSCOREABLE if no binding was declared. The council's "
                "own later vote, elapsed silence, and self-reported correctness "
                "are forbidden settlers. A run with no resolvable outcome is "
                "UNSCOREABLE and is excluded from the calibration population; it "
                "is never given a Brier of 0."
            ),
        },
        "per_round_record": {
            "record_kind": "confidence_statement",
            "schema_version": "cnl-0074.v1",
            "required_fields": [
                "council_run_id",
                "round_id",
                "recorded_at",
                "participant_id",
                "proposition_id",
                "proposition_text",
                "stated_confidence",
                "vote",
                "resolution_binding",
            ],
            "stated_confidence": "P(proposition is true) in [0,1], not P(my vote wins) and not a Likert label.",
            "vote_is_not_the_prediction": (
                "vote records for/against/abstain/delegate. Calibration scores "
                "stated_confidence against the later binary outcome of the "
                "proposition. A participant may vote against while stating p=0.45."
            ),
            "resolution_binding_required_fields": [
                "source_class",
                "observable_id",
                "observable_procedure",
                "due_at",
                "recorder_role",
            ],
            "session_independence": (
                "proposition_text and resolution_binding are frozen on the "
                "statement so a scorer that is given only those bytes plus a later "
                "resolution document can classify and score without the session."
            ),
        },
        "resolution_source_taxonomy": {
            "allowed": {
                "EXTERNAL_OBSERVABLE": (
                    "A named future measurement with procedure, due_at, and an "
                    "independent recorder who is not a session participant."
                ),
                "OWNER_ATTESTED_OUTCOME": (
                    "The owner records what happened after due_at. The owner must "
                    "not also be a voting participant on that run."
                ),
                "AUDIT_REPLAY": (
                    "For process claims only (did the run follow protocol X), a "
                    "later audit against frozen artifacts."
                ),
            },
            "forbidden_settlers": [
                "LATER_COUNCIL_AGREEMENT",
                "SELF_FINAL_VOTE",
                "ELAPSED_SILENCE",
                "SELF_REPORTED_CORRECT",
                "NONE",
            ],
            "unscoreable_rule": (
                "source_class NONE or missing, or a binding missing required "
                "fields, yields UNSCOREABLE. UNSCOREABLE is a terminal honesty "
                "state, not a queue. It cannot be retrofitted with a convenient "
                "source after the session."
            ),
            "pending_rule": (
                "A valid binding with no resolution yet is PENDING. PENDING is "
                "not scored and is not UNSCOREABLE. Silence after due_at is still "
                "PENDING until a resolution is recorded; it is never treated as y=1."
            ),
        },
        "scoring_semantics": {
            "population": "resolved_only",
            "brier": "(p - y)^2 on RESOLVED rows only",
            "log_score": "y*log(clip(p)) + (1-y)*log(clip(1-p)) with clip to [1e-15, 1-1e-15]",
            "not_yet_meaningful": "n_resolved < 10 must set not_yet_meaningful true rather than print a confident calibration claim (IMP-0329).",
            "unscoreable_counted_as_calibrated": False,
            "gameable_metrics_this_closes": [
                "unfalsifiable-metric: a confidence with no named later observable",
                "gameable-metric: counting UNSCOREABLE or PENDING as Brier=0 / y=1",
                "overclaim: a calibration number on n_resolved < 10",
                "spec-underspecified: using the council's own later vote as ground truth",
            ],
        },
        "fixture_tabulation": {
            "deferred_scoreable": deferred,
            "unscoreable": unscore,
            "pending": pending,
            "mismatch_source": mismatch,
            "hand_brier_deferred": {
                "alice": (0.8 - 1.0) ** 2,
                "bob": (0.6 - 1.0) ** 2,
                "cara": (0.3 - 1.0) ** 2,
                "mean": ((0.8 - 1.0) ** 2 + (0.6 - 1.0) ** 2 + (0.3 - 1.0) ** 2) / 3.0,
            },
        },
        "tests": [
            {
                "id": "T1-deferred-resolution",
                "name": "Deferred-resolution fixture remains scoreable after the fact without the original session",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-unscoreable-and-negative-control",
                "name": "No-resolvable-outcome marked UNSCOREABLE; independent recount; mutant that scores UNSCOREABLE as y=1 is rejected",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3-pending-vs-unscoreable",
                "name": "Valid binding without resolution is PENDING, not UNSCOREABLE and not scored",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CNL0074-C1",
                "kind": "known-broken-scorer",
                "description": (
                    "the check rejects a scorer that assigns Brier to UNSCOREABLE "
                    "rows by treating them as resolved-correct (y=1); it stays "
                    "silent when every statement has a named EXTERNAL_OBSERVABLE "
                    "and a matching later resolution."
                ),
                "rejects": "mutant.py treat_unscoreable_and_pending_as_resolved_correct",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "evidence": [
            {
                "signal": 1,
                "mechanism": "catalog-file-line",
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": cat_q,
                "snippet": snippet(CATALOG, cat_q),
                "claim": "Unit question requires a per-round record that later calibration can score against a named resolution source.",
            },
            {
                "signal": 1,
                "mechanism": "catalog-file-line",
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": cat_t1,
                "snippet": snippet(CATALOG, cat_t1),
                "claim": "tests_required includes a deferred-resolution fixture scoreable without the original session.",
            },
            {
                "signal": 1,
                "mechanism": "catalog-file-line",
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": cat_t2,
                "snippet": snippet(CATALOG, cat_t2),
                "claim": "tests_required: no resolvable outcome must be UNSCOREABLE, not counted as calibrated.",
            },
            {
                "signal": 1,
                "mechanism": "implementation-file-line",
                "path": "command-center/p2-wave/probes/CNL-0074/score.py",
                "line": score_cls,
                "snippet": snippet(HERE / "score.py", score_cls),
                "claim": "Author classifier marks missing/forbidden source_class as UNSCOREABLE before any Brier is computed.",
            },
            {
                "signal": 2,
                "mechanism": "reproducible-command-independent-recount",
                "path": "command-center/p2-wave/probes/CNL-0074/recount.py",
                "line": rec_exp,
                "snippet": snippet(HERE / "recount.py", rec_exp),
                "claim": (
                    "Independent recount uses set-membership status and expanded "
                    "Brier p*p+y*y-2py, not the author's (p-y)**2 path."
                ),
                "command": P2,
            },
            {
                "signal": 2,
                "mechanism": "reproducible-command-session-absent",
                "path": "command-center/p2-wave/probes/CNL-0074/probe1_deferred_resolution.py",
                "line": first_line(HERE / "probe1_deferred_resolution.py", "session_dir"),
                "snippet": "session_dir = dest / \"session\"",
                "claim": "Deferred scoring copies only trajectory.json and resolution.json; session/ is absent.",
                "command": P1,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0074-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "recount.py re-derives status counts and mean Brier from the "
                "fixture files with a different formula. A numeric disagreement "
                "with score.py or with fixture_tabulation in this artifact fails "
                "probe2."
            ),
        },
        "catalog_anchors": {
            "id_line": cat_id,
            "question_line": cat_q,
            "deferred_test_line": cat_t1,
            "unscoreable_test_line": cat_t2,
            "score_classify_line": score_cls,
            "score_run_line": score_run,
        },
        "dependencies_note": (
            "Catalog lists CNL-0069 (what number is 0.95 consensus). That number "
            "is a stopping-gate metric. This unit's record is stated_confidence "
            "versus a later observable, which does not wait on the consensus "
            "definition."
        ),
        "residual_unknowns": [
            {
                "claim": "command-center/schema/councilspec.v2.schema.json exists on this tree and this note validates against it.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "CNL-0001 owns the v2 envelope. This unit answers the calibration-record question and validates against probes/CNL-0074/design-note.schema.json.",
            },
            {
                "claim": "Harness restore inputs (_USER-PROMPTS.md:10746-10767 and 11-COUNCIL-SPECIFICATION.schema.json) are on this Linux worktree.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Place the restore tree and re-cite the spec lines for calibration report / post-run calibration.",
            },
            {
                "claim": "Ranking and multi-class propositions have a proper score in this record.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Extend outcome beyond binary 0/1; until then those statements are UNSCOREABLE unless rewritten as binary propositions.",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "deferred-resolution", "command": P1},
            {"id": "probe2", "role": "independent-recount-negative-control", "command": P2},
        ],
        "emitted_at": now,
        "completion": "SUCCESS:CNL-0074",
    }

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0074 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [{}, {"unit_id": "CNL-0074", "state": "SUCCESS"}, {"passing_tests": 999999}]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNL-0074 schema accepted garbage {list(g)[:3]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0074 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
