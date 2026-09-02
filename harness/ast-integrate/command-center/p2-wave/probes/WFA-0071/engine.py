#!/usr/bin/env python3
"""RETIRE re-adjudication engine.

Read-only. A manifest/export path is a claim; only retrieve+hash-match is a receipt.
A candidate already deleted with no preserved copy is P1, not completed retirement.
Retained RETIRE must name capability given up and where the mechanism survives.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]

P1_VERDICTS = frozenset(
    {
        "P1-UNPRESERVED",
        "P1-IDENTITY-UNRECOVERABLE",
        "P1-HASH-MISMATCH",
        "P1-CLAIM-NOT-RECEIPT",
    }
)
TERMINAL_VERDICTS = frozenset({"RETAIN-RETIRE"})


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return digest_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def existence_check(candidate: dict, repo: Path = REPO) -> dict:
    rel = str(candidate.get("live_path") or "").strip()
    if not rel:
        return {
            "present": False,
            "path": None,
            "reason": "no-live-path",
            "bytes": 0,
            "sha256": None,
        }
    path = Path(rel)
    if not path.is_absolute():
        path = repo / rel
    if not path.is_file():
        return {
            "present": False,
            "path": str(path),
            "reason": "absent",
            "bytes": 0,
            "sha256": None,
        }
    sha, size = digest_file(path)
    return {
        "present": True,
        "path": str(path),
        "reason": "file",
        "bytes": size,
        "sha256": sha,
    }


def retrieve_preservation(candidate: dict, repo: Path = REPO) -> dict:
    """Signal B: retrieve named bytes and hash-match. Never treat exists() as proof."""
    claim = candidate.get("preservation_claim") or {}
    kind = str(claim.get("kind") or "none").lower()
    claimed_sha = str(claim.get("sha256") or "").strip().lower()
    base = {
        "kind": kind,
        "claimed_sha256": claimed_sha or None,
        "retrieved": False,
        "matched": False,
        "location": None,
        "sha256": None,
        "bytes": 0,
        "reason": None,
    }
    if kind in {"", "none", "absent"}:
        base["reason"] = "no-preservation-claim"
        return base
    if kind == "git":
        base["reason"] = "git-named-commit-unavailable-on-this-worktree"
        return base
    if kind != "export":
        base["reason"] = f"unknown-kind:{kind}"
        return base
    rel = str(claim.get("path") or "").strip()
    if not rel:
        base["reason"] = "export-path-missing"
        return base
    path = Path(rel)
    if not path.is_absolute():
        path = repo / rel
    base["location"] = str(path)
    if not path.is_file():
        base["reason"] = "export-absent"
        return base
    sha, size = digest_file(path)
    base["retrieved"] = True
    base["sha256"] = sha
    base["bytes"] = size
    if not claimed_sha:
        base["reason"] = "claim-sha-absent"
        return base
    if sha != claimed_sha:
        base["reason"] = "hash-mismatch"
        return base
    base["matched"] = True
    base["reason"] = "retrieved-hash-matched"
    return base


def rationale_holds(candidate: dict, existence: dict) -> dict:
    rationale = str(candidate.get("retirement_rationale") or "").strip()
    identity = str(candidate.get("identity_status") or "NAMED")
    holds = True
    reason = "rationale-compatible-with-estate"
    if identity == "UNRECOVERABLE":
        holds = False
        reason = "identity-unrecoverable-cannot-re-read-rationale"
    elif "DELETE-ALL" in rationale.upper() and existence.get("present") is True:
        holds = False
        reason = "rationale-said-deleted-but-live-file-present"
    elif not rationale:
        holds = False
        reason = "rationale-empty"
    return {"holds": holds, "reason": reason, "text": rationale}


def adjudicate(candidate: dict, repo: Path = REPO) -> dict:
    exist = existence_check(candidate, repo)
    pres = retrieve_preservation(candidate, repo)
    rationale = rationale_holds(candidate, exist)
    cap = str(candidate.get("capability_given_up") or "").strip()
    survives = str(candidate.get("mechanism_survives_at") or "").strip()
    identity = str(candidate.get("identity_status") or "NAMED")
    cid = str(candidate.get("id") or "")

    if identity == "UNRECOVERABLE":
        verdict = "P1-IDENTITY-UNRECOVERABLE"
    elif pres["retrieved"] and not pres["matched"]:
        verdict = "P1-HASH-MISMATCH"
    elif pres["kind"] == "export" and not pres["retrieved"]:
        verdict = "P1-CLAIM-NOT-RECEIPT"
    elif not exist["present"] and not pres["matched"]:
        verdict = "P1-UNPRESERVED"
    elif exist["present"] and not rationale["holds"]:
        verdict = "REOPEN"
    elif pres["matched"] and (not cap or not survives):
        verdict = "REFUSE-RETIRE-MISSING-SURVIVAL"
    elif pres["matched"] and rationale["holds"] and cap and survives:
        verdict = "RETAIN-RETIRE"
    elif pres["matched"] and not rationale["holds"]:
        verdict = "REOPEN"
    else:
        verdict = "UNKNOWN-NEEDS-PROBE"

    completed = verdict in TERMINAL_VERDICTS
    p1 = verdict in P1_VERDICTS
    return {
        "id": cid,
        "classification_was": candidate.get("classification") or "RETIRE",
        "identity_status": identity,
        "existence": exist,
        "preservation": pres,
        "rationale": rationale,
        "capability_given_up": cap or None,
        "mechanism_survives_at": survives or None,
        "verdict": verdict,
        "completed_retirement": completed,
        "p1": p1,
        "severity": "P1" if p1 else ("info" if completed else "open"),
        "note": (
            "P1 finding, not a completed retirement"
            if p1
            else (
                "RETIRE retained: capability named and preservation receipt hash-matched"
                if completed
                else "not terminal"
            )
        ),
    }


def files_deleted_by_this_unit() -> list:
    """This unit re-adjudicates and reports only."""
    return []
