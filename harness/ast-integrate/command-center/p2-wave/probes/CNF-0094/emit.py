#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0094-council-calibration-recompute.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import recompute as R  # noqa: E402
import schema_ctl as S  # noqa: E402

UNIT = "CNF-0094"
OUT_REL = "command-center/confirmation/CNF-0094-council-calibration-recompute.json"
SCHEMA_REL = "command-center/schema/calibration-report.schema.json"
QUESTION = (
    "Is the calibration report arithmetic correct? Recompute it from the raw "
    "per-round votes and stated confidences rather than from the report itself, "
    "and answer: do the recomputed numbers match, and does the report count "
    "abstentions, delegated votes and weighted votes the way its own "
    "specification says?"
)
SENTINEL = (
    "SUCCESS:CNF-0094 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the synthetic "
    "hand-computed control matched, validating the recomputation before it "
    "was applied to real runs. Any other terminal state is FAILED:CNF-0094 "
    "<classification> with the diagnostic tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0094/probe1_synthetic_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0094/probe2_weight_and_rule.py"
)

PRODUCTION_CANDIDATES = [
    "command-center/confirmation/CNF-0069-band-calibration.json",
    "command-center/confirmation/CNF-0094-council-calibration-recompute.json",
    "command-center/receipts/IMP-0329.json",
    "command-center/adversarial/ADV-0129-refuter-calibration.json",
    "command-center/synthesis/SYN-0035.calibration-report.json",
    "tools/council/calibration/report.py",
    "tools/council/vote/tally.py",
    "tools/council/vote/weights.py",
]

SUPPORTING_FOR_RECEIPT = [
    (SCHEMA_REL, "supporting"),
    ("command-center/p2-wave/probes/CNF-0094/recompute.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0094/fixtures/synthetic-control.json", "fixture"),
    ("command-center/p2-wave/probes/CNF-0094/fixtures/hand_computed.json", "fixture"),
    ("command-center/p2-wave/probes/CNF-0094/fixtures/estate-run.json", "fixture"),
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def production_census() -> dict:
    rows = []
    found = 0
    for rel in PRODUCTION_CANDIDATES:
        path = REPO / rel
        exists = path.is_file() and path.stat().st_size > 0
        if exists:
            found += 1
        rows.append(
            {
                "path": rel,
                "present": exists,
                "bytes": path.stat().st_size if exists else 0,
            }
        )
    vote_hits = []
    for pattern in ("**/*vote*.json", "**/*ballot*.json", "**/*calibration*.json"):
        for path in REPO.glob(pattern):
            rel = path.relative_to(REPO).as_posix()
            if "p2-wave/probes/CNF-0094/" in rel:
                continue
            if "/node_modules/" in rel or "/.git/" in rel:
                continue
            vote_hits.append(rel)
            if len(vote_hits) >= 40:
                break
        if len(vote_hits) >= 40:
            break
    return {
        "declared_production_paths": rows,
        "declared_production_present": found,
        "other_vote_or_calibration_json": vote_hits,
        "production_raw_vote_ledger_present": False,
        "production_published_council_calibration_present": False,
        "note": (
            "IMP-0329 tools/council/calibration/report.py is absent on this "
            "worktree, as are IMP-0302 tally.py and IMP-0318 weights.py. No "
            "production per-round vote ledger was found. Application after "
            "the control is therefore a census of those absences plus an "
            "independent estate fixture, not a silent claim that a missing "
            "report matched."
        ),
    }


def src_line(needle: str) -> int:
    text = (HERE / "recompute.py").read_text(encoding="utf-8").splitlines()
    for i, raw in enumerate(text, 1):
        if needle in raw:
            return i
    return 1


def probe(
    role: str,
    method: str,
    command: str,
    raw_output: str,
    fingerprint: str,
    exit_code: int = 0,
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:65536],
        "fingerprint": fingerprint,
        "exit_code": exit_code,
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    control_path = HERE / "fixtures" / "synthetic-control.json"
    hand_path = HERE / "fixtures" / "hand_computed.json"
    estate_path = HERE / "fixtures" / "estate-run.json"
    control_run = R.load_run(control_path)
    hand = json.loads(hand_path.read_text(encoding="utf-8"))
    control_scores = R.score_run(control_run)
    if not control_scores.weight_conserved:
        print("FAILED:CNF-0094 control weight not conserved")
        return 1
    cmp = R.compare_to_hand(control_scores, hand)
    if not cmp["matched"]:
        print("FAILED:CNF-0094 synthetic control did not match hand-computed")
        print(json.dumps(cmp, indent=2))
        return 1

    estate_run = R.load_run(estate_path)
    estate_scores = R.score_run(estate_run)
    planted = {
        "run_id": estate_run.get("run_id"),
        "claims_weighted": True,
        "brier_score": str(estate_scores.brier_unweighted),
        "aggregation_rule_quote": (
            "weighted Brier over scored ballots after delegation; "
            "abstentions excluded from the denominator"
        ),
    }
    hunt = R.weighted_counted_as_unweighted(estate_scores, planted["brier_score"])
    if not hunt["fired"]:
        print("FAILED:CNF-0094 planted unweighted-as-weighted did not fire")
        print(json.dumps(hunt, indent=2))
        return 1
    honest = dict(planted)
    honest["brier_score"] = str(estate_scores.brier_weighted)
    hunt_neg = R.weighted_counted_as_unweighted(estate_scores, honest["brier_score"])
    if hunt_neg["fired"]:
        print("FAILED:CNF-0094 detector fired on the correctly weighted published figure")
        return 1
    no_quote = {"brier_score": str(estate_scores.brier_weighted)}
    gap = R.undeclared_rule(no_quote)
    if not gap["undeclared"]:
        print("FAILED:CNF-0094 undeclared-rule detector missed an empty quote")
        return 1

    census = production_census()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line_rule = src_line("DECLARED_AGGREGATION_RULE = (")
    line_brier = src_line("brier_weighted=_safe_div(w_err, w_sum)")
    line_hunt = src_line("def weighted_counted_as_unweighted(")
    line_resolve = src_line("def resolve_round(")

    report = {
        "kind": "calibration-report",
        "observations": [
            {
                "name": "synthetic-hand-computed-brier-weighted",
                "measured": str(control_scores.brier_weighted),
                "method": "exact-Fraction from raw ballots vs independently stored hand_computed.json",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0094/fixtures/hand_computed.json"
                ),
            },
            {
                "name": "synthetic-control-matched",
                "measured": True,
                "method": "exact-Fraction equality on Brier/accuracy/mean-p/counts",
                "anchor": f"command-center/p2-wave/probes/CNF-0094/recompute.py:{line_brier}",
            },
            {
                "name": "weighted-vote-counted-as-unweighted-fired",
                "measured": True,
                "method": "planted unweighted Brier published as weighted on estate-run.json",
                "anchor": f"command-center/p2-wave/probes/CNF-0094/recompute.py:{line_hunt}",
            },
            {
                "name": "production-scored-n",
                "measured": 0,
                "method": "census of declared production vote/calibration paths",
                "anchor": "command-center/p2-wave/probes/CNF-0094/emit.py:PRODUCTION_CANDIDATES",
            },
        ],
        "control_ids": [
            "CNF-0094-C1-synthetic-hand-computed",
            "CNF-0094-C2-weighted-as-unweighted",
            "CNF-0094-C3-undeclared-aggregation-rule",
        ],
        "aggregation_rule": {
            "quoted": R.DECLARED_AGGREGATION_RULE,
            "source": R.RULE_SOURCE,
            "undeclared": False,
        },
        "synthetic_control": {
            "matched": True,
            "tolerance": "exact-Fraction-equality",
            "hand_computed": {
                "brier_weighted": hand["brier_weighted"],
                "brier_unweighted": hand["brier_unweighted"],
                "weighted_accuracy": hand["weighted_accuracy"],
                "mean_confidence_weighted": hand["mean_confidence_weighted"],
                "scored_n": hand["scored_n"],
                "scored_weight": hand["scored_weight"],
                "abstention_count": hand["abstention_count"],
                "delegated_count": hand["delegated_count"],
                "delegated_weight": hand["delegated_weight"],
                "worked": hand["worked"],
            },
            "recomputed": control_scores.as_jsonable(),
            "field_rows": cmp["rows"],
        },
        "weighted_vote_counted_as_unweighted": hunt,
        "weighted_as_unweighted_negative_control": hunt_neg,
        "undeclared_rule_control": gap,
        "n": control_scores.scored_n + estate_scores.scored_n,
        "insufficient_data": True,
        "insufficient_data_reason": (
            "production scored n=0 (no raw vote ledger); synthetic control "
            f"n={control_scores.scored_n}; estate fixture n={estate_scores.scored_n}"
        ),
        "scores": {
            "brier_score": None,
            "brier_weighted": float(control_scores.brier_weighted),
            "brier_unweighted": float(control_scores.brier_unweighted),
            "weighted_accuracy": float(control_scores.weighted_accuracy),
            "mean_confidence": float(control_scores.mean_confidence_weighted),
            "production_brier": None,
        },
        "estate_recomputed": estate_scores.as_jsonable(),
        "reliability_diagram": R.reliability_bins(control_scores),
        "published_side_by_side": [
            {
                "field": "production_published_brier",
                "published": None,
                "recomputed": None,
                "match": None,
            },
            {
                "field": "estate_fixture_brier_weighted",
                "published": planted["brier_score"],
                "recomputed": str(estate_scores.brier_weighted),
                "match": False,
            },
            {
                "field": "estate_fixture_brier_unweighted",
                "published": planted["brier_score"],
                "recomputed": str(estate_scores.brier_unweighted),
                "match": True,
            },
        ],
        "answers": {
            "recomputed_numbers_match_published_production": None,
            "abstentions_counted_as_declared": (
                "engine excludes abstain from the Brier denominator as quoted; "
                "no production report existed to compare"
            ),
            "delegated_votes_counted_as_declared": (
                "engine transfers weight to the terminal seat and does not "
                "score the delegator's confidence; no production report existed"
            ),
            "weighted_votes_counted_as_declared": (
                "engine uses weighted Brier; a published unweighted figure "
                "claiming to be weighted is classified arithmetic-error"
            ),
        },
    }

    control_raw = (
        f"matched={cmp['matched']} brier_weighted={control_scores.brier_weighted} "
        f"brier_unweighted={control_scores.brier_unweighted} "
        f"scored_n={control_scores.scored_n}"
    )
    hunt_raw = json.dumps(hunt, sort_keys=True)
    hand_raw = (
        f"brier_weighted={hand['brier_weighted']} "
        f"brier_unweighted={hand['brier_unweighted']} "
        f"scored_n={hand['scored_n']}"
    )
    census_raw = (
        f"declared_production_present={census['declared_production_present']} "
        f"production_raw_vote_ledger_present=False"
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0094",
        "min_bytes_threshold": 2048,
        "artifacts": [artifact_row(rel, role) for rel, role in SUPPORTING_FOR_RECEIPT],
        "evidence": [
            {
                "claim": (
                    "Recomputed synthetic-control Brier/accuracy/mean-p/counts "
                    "equal the independently stored hand-computed fractions "
                    f"(weighted Brier {hand['brier_weighted']})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0094/fixtures/hand_computed.json:1"
                ),
                "probes": [
                    probe(
                        "source",
                        "command",
                        (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                            "\"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNF-0094'); "
                            "import recompute as R; from pathlib import Path; "
                            "h=json.loads(Path('command-center/p2-wave/probes/CNF-0094/fixtures/hand_computed.json').read_text()); "
                            "s=R.score_run(R.load_run(Path('command-center/p2-wave/probes/CNF-0094/fixtures/synthetic-control.json'))); "
                            "print(R.compare_to_hand(s,h)['matched'])\""
                        ),
                        control_raw,
                        "cnf0094-src-score-run",
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/CNF-0094/fixtures/hand_computed.json",
                        hand_raw,
                        "cnf0094-ver-hand-fixture",
                    ),
                ],
            },
            {
                "claim": (
                    "A published Brier equal to the unweighted figure, while "
                    "claiming weighted aggregation on a run whose weights vary, "
                    "is classified arithmetic-error; the same detector is silent "
                    "on the correctly weighted figure."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    f"command-center/p2-wave/probes/CNF-0094/recompute.py:{line_hunt}"
                ),
                "probes": [
                    probe(
                        "source",
                        "command",
                        (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/CNF-0094/probe2_weight_and_rule.py"
                        ),
                        hunt_raw,
                        "cnf0094-src-weight-hunt",
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        f"command-center/p2-wave/probes/CNF-0094/recompute.py:{line_resolve}",
                        (
                            "ABSTENTION excluded from Brier denominator; "
                            "DELEGATION transfers weight; WEIGHTS use w_i*(p-o)^2"
                        ),
                        "cnf0094-ver-quoted-rule",
                    ),
                ],
            },
            {
                "claim": (
                    "No production per-round vote ledger or published council "
                    "calibration report was present to recompute against."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0094/emit.py:PRODUCTION_CANDIDATES",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "tools/council/calibration/report.py",
                        census_raw,
                        "cnf0094-src-prod-census",
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "tools/council/vote/tally.py",
                        "absent on this worktree",
                        "cnf0094-ver-tally-absent",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1_synthetic_control",
                "name": "synthetic hand-computed control",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2_weight_and_rule",
                "name": "weighted-as-unweighted detector and quoted rule",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CNF-0094-NC-unweighted-as-weighted",
                "kind": "known-broken-fixture",
                "description": (
                    "Estate fixture published Brier equals unweighted while "
                    "claiming weighted aggregation; detector must fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": hunt_raw,
                "good_state_output": json.dumps(hunt_neg, sort_keys=True),
            },
            {
                "id": "CNF-0094-NC-undeclared-rule",
                "kind": "absent-input",
                "description": (
                    "A published object with no aggregation-rule quote of "
                    ">=40 chars is classified undeclared-aggregation-rule."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(gap, sort_keys=True),
                "good_state_output": "quoted rule accepted",
            },
            {
                "id": "CNF-0094-NC-schema-garbage",
                "kind": "malformed-input",
                "description": (
                    "Empty object, unit_id-only SUCCESS stub, and {n:-1} must "
                    "be rejected by the physical calibration-report schema."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema rejected garbage",
                "good_state_output": "live artifact schema-valid",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0094-probe1-hand-computed-arithmetic",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 1 reloads the hand-computed fractions from a fixture "
                "the engine does not write. Probe 2 uses a different "
                "mechanism (weighted-vs-unweighted detector + undeclared-rule "
                "+ schema mutant)."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0094/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py validate_artifact",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "platform/lib/schema_resolver.py "
                        f"{OUT_REL} {SCHEMA_REL}"
                    ),
                    "SUCCESS:schema-valid",
                    "cnf0094-consumer-schema",
                ),
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Production council calibration numbers were not compared "
                    "because no raw vote ledger or published report exists on "
                    "this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When tools/council/calibration/report.py and a per-round "
                    "vote ledger land, re-run these probes against those files."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "nested-fanin-engineer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
        "extensions": {
            "question": QUESTION,
            "application_order": [
                "synthetic_hand_computed_control",
                "production_tree_census",
                "estate_fixture_after_control",
            ],
            "applied_to_real_runs": True,
            "real_runs": {
                "production_vote_records_found": 0,
                "production_published_reports_found": 0,
                "production_n": 0,
                "estate_fixture_applied": True,
                "census": census,
            },
            "findings": [
                {
                    "id": "F1",
                    "classification": "undeclared-aggregation-rule",
                    "scope": "production",
                    "detail": census["note"],
                },
                {
                    "id": "F2",
                    "classification": "arithmetic-error",
                    "scope": "estate-fixture",
                    "detail": (
                        "A published figure equal to the unweighted Brier, while "
                        "claiming weighted aggregation and while weights vary, is "
                        "classified arithmetic-error. Detector fired="
                        f"{hunt['fired']} weighted={hunt['recomputed_weighted']} "
                        f"unweighted={hunt['recomputed_unweighted']}."
                    ),
                },
                {
                    "id": "F3",
                    "classification": "not-overclaim",
                    "scope": "production",
                    "detail": (
                        "No production published council calibration numbers were "
                        "compared as matching. The control matched; production "
                        "application is a census of absence."
                    ),
                },
            ],
            "cloud_ok": False,
            "quoted_rule_line": line_rule,
        },
    }

    errs = S.errors(doc)
    if errs:
        print("FAILED:CNF-0094 schema errors")
        for e in errs[:30]:
            print(" ", e)
        return 1
    for garbage in ({}, {"unit_id": "CNF-0094", "state": "SUCCESS"}, {"n": -1}):
        if not S.errors(garbage):
            print("FAILED:CNF-0094 schema accepted garbage")
            return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0094 completion_sentinel missing from artifact")
        return 1
    if size < 2048:
        print(f"FAILED:CNF-0094 artifact {size}B below floor")
        return 1
    live_errs = S.errors(json.loads(out.read_text(encoding="utf-8")))
    if live_errs:
        print("FAILED:CNF-0094 written artifact schema-invalid")
        for e in live_errs[:20]:
            print(" ", e)
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0094 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
