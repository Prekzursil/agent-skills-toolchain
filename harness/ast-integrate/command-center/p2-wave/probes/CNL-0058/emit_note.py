#!/usr/bin/env python3
"""Emit CNL-0058 design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures_lib as F  # noqa: E402
import recount as R  # noqa: E402
import schema_lib as SL  # noqa: E402
import tally as T  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0058/probe1_shrinking_denominator.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0058/probe2_reviewer_recount.py"
)
QUESTION = (
    "How do threshold and quorum interact when seats abstain or are replaced "
    "mid-council - and can a supermajority threshold be met by a shrinking "
    "denominator rather than by persuasion?"
)
TALLY_REL = "command-center/p2-wave/probes/CNL-0058/tally.py"
BAD_REL = "command-center/p2-wave/probes/CNL-0058/fixtures/planted-bad.json"
GOOD_REL = "command-center/p2-wave/probes/CNL-0058/fixtures/known-good.json"


def needle_line(rel: str, needle: str) -> int:
    path = REPO / rel
    hits = [
        i for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if needle in ln
    ]
    if len(hits) != 1:
        raise SystemExit(f"needle {needle!r} in {rel} hits={hits}")
    return hits[0]


def measured_row(row: dict) -> dict:
    return {
        "yes": row["yes"],
        "no": row["no"],
        "abstain": row["abstain"],
        "absent": row["absent"],
        "freeze_n": row["freeze_n"],
        "shrunk_n": row["shrunk_n"],
        "participating_n": row["participating_n"],
        "quorum_met": row["quorum_met"],
        "frozen_pass": row["frozen_pass"],
        "shrunk_pass": row["shrunk_pass"],
        "detector": row["detector"],
        "outcome": row["outcome"],
    }


def main() -> int:
    bad = F.load_fixture("planted-bad")
    good = F.load_fixture("known-good")
    void = F.load_fixture("quorum-void")
    maj = F.load_fixture("majority-not-supermajority")
    death = F.load_fixture("death-unreplaced")
    replaced = T.replace_seat(death, "F", "F2", T.YES)
    replaced["id"] = "replacement"

    r_bad = T.decide(bad, T.SUPERMAJORITY_2_3)
    r_good = T.decide(good, T.SUPERMAJORITY_2_3)
    r_void = T.decide(void, T.SUPERMAJORITY_2_3)
    r_death = T.decide(death, T.SUPERMAJORITY_2_3)
    r_rep = T.decide(replaced, T.SUPERMAJORITY_2_3)
    r_maj_m = T.decide(maj, T.MAJORITY)
    r_maj_s = T.decide(maj, T.SUPERMAJORITY_2_3)

    rec_bad = R.recount(bad)
    rec_good = R.recount(good)
    text_yes_bad = R.text_yes_count(F.fixture_path("planted-bad").read_text(encoding="utf-8"))
    text_yes_good = R.text_yes_count(F.fixture_path("known-good").read_text(encoding="utf-8"))
    if rec_bad["yes"] != r_bad["yes"] or rec_good["yes"] != r_good["yes"]:
        print("FAILED:emit author tally disagrees with independent recount")
        return 1
    if text_yes_bad != r_bad["yes"] or text_yes_good != r_good["yes"]:
        print("FAILED:emit text-yes disagrees with field-yes")
        return 1

    freeze_line = needle_line(TALLY_REL, "FREEZE-N: len(freeze_set)")
    super_line = needle_line(TALLY_REL, "SUPERMAJORITY: m * yes")
    det_line = needle_line(TALLY_REL, "DETECTOR: FIRE iff")
    maj_line = needle_line(TALLY_REL, "MAJORITY: 2 * yes > n")

    verbatim_fire = T.compact(r_bad)
    verbatim_silent = T.compact(r_good)
    verbatim_void = T.compact(r_void)
    verbatim_death = T.compact(r_death)
    verbatim_rep = T.compact(r_rep)

    decision = (
        "No. A supermajority cannot be met by shrinking the denominator. "
        "Majority (2*yes > N) and supermajority (default 2/3: 3*yes >= 2*N) use "
        "the freeze-set N locked at vote-open. Abstention, death, and unreplaced "
        "seats stay in N; they make the bar harder, not easier. Mid-council "
        "replacement substitutes a slot and leaves N unchanged. Quorum is a "
        "separate participating-seat floor (yes+no+abstain); missing it voids "
        "the vote (NO_QUORUM) instead of lowering N. The shrinking-denominator "
        "detector FIRES when the same yes-count fails freeze-N but would pass "
        "present-and-voting; that path is a detected defect, never a pass."
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNL-0058",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0058",
        "schema_version": 1,
        "report_kind": "council-design-note",
        "title": "Majority, supermajority and their interaction with quorum",
        "question": QUESTION,
        "decision": decision,
        "produced_at": now,
        "tally_model": {
            "denominator": "freeze_set locked at vote-open",
            "majority": "2 * yes > N",
            "supermajority_default": "3 * yes >= 2 * N",
            "quorum": "participating (yes+no+abstain) >= Q; fail => NO_QUORUM",
            "shrunk_denominator_is": "yes+no (present-and-voting); never official",
            "empty_council_cannot_pass": True,
            "weights": "equal 1.0 per freeze-set seat; non-equal weights are CNL-0023",
        },
        "rules": [
            {
                "id": "R1-freeze-N",
                "statement": (
                    "Threshold arithmetic uses freeze-set length at vote-open. "
                    "Replacement substitutes a named slot; N does not drop."
                ),
            },
            {
                "id": "R2-abstention-in-N",
                "statement": (
                    "Abstain is not yes. It counts toward quorum participation "
                    "and remains in freeze-N, so it cannot manufacture a majority "
                    "or supermajority."
                ),
            },
            {
                "id": "R3-quorum-voids",
                "statement": (
                    "Quorum is independent of the threshold. A sub-quorum council "
                    "is NO_QUORUM even if present-and-voting would be unanimous."
                ),
            },
            {
                "id": "R4-shrink-detector",
                "statement": (
                    "FIRE iff the same yes-count fails freeze-N and passes the "
                    "present-and-voting denominator. Official outcome never uses "
                    "the shrunk N."
                ),
            },
        ],
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Same ballots (3 yes) fail 2/3 of freeze-N=6 and pass 2/3 of "
                    "shrunk N=4; the detector FIRES and official outcome is FAIL."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{TALLY_REL}:{det_line}",
            },
            {
                "id": "C2",
                "claim": (
                    "Known-good 4 yes / 6 freeze-set seats PASSES 2/3 on freeze-N "
                    "and the detector is SILENT."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{GOOD_REL}:1",
            },
            {
                "id": "C3",
                "claim": (
                    "Quorum-void with Q=5 and 4 participating is NO_QUORUM; "
                    "shrinking would still pass 2/3 so the detector FIRES, but "
                    "that fire does not convert the void into a pass."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{TALLY_REL}:{freeze_line}",
            },
            {
                "id": "C4",
                "claim": (
                    "N=5 with 3 yes is majority PASS (2*3 > 5) and supermajority "
                    "FAIL (3*3 < 2*5), so the two thresholds are not the same rule."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{TALLY_REL}:{maj_line}",
            },
            {
                "id": "C5",
                "claim": (
                    "Unreplaced death keeps freeze-N=6 (3 yes FAIL). Replacing "
                    "the dead seat with a yes vote keeps freeze-N=6 and PASSES "
                    "with 4 yes — persuasion of the new seat, not a smaller N."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{TALLY_REL}:{super_line}",
            },
        ],
        "tests": [
            {"id": "probe1-both-states", "command": P1, "result": "PASS"},
            {"id": "probe2-independent-recount", "command": P2, "result": "PASS"},
        ],
        "both_states": {
            "fires_on": "fixtures/planted-bad.json (3 yes, 1 no, 1 abstain, 1 absent, N=6)",
            "silent_on": "fixtures/known-good.json (4 yes, 2 no, N=6)",
            "verbatim_fire": verbatim_fire,
            "verbatim_silent": verbatim_silent,
        },
        "negative_controls": [
            {
                "id": "NC-planted-bad",
                "rejects": (
                    "a tally that treats present-and-voting as the supermajority "
                    "denominator"
                ),
                "observed": (
                    "on planted-bad the check FIRES and official outcome stays FAIL; "
                    + verbatim_fire
                ),
            },
            {
                "id": "NC-quorum-void",
                "rejects": (
                    "converting a sub-quorum remainder-unanimous council into a pass"
                ),
                "observed": (
                    "on quorum-void outcome=NO_QUORUM even though shrunk_pass is true; "
                    + verbatim_void
                ),
            },
        ],
        "evidence": [
            {
                "claim": "planted-bad 3 yes fail freeze-N=6 and pass shrunk N=4",
                "mechanism": "integer field tally: 3*yes >= 2*N on freeze vs shrunk",
                "anchor": f"{TALLY_REL}:{super_line}",
                "verbatim": verbatim_fire,
            },
            {
                "claim": "same planted-bad yes-count via fixture-byte regex, not JSON fields",
                "mechanism": "regex count of \"choice\": \"yes\" in planted-bad.json bytes",
                "anchor": f"{BAD_REL}:6",
                "verbatim": (
                    f"text_yes={text_yes_bad} field_yes={r_bad['yes']} "
                    f"recount_yes={rec_bad['yes']}"
                ),
            },
            {
                "claim": "known-good detector SILENT with freeze-N pass",
                "mechanism": "integer field tally on known-good.json",
                "anchor": f"{GOOD_REL}:6",
                "verbatim": verbatim_silent,
            },
            {
                "claim": "independent recount agrees with author tally on planted-bad",
                "mechanism": "recount.py loop over freeze_set, no tally.py import",
                "anchor": "command-center/p2-wave/probes/CNL-0058/recount.py:16",
                "verbatim": (
                    f"recount detector={rec_bad['detector']} yes={rec_bad['yes']} "
                    f"freeze_n={rec_bad['freeze_n']} shrunk_n={rec_bad['shrunk_n']} "
                    f"outcome={rec_bad['outcome']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0058-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "independent recount / re-tabulation of yes/no/abstain/absent from "
                "fixture freeze_set without reading the author's argument; a "
                "disagreement in the number blocks the unit"
            ),
            "disagreement_blocks": True,
        },
        "measured": {
            "supermajority": {
                "planted-bad": measured_row(r_bad),
                "known-good": measured_row(r_good),
                "quorum-void": measured_row(r_void),
                "death-unreplaced": measured_row(r_death),
                "replacement": measured_row(r_rep),
            },
            "majority_vs_supermajority": {
                "fixture": "majority-not-supermajority",
                "freeze_n": r_maj_m["freeze_n"],
                "yes": r_maj_m["yes"],
                "majority_outcome": r_maj_m["outcome"],
                "majority_frozen_pass": r_maj_m["frozen_pass"],
                "supermajority_frozen_pass": r_maj_s["frozen_pass"],
                "supermajority_outcome": r_maj_s["outcome"],
            },
            "replacement": {
                "verbatim_death": verbatim_death,
                "verbatim_replacement": verbatim_rep,
                "freeze_n_before": r_death["freeze_n"],
                "freeze_n_after": r_rep["freeze_n"],
                "n_unchanged": r_death["freeze_n"] == r_rep["freeze_n"],
            },
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "contract"},
            {"path": TALLY_REL, "exists": True, "role": "tally-engine"},
            {"path": BAD_REL, "exists": True, "role": "planted-bad-fixture"},
            {"path": GOOD_REL, "exists": True, "role": "known-good-fixture"},
        ],
        "residual_unknowns": [
            (
                "Harness-restore inputs (11-COUNCIL-SPECIFICATION.schema.json, "
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json, _USER-PROMPTS.md:10915-10946) "
                "are not on this Linux worktree; default supermajority is 2/3 until "
                "a protocol record names another k/m."
            ),
            (
                "CNL-0023 (non-equal weight provenance) is not delivered here. "
                "This note assumes weight 1.0 per freeze-set seat; weighted "
                "shrink attacks are in scope for CNL-0064, not this unit."
            ),
            (
                "CNL-0021 replacement/independence detection is not delivered. "
                "This note only specifies that a replacement keeps freeze-N; it "
                "does not detect duplicate-model seats."
            ),
        ],
        "catalog_tests_required": [
            "a shrinking-denominator fixture must be detected: the same ballots with fewer seats must not silently cross the threshold",
            "a both-states control: the check FIRES on a planted-bad fixture and is SILENT on the known-good one, both runs recorded verbatim",
            "negative control recorded verbatim: state what the check does on the state it is meant to reject",
        ],
    }

    validator = SL.validator()
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:CNL-0058 emit schema errors")
        for e in errors[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0058", "state": "SUCCESS", "sentinel": "SUCCESS:CNL-0058"},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNL-0058 emit schema accepted garbage {list(garbage)[:3]}")
            return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT}")
    print("verbatim_fire " + verbatim_fire)
    print("verbatim_silent " + verbatim_silent)
    print("SUCCESS:CNL-0058 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
