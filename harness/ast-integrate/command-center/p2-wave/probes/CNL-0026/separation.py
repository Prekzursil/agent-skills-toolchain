#!/usr/bin/env python3
"""Judge/juror separation: authority over the published outcome, not seat labels.

Separated: published outcome = mechanical majority of juror ballots. The judge
has no ballot and may only certify that tally. Certification failure does not
replace the tally.

Fused (relabel): the judge's write-up IS the published outcome. Juror ballots
are advisory and dissent can vanish from the decision record.

The corruption threshold is the size of the smallest role set whose corruption
flips the published outcome. It is found by enumerating subsets, not asserted.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Iterable

SUPPORT = "SUPPORT"
REJECT = "REJECT"
HUNG = "NO-DECISION"
ABSTAIN = "ABSTAIN"

N_JURORS = 5
KNOWN_ANSWER = SUPPORT
WRONG = REJECT


def majority_need(n: int) -> int:
    return n // 2 + 1


def mechanical_majority(ballots: list[str]) -> str:
    """Strict majority of juror *seats* (abstention cannot manufacture a majority)."""
    n = len(ballots)
    need = majority_need(n)
    counted = Counter(b for b in ballots if b in (SUPPORT, REJECT))
    if counted[SUPPORT] >= need:
        return SUPPORT
    if counted[REJECT] >= need:
        return REJECT
    return HUNG


def publish_separated(juror_ballots: list[str], judge_certified: str) -> dict:
    mechanical = mechanical_majority(juror_ballots)
    dissent = [b for b in juror_ballots if b not in (mechanical, ABSTAIN)]
    if mechanical == HUNG:
        dissent = [b for b in juror_ballots if b in (SUPPORT, REJECT)]
    return {
        "mode": "separated",
        "outcome": mechanical,
        "mechanical": mechanical,
        "certification_accepted": judge_certified == mechanical,
        "judge_had_ballot": False,
        "dissent_ballots": dissent,
        "dissent_preserved": True,
        "n_jurors": len(juror_ballots),
        "need": majority_need(len(juror_ballots)),
        "tally": dict(Counter(juror_ballots)),
    }


def publish_fused(juror_ballots: list[str], judge_written: str) -> dict:
    mechanical = mechanical_majority(juror_ballots)
    return {
        "mode": "fused",
        "outcome": judge_written,
        "mechanical": mechanical,
        "certification_accepted": True,
        "judge_had_ballot": True,
        "dissent_ballots": [],
        "dissent_preserved": False,
        "n_jurors": len(juror_ballots),
        "need": majority_need(len(juror_ballots)),
        "tally": dict(Counter(juror_ballots)),
    }


def publish(mode: str, juror_ballots: list[str], judge_value: str) -> dict:
    if mode == "separated":
        return publish_separated(juror_ballots, judge_value)
    if mode == "fused":
        return publish_fused(juror_ballots, judge_value)
    raise ValueError(f"unknown mode {mode}")


def honest_unanimous_panel() -> tuple[list[str], str]:
    return [SUPPORT] * N_JURORS, SUPPORT


def honest_with_dissent_panel() -> tuple[list[str], str]:
    return [SUPPORT, SUPPORT, SUPPORT, SUPPORT, REJECT], SUPPORT


def hung_panel() -> tuple[list[str], str]:
    return [SUPPORT, SUPPORT, REJECT, REJECT, ABSTAIN], SUPPORT


def apply_corruption(
    juror_ballots: list[str],
    judge_value: str,
    corrupted: Iterable[str],
    wrong: str = WRONG,
) -> tuple[list[str], str]:
    ballots = list(juror_ballots)
    judge = judge_value
    for role in corrupted:
        if role == "judge":
            judge = wrong
        elif role.startswith("juror_"):
            idx = int(role.split("_", 1)[1])
            ballots[idx] = wrong
        else:
            raise ValueError(f"unknown role {role}")
    return ballots, judge


def role_ids(n: int) -> list[str]:
    return [f"juror_{i}" for i in range(n)] + ["judge"]


def min_corrupting_sets(
    mode: str,
    juror_ballots: list[str],
    judge_value: str,
    wrong: str = WRONG,
) -> dict:
    """Brute-force the minimum role sets that flip the published outcome."""
    n = len(juror_ballots)
    roles = role_ids(n)
    honest = publish(mode, juror_ballots, judge_value)
    honest_outcome = honest["outcome"]
    found: list[list[str]] = []
    min_k: int | None = None
    examined = 0
    for k in range(1, len(roles) + 1):
        hits_at_k: list[list[str]] = []
        for subset in combinations(roles, k):
            examined += 1
            b, j = apply_corruption(juror_ballots, judge_value, subset, wrong)
            out = publish(mode, b, j)["outcome"]
            if out != honest_outcome:
                hits_at_k.append(list(subset))
        if hits_at_k:
            min_k = k
            found = hits_at_k
            break
    judge_alone = publish(
        mode, *apply_corruption(juror_ballots, judge_value, ["judge"], wrong)
    )
    return {
        "mode": mode,
        "honest_outcome": honest_outcome,
        "honest_tally": honest["tally"],
        "n_roles": len(roles),
        "n_jurors": n,
        "majority_need": majority_need(n),
        "min_k": min_k,
        "min_sets": found,
        "min_sets_count": len(found),
        "judge_in_every_min_set": bool(found) and all("judge" in s for s in found),
        "judge_in_any_min_set": any("judge" in s for s in found),
        "judge_alone_outcome": judge_alone["outcome"],
        "judge_alone_flips": judge_alone["outcome"] != honest_outcome,
        "subsets_examined": examined,
        "computed_not_asserted": True,
        "method": (
            "enumerate combinations of role ids by increasing size; "
            "first size that flips published outcome is min_k"
        ),
    }


def judge_spof_check(mode: str, juror_ballots: list[str], judge_value: str) -> dict:
    """FIRE when corrupting only the judge flips the published outcome."""
    honest = publish(mode, juror_ballots, judge_value)
    corrupted = publish(
        mode, *apply_corruption(juror_ballots, judge_value, ["judge"])
    )
    flipped = corrupted["outcome"] != honest["outcome"]
    return {
        "check_id": "judge-alone-determines-outcome",
        "mode": mode,
        "honest_outcome": honest["outcome"],
        "corrupted_judge_outcome": corrupted["outcome"],
        "flipped": flipped,
        "fires": flipped,
        "silent": not flipped,
        "dissent_preserved_honest": honest["dissent_preserved"],
        "dissent_preserved_corrupted": corrupted["dissent_preserved"],
        "certification_accepted_corrupted": corrupted["certification_accepted"],
    }


def both_states_control() -> dict:
    ballots, judge = honest_unanimous_panel()
    separated = judge_spof_check("separated", ballots, judge)
    fused = judge_spof_check("fused", ballots, judge)
    return {
        "fixture": "unanimous-SUPPORT-N5",
        "known_answer": KNOWN_ANSWER,
        "separated": separated,
        "fused": fused,
        "silent_on_separated": separated["silent"] is True,
        "fires_on_fused": fused["fires"] is True,
        "pass": separated["silent"] is True and fused["fires"] is True,
    }


def hung_control() -> dict:
    ballots, judge_pick = hung_panel()
    sep = publish_separated(ballots, judge_pick)
    fused = publish_fused(ballots, judge_pick)
    return {
        "fixture": "2-2-1-abstain",
        "separated_outcome": sep["outcome"],
        "fused_outcome": fused["outcome"],
        "separated_is_hung": sep["outcome"] == HUNG,
        "fused_judge_picks": fused["outcome"] == judge_pick,
        "pass": sep["outcome"] == HUNG and fused["outcome"] == judge_pick,
    }


def dissent_control() -> dict:
    ballots, judge = honest_with_dissent_panel()
    sep_honest = publish_separated(ballots, judge)
    sep_bad_cert = publish_separated(ballots, REJECT)
    fused_drop = publish_fused(ballots, SUPPORT)
    return {
        "fixture": "4-SUPPORT-1-REJECT",
        "separated_outcome": sep_honest["outcome"],
        "separated_dissent_count": len(sep_honest["dissent_ballots"]),
        "bad_cert_outcome": sep_bad_cert["outcome"],
        "bad_cert_accepted": sep_bad_cert["certification_accepted"],
        "bad_cert_dissent_count": len(sep_bad_cert["dissent_ballots"]),
        "fused_dissent_count": len(fused_drop["dissent_ballots"]),
        "pass": (
            sep_honest["outcome"] == SUPPORT
            and len(sep_honest["dissent_ballots"]) == 1
            and sep_bad_cert["outcome"] == SUPPORT
            and sep_bad_cert["certification_accepted"] is False
            and len(sep_bad_cert["dissent_ballots"]) == 1
            and fused_drop["dissent_ballots"] == []
        ),
    }


def verbatim_line(row: dict) -> str:
    return (
        f"CHECK|id={row['check_id']}|mode={row['mode']}"
        f"|honest_outcome={row['honest_outcome']}"
        f"|corrupted_judge_outcome={row['corrupted_judge_outcome']}"
        f"|flipped={str(row['flipped']).lower()}"
        f"|fires={str(row['fires']).lower()}"
        f"|silent={str(row['silent']).lower()}"
        f"|certification_accepted_corrupted={str(row['certification_accepted_corrupted']).lower()}"
    )


def live_measurement() -> dict:
    ballots, judge = honest_unanimous_panel()
    sep_cut = min_corrupting_sets("separated", ballots, judge)
    fused_cut = min_corrupting_sets("fused", ballots, judge)
    both = both_states_control()
    hung = hung_control()
    dissent = dissent_control()
    sep_line = verbatim_line(both["separated"])
    fused_line = verbatim_line(both["fused"])
    k = sep_cut["min_k"]
    need = majority_need(N_JURORS)
    formula_match = k == need
    return {
        "n_jurors": N_JURORS,
        "known_answer": KNOWN_ANSWER,
        "majority_need": need,
        "separated_cut": sep_cut,
        "fused_cut": fused_cut,
        "both_states": both,
        "hung": hung,
        "dissent": dissent,
        "verbatim_separated": sep_line,
        "verbatim_fused": fused_line,
        "negative_control_verbatim": (
            "NEGATIVE_CONTROL|state=fused-judge-writes-verdict|"
            "meant_to_reject=judge_is_single_point_of_epistemic_failure|"
            f"check_does={fused_line}|result=FIRES"
        ),
        "corruption_threshold": {
            "value": k,
            "n_jurors": N_JURORS,
            "formula": "floor(N/2)+1",
            "formula_value": need,
            "formula_matches_brute_force": formula_match,
            "unit": "roles",
            "which_roles": "juror seats only; judge is not in any minimum set",
            "fused_value": fused_cut["min_k"],
            "fused_which_roles": "judge alone",
            "computed_not_asserted": True,
            "method": sep_cut["method"],
            "subsets_examined": sep_cut["subsets_examined"],
            "min_sets_count": sep_cut["min_sets_count"],
            "judge_alone_flips_separated": sep_cut["judge_alone_flips"],
            "judge_alone_flips_fused": fused_cut["judge_alone_flips"],
        },
        "pass": (
            both["pass"]
            and hung["pass"]
            and dissent["pass"]
            and formula_match
            and k == 3
            and fused_cut["min_k"] == 1
            and fused_cut["judge_alone_flips"] is True
            and sep_cut["judge_alone_flips"] is False
            and sep_cut["judge_in_any_min_set"] is False
        ),
    }
