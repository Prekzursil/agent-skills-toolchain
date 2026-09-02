#!/usr/bin/env python3
"""Emit the CNL-0062 design note (JSON document at the catalog .md path).

G-1 `_measure_one_delivered.py` json.loads the catalog output_path. The path
suffix is .md; the bytes are a JSON object. That catalog/G-1 tension is
recorded under residual_unknowns, not papered over.
"""
from __future__ import annotations

import inspect
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import tabulate as T  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0062-cardinal-ballots-approval-and-score-and-cross-participant-.md"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0062/probe1_scale_drift.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0062/probe2_both_states.py"
)
QUESTION = (
    "Approval is score voting restricted to {0,1} - what does the shared "
    "cardinal tabulation look like, and how are scores comparable across "
    "participants who anchor their scales differently?"
)
MIN_BYTES = 8000


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def cite(fn) -> str:
    path = Path(inspect.getsourcefile(fn) or "").resolve()
    try:
        rel = path.relative_to(REPO).as_posix()
    except ValueError:
        rel = path.as_posix()
    line = inspect.getsourcelines(fn)[1]
    return f"{rel}:{line}"


def main() -> int:
    drift = load_fix("scale_drift.json")
    good = load_fix("known_good.json")
    bad = load_fix("planted_bad.json")
    appr = load_fix("approval_identity.json")
    as_score = deepcopy(appr)
    as_score["ballots"] = appr["as_score_ballots"]

    cands = list(drift["candidates"])
    by_id = {b["seat_id"]: b for b in drift["ballots"]}
    src = {c: T.as_frac(by_id["canonical"]["scores"][c]) for c in cands}
    dst = {c: T.as_frac(by_id["drifted"]["scores"][c]) for c in cands}
    affine = T.positive_affine_map(src, dst, cands)
    if affine is None:
        print("FAILED:CNL-0062 emit affine pair broken")
        return 1
    a_map, b_map = affine

    raw_can = T.tabulate(drift, drift["electorates"]["with_canonical"], calibrate=False)
    raw_dft = T.tabulate(drift, drift["electorates"]["with_drifted"], calibrate=False)
    cal_can = T.tabulate(drift, drift["electorates"]["with_canonical"], calibrate=True)
    cal_dft = T.tabulate(drift, drift["electorates"]["with_drifted"], calibrate=True)
    t_appr = T.tabulate(appr, calibrate=True)
    t_score = T.tabulate(as_score, calibrate=True)
    t_good_raw = T.tabulate(good, calibrate=False)
    t_good_cal = T.tabulate(good, calibrate=True)
    t_bad_raw = T.tabulate(bad, calibrate=False)
    t_bad_cal = T.tabulate(bad, calibrate=True)

    if raw_can["winner_totals"] == raw_dft["winner_totals"]:
        print("FAILED:CNL-0062 emit scale-drift fixture is not load-bearing")
        return 1
    if cal_can["winner_totals"] != cal_dft["winner_totals"]:
        print("FAILED:CNL-0062 emit calibration does not stabilize winner")
        return 1
    if t_appr["winner_totals"] != t_score["winner_totals"]:
        print("FAILED:CNL-0062 emit approval/score identity broken")
        return 1
    known_good_fired = t_good_raw["winner_totals"] != t_good_cal["winner_totals"]
    planted_bad_fired = t_bad_raw["winner_totals"] != t_bad_cal["winner_totals"]
    if known_good_fired or not planted_bad_fired:
        print("FAILED:CNL-0062 emit both-states collapsed")
        return 1

    inputs_present = {
        "USER-PROMPTS.md:10746-10767": False,
        "USER-PROMPTS.md:10915-10946": False,
        "11-COUNCIL-SPECIFICATION.schema.json": False,
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
        "CNL-0023 artifact": (
            REPO
            / "command-center/design/council/"
            / "CNL-0023-vote-rights-and-the-provenance-of-every-non-equal-weight.md"
        ).is_file(),
        "council-design-note.schema.json": (
            REPO / "command-center/schema/council-design-note.schema.json"
        ).is_file(),
    }

    markdown = "\n".join(
        [
            "# Cardinal ballots (approval and score) and cross-participant scale calibration",
            "",
            QUESTION,
            "",
            "## Shared tabulation (declared before ballots are seen)",
            "",
            "Approval is not a second method. It is score voting with domain {0,1}.",
            "One engine tabulates both:",
            "",
            "1. Fill omitted candidates with the declared floor L (default 0).",
            "2. Reject approval scores outside {0,1}; reject score votes outside [L,H].",
            "3. Affine-calibrate each ballot onto [0,1]: s' = (s-min)/(max-min).",
            "   A flat ballot (max==min) contributes 0 to every candidate.",
            "4. T[c] = sum_i weight_i * s'_i[c] as exact rationals (Fraction).",
            "5. Winner = unique argmax(T). Ties: lexicographically smallest candidate_id.",
            "",
            "Seat weight defaults to 1. A weight other than 1 without a provenance",
            "record is rejected (CNL-0023). That provenance schema is NOT-CHECKED here",
            "because the CNL-0023 artifact is absent on this worktree.",
            "",
            "## Why calibration is load-bearing",
            "",
            "canonical scores (A,B,C) = (10, 5, 0).",
            "drifted scores = 2*canonical + 10 = (30, 20, 10) — the same preference,",
            "a different anchor. Substituting drifted for canonical in the same",
            "three-seat electorate flips the uncalibrated winner and does not flip",
            "the calibrated winner. Numbers are in worked_examples.scale_drift.",
            "",
            "## Both-states and negative control",
            "",
            "Check: uncalibrated winner != calibrated winner.",
            "SILENT on known-good mixed approval (calibration is identity).",
            "FIRES on planted-bad affine-stretched scores. The negative control is",
            "that FIRES on planted-bad — the state the check is meant to reject.",
            "",
            "SUCCESS:CNL-0062",
        ]
    )

    doc = {
        "unit_id": "CNL-0062",
        "kind": "council-design-note",
        "schema_version": 1,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0062",
        "completion_sentinel": "SUCCESS:CNL-0062",
        "title": "Cardinal ballots (approval and score) and cross-participant scale calibration",
        "question": QUESTION,
        "answer": (
            "Shared cardinal tabulation is a weighted sum of per-ballot affine-"
            "calibrated scores on [0,1], with argmax winner and a priori lex-min "
            "tie-break. Approval is that procedure with domain {0,1}; mixed "
            "approval ballots are already calibrated. Cross-participant anchors "
            "are comparable because a positive affine transform of a ballot "
            "(the definition of the same cardinal preference with a different "
            "scale) is mapped to the identical [0,1] vector, so substituting "
            "one for the other cannot change the winner after calibration. "
            "Uncalibrated substitution can and, on the scale-drift fixture, does."
        ),
        "markdown": markdown,
        "procedure": {
            "declared_before_ballots": True,
            "domain_approval": "{0,1}",
            "domain_score": "[L,H] with L<H declared in the council spec",
            "omitted_candidate": "declared floor L (default 0)",
            "calibration": "per-ballot min-max onto [0,1]; flat ballot -> 0 vector",
            "aggregation": "T[c] = sum weight_i * s'_i[c] as Fraction",
            "winner": "unique argmax(T)",
            "tie_break": "lexicographically smallest candidate_id",
            "weight_default": "1",
            "weight_nonequal": "rejected unless weight_provenance is present (CNL-0023)",
            "executable": "command-center/p2-wave/probes/CNL-0062/tabulate.py",
        },
        "anchors": {
            "calibrate_ballot": cite(T.calibrate_ballot),
            "tabulate": cite(T.tabulate),
            "totals_row_major": cite(T.totals_row_major),
            "pairwise_score_margins": cite(T.pairwise_score_margins),
            "positive_affine_map": cite(T.positive_affine_map),
        },
        "worked_examples": {
            "scale_drift": {
                "fixture": "command-center/p2-wave/probes/CNL-0062/fixtures/scale_drift.json",
                "affine_a": str(a_map),
                "affine_b": str(b_map),
                "raw_winner_with_canonical": raw_can["winner_totals"],
                "raw_winner_with_drifted": raw_dft["winner_totals"],
                "raw_totals_with_canonical": raw_can["totals"],
                "raw_totals_with_drifted": raw_dft["totals"],
                "calibrated_winner_with_canonical": cal_can["winner_totals"],
                "calibrated_winner_with_drifted": cal_dft["winner_totals"],
                "calibrated_totals": cal_can["totals"],
                "drift_flips_uncalibrated_winner": True,
                "calibration_stabilizes_winner": True,
                "approval_winner": t_appr["winner_totals"],
                "score_on_01_winner": t_score["winner_totals"],
                "approval_totals": t_appr["totals"],
            }
        },
        "both_states": {
            "check": "uncalibrated_winner != calibrated_winner",
            "known_good_fixture": "command-center/p2-wave/probes/CNL-0062/fixtures/known_good.json",
            "planted_bad_fixture": "command-center/p2-wave/probes/CNL-0062/fixtures/planted_bad.json",
            "known_good_fired": False,
            "known_good_silent": True,
            "known_good_raw_winner": t_good_raw["winner_totals"],
            "known_good_cal_winner": t_good_cal["winner_totals"],
            "planted_bad_fired": True,
            "planted_bad_raw_winner": t_bad_raw["winner_totals"],
            "planted_bad_cal_winner": t_bad_cal["winner_totals"],
            "negative_control_on_reject_state": "FIRES",
            "negative_control_verbatim": (
                "On planted_bad.json (affine-stretched drifted ballot tabulated "
                f"as commensurate) the check FIRES: raw_winner="
                f"{t_bad_raw['winner_totals']} cal_winner="
                f"{t_bad_cal['winner_totals']}."
            ),
        },
        "tests": [
            {
                "id": "scale-drift",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "both-states-and-negative-control",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "scale-drift-uncalibrated",
                "rejects": "planted_bad.json",
                "on_reject_state": "FIRES",
                "verbatim": (
                    f"raw_winner={t_bad_raw['winner_totals']} "
                    f"cal_winner={t_bad_cal['winner_totals']} "
                    "fired=True"
                ),
            },
            {
                "id": "weight-without-provenance",
                "rejects": "weight!=1 and weight_provenance absent",
                "on_reject_state": "ValueError weight_provenance",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Uncalibrated substitution of an affine-stretched copy of the "
                    "same preference flips the winner on the scale-drift fixture."
                ),
                "verdict": "CONFIRMED",
                "anchor": cite(T.tabulate),
                "signal": "argmax of uncalibrated Fraction totals",
                "verbatim": (
                    f"raw_with_canonical={raw_can['winner_totals']} "
                    f"raw_with_drifted={raw_dft['winner_totals']} "
                    f"totals_can={raw_can['totals']} totals_dft={raw_dft['totals']}"
                ),
            },
            {
                "claim": (
                    "After per-ballot min-max calibration the same substitution "
                    "does not change the winner (or the totals)."
                ),
                "verdict": "CONFIRMED",
                "anchor": cite(T.calibrate_ballot),
                "signal": "pairwise score-margin Condorcet on calibrated ballots",
                "verbatim": (
                    f"cal_with_canonical={cal_can['winner_totals']} "
                    f"cal_with_drifted={cal_dft['winner_totals']} "
                    f"totals={cal_can['totals']} pairwise={cal_can['winner_pairwise']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0062-probe2-column-major-recount",
            "independent": True,
            "verdict": "PASS",
            "method": (
                "probe2 re-tabulates known_good.json and planted_bad.json with "
                "a column-major Fraction loop that does not call "
                "totals_row_major, then requires the published winners to match."
            ),
        },
        "inputs_on_this_worktree": inputs_present,
        "report": {
            "kind": "council-design-note",
            "control_ids": [
                "scale-drift-uncalibrated",
                "weight-without-provenance",
            ],
            "observations": [
                {
                    "name": "scale_drift_raw_flip",
                    "measured": True,
                    "method": "argmax of uncalibrated Fraction totals",
                    "anchor": cite(T.tabulate),
                },
                {
                    "name": "scale_drift_calibrated_stable",
                    "measured": True,
                    "method": "pairwise score-margin Condorcet after min-max",
                    "anchor": cite(T.calibrate_ballot),
                },
                {
                    "name": "approval_is_score_on_01",
                    "measured": t_appr["winner_totals"] == t_score["winner_totals"],
                    "method": "shared tabulate() on identical {0,1} ballots",
                    "anchor": cite(T.tabulate),
                },
            ],
        },
        "residual_unknowns": [
            (
                "Catalog inputs USER-PROMPTS.md slices and 11/12 council JSON "
                "files are Windows restore paths absent on this Linux worktree. "
                "The procedure is derived from the catalog question plus "
                "re-runnable fixtures, not from those bytes. NOT-CHECKED against "
                "the restore tree."
            ),
            (
                "output_schema command-center/schema/council-design-note.schema.json "
                "exists as a generated shim ($ref to platform artifact-class-"
                "profiles). G-1 json.loads the catalog .md path, so this artifact "
                "is a JSON object at a .md suffix. Full Draft 2020-12 validation "
                "of the physical council-design-note profile (receipt_core "
                "additionalProperties false) is NOT-CHECKED here."
            ),
            (
                "CNL-0023 is a declared dependency and its artifact is absent. "
                "Non-equal weights are rejected without provenance; the provenance "
                "record shape is NOT specified here."
            ),
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNL-0062/tabulate.py",
                "exists": True,
                "role": "engine",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0062/fixtures/scale_drift.json",
                "exists": True,
                "role": "fixture",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "min_bytes_threshold": MIN_BYTES,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 for CNL-0062. cloud ok=true is not delivery. Did not run "
            "global unit_manifest.py --write. Did not git add/commit/push."
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:CNL-0062" not in text:
        print("FAILED:CNL-0062 emit sentinel missing from serialization")
        return 1
    if len("".join(text.replace("SUCCESS:CNL-0062", "").split())) < 200:
        print("FAILED:CNL-0062 emit body too thin for text-artifact gate")
        return 1
    out.write_text(text, encoding="utf-8")
    size = len(text.encode("utf-8"))
    if size < MIN_BYTES:
        print(f"FAILED:CNL-0062 emit {size}B below floor {MIN_BYTES}")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:CNL-0062 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
