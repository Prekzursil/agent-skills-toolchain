"""Commit-reveal secret ballot with a verifiable public tally (IMP-0346)."""
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Iterable, Sequence


class SecretBallotError(ValueError):
    """Opening set does not bijection the commitment set."""


def _sha(parts: Sequence[str]) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


def make_nonce() -> str:
    return os.urandom(16).hex()


def commit(election_id: str, choice: str, nonce: str) -> str:
    return _sha([election_id, choice, nonce])


def verify_opening(election_id: str, commitment: str, choice: str, nonce: str) -> bool:
    return hmac.compare_digest(commit(election_id, choice, nonce), commitment)


@dataclass
class Tally:
    n_ballots: int
    n_commitments: int
    counts: dict[str, int]

    def as_dict(self) -> dict:
        return {
            "n_ballots": self.n_ballots,
            "n_commitments": self.n_commitments,
            "counts": dict(self.counts),
        }


def recompute_tally(
    election_id: str,
    commitments: Sequence[str],
    openings: Sequence[dict],
) -> Tally:
    if len(openings) != len(commitments):
        raise SecretBallotError("opening/commitment cardinality mismatch")
    want = list(commitments)
    used: set[str] = set()
    counts: dict[str, int] = {}
    for raw in openings:
        choice = str(raw.get("choice") or "")
        nonce = str(raw.get("nonce") or "")
        commitment = str(raw.get("commitment") or "")
        if commitment not in want or commitment in used:
            raise SecretBallotError("opening is not a bijection of commitments")
        if not verify_opening(election_id, commitment, choice, nonce):
            raise SecretBallotError("opening failed to verify")
        used.add(commitment)
        counts[choice] = counts.get(choice, 0) + 1
    if set(used) != set(want):
        raise SecretBallotError("commitment set not fully opened")
    return Tally(n_ballots=len(openings), n_commitments=len(commitments), counts=counts)


def public_view_leaks_voter_ids(view: dict, voters: Iterable[str]) -> list[str]:
    blob = json_dumps(view)
    return [v for v in voters if v and v in blob]


def json_dumps(obj: object) -> str:
    import json

    return json.dumps(obj, sort_keys=True)


def run_election(
    election_id: str,
    ballots: Sequence[tuple[str, str]],
    canonical_order: bool = True,
) -> dict:
    openings = []
    voters = []
    for voter_id, choice in ballots:
        nonce = make_nonce()
        commitment = commit(election_id, choice, nonce)
        openings.append({"commitment": commitment, "choice": choice, "nonce": nonce})
        voters.append(voter_id)
    commitments = [row["commitment"] for row in openings]
    if canonical_order:
        order = sorted(range(len(commitments)), key=lambda i: commitments[i])
        commitments = [commitments[i] for i in order]
        openings = [openings[i] for i in order]
    tally = recompute_tally(election_id, commitments, openings)
    view = {
        "election_id": election_id,
        "scheme": "commit-reveal-hmac-sha256",
        "order": "canonical-commitment-hex" if canonical_order else "submission",
        "commitments": commitments,
        "openings": openings,
        "tally": tally.as_dict(),
    }
    truth = {voter_id: choice for voter_id, choice in ballots}
    return {
        "public_view": view,
        "voters_in_submission_order": voters,
        "truth_choice_by_voter": truth,
        "tally": tally,
    }


def positional_deanonymise(
    voters: Sequence[str],
    commitments: Sequence[str],
    openings: Sequence[dict],
    truth_choice_by_voter: dict[str, str],
) -> dict:
    hits = 0
    for i, voter in enumerate(voters):
        if i < len(openings) and openings[i].get("choice") == truth_choice_by_voter.get(voter):
            hits += 1
    n = len(voters)
    return {
        "accuracy": (hits / n) if n else 0.0,
        "hits": hits,
        "n": n,
        "positional_hits": hits,
    }


__all__ = [
    "SecretBallotError",
    "Tally",
    "commit",
    "make_nonce",
    "public_view_leaks_voter_ids",
    "recompute_tally",
    "run_election",
    "verify_opening",
]
