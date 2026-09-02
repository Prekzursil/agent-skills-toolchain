#!/usr/bin/env python3
"""Emit the CNL-0071 design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fingerprint import attach_moves  # noqa: E402
from gain import attach_trace, last_defined_gain  # noqa: E402
from irreducibility import attach_honest_trace, check_declaration  # noqa: E402
from note_schema import rejects_garbage, validate_note  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0071-irreducible-disagreement-when-to-stop-trying-to-converge.md"
)
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
QUESTION = (
    "What distinguishes a disagreement that more rounds would resolve from one "
    "that no amount of deliberation can - and what evidence must accompany an "
    "irreducible-disagreement verdict so it is not simply fatigue relabelled?"
)


def line_of(rel: str, needle: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"needle not found in {rel}: {needle!r}")


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    garbage_ok, garbage_why = rejects_garbage()
    if not garbage_ok:
        print("FAILED:emit garbage control", garbage_why)
        return 1

    bad = attach_honest_trace(load_fix("planted-bad.json"))
    good = attach_honest_trace(load_fix("known-good.json"))
    fat = attach_honest_trace(load_fix("fatigue.json"))
    bad_v = check_declaration(bad)
    good_v = check_declaration(good)
    fat_v = check_declaration(fat)
    if not bad_v.get("fired") or bad_v.get("reason") != "positive-gain":
        print("FAILED:emit planted-bad did not fire", bad_v)
        return 1
    if good_v.get("fired") or not good_v.get("accepted"):
        print("FAILED:emit known-good not accepted", good_v)
        return 1
    if not fat_v.get("fired") or fat_v.get("reason") != "fatigue-relabel":
        print("FAILED:emit fatigue did not fire", fat_v)
        return 1

    bad_last = last_defined_gain(bad["information_gain_trace"])
    good_last = last_defined_gain(good["information_gain_trace"])
    moves_bad = attach_moves(bad["rounds"])
    moves_good = attach_moves(good["rounds"])

    gain_rel = "command-center/p2-wave/probes/CNL-0071/gain.py"
    fp_rel = "command-center/p2-wave/probes/CNL-0071/fingerprint.py"
    irr_rel = "command-center/p2-wave/probes/CNL-0071/irreducibility.py"
    cat_rel = "command-center/WORK-UNIT-CATALOG.json"
    p1_rel = "command-center/p2-wave/probes/CNL-0071/probe1_positive_gain_must_fail.py"
    p2_rel = "command-center/p2-wave/probes/CNL-0071/probe2_negative_control.py"

    pos_line = line_of(irr_rel, 'reason": "positive-gain"')
    miss_line = line_of(irr_rel, 'reason": "missing-information-gain-trace"')
    fat_line = line_of(irr_rel, 'reason": "fatigue-relabel"')
    gain_line = line_of(gain_rel, "gain = content + hamming")
    fp_line = line_of(fp_rel, "moved = claims_moved or evidence_moved or votes_moved")
    q_line = line_of(cat_rel, "no amount of deliberation can")
    t_line = line_of(cat_rel, "declaring irreducibility while gain is still positive")

    p1_cmd = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p1_rel}"
    p2_cmd = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p2_rel}"

    nc_verbatim = (
        f"rejected_state=declared_outcome=irreducible-disagreement AND "
        f"last-round information gain > 0; "
        f"planted-bad fired={bad_v.get('fired')} reason={bad_v.get('reason')} "
        f"last_gain={bad_last}; "
        f"known-good fired={good_v.get('fired')} silent={good_v.get('silent')} "
        f"reason={good_v.get('reason')}"
    )

    doc = {
        "unit_id": "CNL-0071",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0071",
        "title": "Irreducible disagreement: when to stop trying to converge",
        "output_schema": SCHEMA_REL,
        "catalog_path_is_md_bytes_are_json": True,
        "question": QUESTION,
        "answer": (
            "More rounds can still resolve a disagreement when the attached "
            "information-gain trace shows the last stable_window rounds still "
            "moving: new claim ids, new evidence ids, or vote Hamming > 0 "
            "(signal 1) AND a sha256 mismatch of the canonical claim/evidence "
            "dumps or vote tuple (signal 2). No amount of further deliberation "
            "is the right call only when those two signals agree that gain has "
            "collapsed for the window, the position partition is unchanged, "
            "and the record names an irreducible_set of at least two claims "
            "that cannot be jointly satisfied for a reason that is not budget, "
            "timeout, or fatigue. Round-budget exhaustion without that pack is "
            "no-decision / fatigue, not irreducible-disagreement."
        ),
        "distinction": {
            "resolvable_if": (
                "last defined round-gain > 0, or any round inside stable_window "
                "still moved on either independent signal."
            ),
            "irreducible_if": (
                "honest trace attached, both signals agree gain==0 and "
                "moved==false for stable_window consecutive rounds, stop_reason "
                "is an incommensurability class, and irreducible_set names the "
                "mutually unsatisfiable claims."
            ),
            "fatigue_is_not": (
                "stop_reason in {round-budget, timeout, fatigue, chair-discretion, "
                "majority-tired}, or an irreducible_set whose why is tired/budget, "
                "even if gain has already hit zero."
            ),
            "not_deadlock": (
                "CNL-0084 (not delivered on this tree) is process-stuck vs "
                "slow-but-progressing. This unit is epistemic: still-moving "
                "disagreement vs named incommensurability after gain collapse."
            ),
            "not_circular_debate_detector": (
                "CNL-0090 (not delivered) detects circling. Circling without a "
                "named irreducible_set is circular-debate, not irreducible-"
                "disagreement."
            ),
        },
        "irreducible_verdict_requirements": [
            "information_gain_trace attached covering every round; missing trace fails the declaration",
            "recomputed trace must match the attached one (forged zero-gain is rejected)",
            "signal 1 (set cardinality + vote Hamming) and signal 2 (sha256 canonical dump inequality) must agree; disagreement fails closed",
            "last stable_window rounds (default 2) have gain==0 and moved==false",
            "stop_reason in {incommensurable-positions, incompatible-evidence-standards, mutually-exclusive-axioms}",
            "irreducible_set has >=2 paired claims with a why that is not fatigue/budget/timeout",
        ],
        "gain_definition": {
            "signal_1": "gain(t)=|claims_t-claims_{t-1}|+|evidence_t-evidence_{t-1}|+Hamming(votes_t,votes_{t-1})",
            "signal_2": "moved(t)=sha256(canon(claim_ids)) or sha256(canon(evidence_ids)) or vote-tuple differs",
            "round_1": "no predecessor; gain and moved are undefined",
            "identifier_not_lexical": (
                "Gain is over claim/evidence identifiers, not paraphrase text. "
                "A rewrite of the same id is NOT counted as gain here. Semantic "
                "uniqueness is CNL-0051 / CNL-0090 and is residual."
            ),
        },
        "claims": [
            {
                "id": "C1",
                "claim": "Declaring irreducible-disagreement while last-round information gain is still positive must be rejected.",
                "verdict": "CONFIRMED",
                "anchor": f"{irr_rel}:{pos_line}",
            },
            {
                "id": "C2",
                "claim": "An irreducible declaration with no attached information-gain trace must be rejected.",
                "verdict": "CONFIRMED",
                "anchor": f"{irr_rel}:{miss_line}",
            },
            {
                "id": "C3",
                "claim": "Zero-gain plus a round-budget/fatigue stop is fatigue relabel, not irreducible-disagreement.",
                "verdict": "CONFIRMED",
                "anchor": f"{irr_rel}:{fat_line}",
            },
            {
                "id": "C4",
                "claim": "A collapsed-gain run with incommensurable-positions and a two-claim irreducible_set is accepted (known-good silent).",
                "verdict": "CONFIRMED",
                "anchor": f"{p2_rel}:1",
            },
        ],
        "evidence": [
            {
                "claim": "Catalog question and the positive-gain fail test for this unit.",
                "verdict": "CONFIRMED",
                "anchor": f"{cat_rel}:{q_line}",
                "second_anchor": f"{cat_rel}:{t_line}",
            },
            {
                "claim": "Signal 1 is cardinality+Hamming, not a hash.",
                "verdict": "CONFIRMED",
                "anchor": f"{gain_rel}:{gain_line}",
            },
            {
                "claim": "Signal 2 is sha256/tuple inequality, not a count.",
                "verdict": "CONFIRMED",
                "anchor": f"{fp_rel}:{fp_line}",
            },
            {
                "claim": "Planted-bad last gain is positive; known-good last gain is 0.",
                "verdict": "CONFIRMED",
                "anchor": f"{HERE.relative_to(REPO).as_posix()}/fixtures/planted-bad.json:1",
                "measured": {
                    "planted_bad_last_gain": bad_last,
                    "known_good_last_gain": good_last,
                    "planted_bad_check": bad_v,
                    "known_good_check": good_v,
                    "fatigue_check": fat_v,
                    "planted_bad_moves_last": moves_bad[-1],
                    "known_good_moves_last": moves_good[-1],
                },
            },
        ],
        "tests": [
            {
                "id": "probe1",
                "command": p1_cmd,
                "result": "NOT-RUN",
                "requirement": "information-gain trace attached; declaring irreducibility while gain is still positive must FAIL",
            },
            {
                "id": "probe2",
                "command": p2_cmd,
                "result": "NOT-RUN",
                "requirement": "negative control recorded verbatim: what the check does on the state it is meant to reject",
            },
        ],
        "negative_controls": [
            {
                "rejected_state": (
                    "declared_outcome=irreducible-disagreement AND last-round "
                    "information gain > 0"
                ),
                "check_behavior": (
                    "FIRES (rejects the declaration) with reason=positive-gain"
                ),
                "verbatim": nc_verbatim,
                "known_good_behavior": (
                    "SILENT / accepted=true with reason=irreducible-evidence-complete"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0071-probe1-positive-gain-counterexample",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "counterexample": (
                "fixtures/planted-bad.json declares irreducible-disagreement "
                f"with last_gain={bad_last}; check fires reason=positive-gain."
            ),
            "human_fresh_context": "REFUTED-NOT-ATTEMPTED",
        },
        "strongest_surviving_counterargument": (
            "Identifier-set gain treats a same-id paraphrase as zero content "
            "gain. If members only reword C1/C2, this unit will allow an "
            "irreducible verdict once votes also freeze. Whether that paraphrase "
            "is still 'new information' is CNL-0051/CNL-0090 and is NOT-CHECKED "
            "here. The 0.95 consensus interaction is CNL-0069, also residual."
        ),
        "dependencies_on_this_tree": {
            "CNL-0069": "artifact absent — consensus number not used as a gate in this check",
            "CNL-0084": "artifact absent — deadlock ladder not used; distinction stated in prose only",
        },
        "inputs_on_this_tree": {
            "_USER-PROMPTS.md:10746-10767": False,
            "_USER-PROMPTS.md:10915-10946": False,
            "11-COUNCIL-SPECIFICATION.schema.json": False,
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
            "note": (
                "Harness paths from the catalog are not present on this worktree. "
                "No quotes from those files are invented. Anchors are catalog + live probes."
            ),
        },
        "schema_garbage_control": {
            "ok": garbage_ok,
            "detail": garbage_why,
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {"path": irr_rel, "exists": True, "role": "check"},
        ],
        "residual_unknowns": [
            "Harness restore files named in catalog inputs are absent; v1 $defs.outcome 17-enum not re-derived here (that is CNL-0072).",
            "CNL-0069 0.95 consensus definition is not on disk; this unit does not treat consensus>=0.95 as irreducibility.",
            "CNL-0084 deadlock escalation ladder is not on disk.",
            "Semantic paraphrase-vs-new-claim (CNL-0051) is not this metric.",
            "A separate human reviewer in a fresh context was REFUTED-NOT-ATTEMPTED; the executable counterexample is probe1.",
        ],
        "SUCCESS:CNL-0071": True,
    }

    ok, why = validate_note(doc)
    if not ok:
        print("FAILED:emit note schema", why)
        return 1

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={dest.stat().st_size}")
    print("SUCCESS:CNL-0071 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
