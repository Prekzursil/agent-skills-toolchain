#!/usr/bin/env python3
"""Named probe 2: de-anonymisation at chance; ordered publication as control."""
from __future__ import annotations

import json
import secrets
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SECRET_PATH = REPO / "tools" / "council" / "vote" / "secret.py"


def load_secret():
    sys.path.insert(0, str(REPO))
    from tools.council.vote import secret as mod  # noqa: E402

    return mod


def unique_ballots(n: int) -> list[tuple[str, str]]:
    return [(f"seat-{i:02d}", f"ticket-{i:02d}") for i in range(n)]


def attack(secret, election_id: str, ballots, canonical_order: bool) -> dict:
    result = secret.run_election(election_id, ballots, canonical_order=canonical_order)
    view = result["public_view"]
    leaked = secret.public_view_leaks_voter_ids(
        view, result["voters_in_submission_order"]
    )
    if leaked:
        raise SystemExit(f"FAILED:IMP-0346-probe2 leak {leaked}")
    report = secret.positional_deanonymise(
        result["voters_in_submission_order"],
        view["commitments"],
        view["openings"],
        result["truth_choice_by_voter"],
    )
    report["order"] = view["order"]
    report["leaks"] = leaked
    return report


def main() -> int:
    if not SECRET_PATH.is_file():
        print("FAILED:IMP-0346-probe2 missing tools/council/vote/secret.py")
        return 1
    secret = load_secret()
    n = 32
    ballots = unique_ballots(n)
    chance = 1.0 / n

    ordered = attack(secret, "imp-0346-probe2-ordered", ballots, canonical_order=False)
    if ordered["accuracy"] != 1.0:
        print("FAILED:IMP-0346-probe2 negative control did not rise to 1.0")
        print(json.dumps(ordered, sort_keys=True))
        return 1
    if ordered["order"] != "submission":
        print("FAILED:IMP-0346-probe2 expected submission order on control")
        return 1

    trials = []
    for i in range(8):
        # Fresh nonces each trial (cast generates them). Shuffle roster so the
        # submission sequence is not a hidden function of ticket labels.
        roster = list(ballots)
        for j in range(len(roster) - 1, 0, -1):
            k = secrets.randbelow(j + 1)
            roster[j], roster[k] = roster[k], roster[j]
        row = attack(
            secret,
            f"imp-0346-probe2-canonical-{i}",
            roster,
            canonical_order=True,
        )
        trials.append(row["accuracy"])
        if row["order"] != "canonical-commitment-hex":
            print("FAILED:IMP-0346-probe2 expected canonical order")
            return 1

    mean_acc = statistics.fmean(trials)
    max_acc = max(trials)
    # Chance is 1/n. Allow generous slack so the live probe is not a coin-flip
    # flake, while remaining far below the ordered control (1.0).
    if mean_acc >= 0.25 or max_acc >= 0.40:
        print("FAILED:IMP-0346-probe2 canonical accuracy not at chance")
        print(json.dumps({"trials": trials, "mean": mean_acc, "max": max_acc}))
        return 1
    if not (mean_acc < ordered["accuracy"]):
        print("FAILED:IMP-0346-probe2 control did not raise accuracy")
        return 1

    payload = {
        "probe": "probe2-deanonymisation",
        "unit_id": "IMP-0346",
        "pass": True,
        "n_ballots": n,
        "chance": chance,
        "canonical_trial_accuracies": trials,
        "canonical_mean_accuracy": mean_acc,
        "canonical_max_accuracy": max_acc,
        "ordered_negative_control_accuracy": ordered["accuracy"],
        "ordered_rises_above_chance": ordered["accuracy"] > chance,
        "canonical_at_chance": mean_acc < 0.25,
        "reviewer_starts_from_public_bulletin": True,
        "reviewer_grants_owner_signoff": False,
        "module": "tools/council/vote/secret.py",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"canonical_mean={mean_acc:.4f} chance={chance:.4f} "
        f"ordered={ordered['accuracy']:.4f} trials={len(trials)}"
    )
    print("SUCCESS:IMP-0346-probe2 de-anonymisation at chance; ordered control rises")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
