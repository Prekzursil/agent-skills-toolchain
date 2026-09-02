#!/usr/bin/env python3
"""Named probe 1: commit, reveal, independent tally from the commitment set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SECRET_PATH = REPO / "tools" / "council" / "vote" / "secret.py"


def load_secret():
    sys.path.insert(0, str(REPO))
    from tools.council.vote import secret as mod  # noqa: E402

    return mod


def main() -> int:
    if not SECRET_PATH.is_file():
        print("FAILED:IMP-0346-probe1 missing tools/council/vote/secret.py")
        return 1
    secret = load_secret()
    n = 32
    ballots = [(f"voter-{i:02d}", f"opt-{i:02d}") for i in range(n)]
    result = secret.run_election("imp-0346-probe1", ballots, canonical_order=True)
    view = result["public_view"]
    independent = secret.recompute_tally(
        view["election_id"], view["commitments"], view["openings"]
    )
    published = view["tally"]
    recomputed = independent.as_dict()
    if recomputed != published:
        print("FAILED:IMP-0346-probe1 published tally != independent recompute")
        print(json.dumps({"published": published, "recomputed": recomputed}, indent=2))
        return 1
    if recomputed["n_ballots"] != n or recomputed["n_commitments"] != n:
        print("FAILED:IMP-0346-probe1 tally cardinality")
        return 1
    if set(recomputed["counts"]) != {choice for _, choice in ballots}:
        print("FAILED:IMP-0346-probe1 choice set mismatch")
        return 1
    if any(v != 1 for v in recomputed["counts"].values()):
        print("FAILED:IMP-0346-probe1 expected unique choices")
        return 1
    if view["order"] != "canonical-commitment-hex":
        print("FAILED:IMP-0346-probe1 expected canonical order")
        return 1
    if view["commitments"] != sorted(view["commitments"]):
        print("FAILED:IMP-0346-probe1 commitments not canonically sorted")
        return 1
    leaked = secret.public_view_leaks_voter_ids(
        view, result["voters_in_submission_order"]
    )
    if leaked:
        print("FAILED:IMP-0346-probe1 public view leaked voters", leaked)
        return 1
    for raw in view["openings"]:
        if any(k in raw for k in ("voter_id", "voter", "submitter")):
            print("FAILED:IMP-0346-probe1 opening carries voter identity")
            return 1
        if not secret.verify_opening(
            view["election_id"], raw["commitment"], raw["choice"], raw["nonce"]
        ):
            print("FAILED:IMP-0346-probe1 opening failed to verify")
            return 1

    # Mutant: flip one nonce; independent recompute must refuse.
    bad = [dict(o) for o in view["openings"]]
    flipped = "0" if bad[0]["nonce"][0] != "0" else "1"
    bad[0]["nonce"] = flipped + bad[0]["nonce"][1:]
    refused = False
    try:
        secret.recompute_tally(view["election_id"], view["commitments"], bad)
    except secret.SecretBallotError:
        refused = True
    if not refused:
        print("FAILED:IMP-0346-probe1 mutant opening was accepted")
        return 1

    # Mutant: drop one opening; bijection must fail.
    dropped = list(view["openings"])[:-1]
    refused_drop = False
    try:
        secret.recompute_tally(view["election_id"], view["commitments"], dropped)
    except secret.SecretBallotError:
        refused_drop = True
    if not refused_drop:
        print("FAILED:IMP-0346-probe1 partial openings were accepted")
        return 1

    payload = {
        "probe": "probe1-commit-reveal-tally",
        "unit_id": "IMP-0346",
        "pass": True,
        "n_ballots": n,
        "independent_matches_published": True,
        "tally": recomputed,
        "mutant_bad_nonce_refused": True,
        "mutant_partial_openings_refused": True,
        "public_view_voter_id_leaks": [],
        "order": view["order"],
        "scheme": view["scheme"],
        "module": "tools/council/vote/secret.py",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "independent_matches=True n="
        f"{n} mutant_nonce_refused=True mutant_partial_refused=True leaks=0"
    )
    print("SUCCESS:IMP-0346-probe1 commit-reveal independent tally")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
