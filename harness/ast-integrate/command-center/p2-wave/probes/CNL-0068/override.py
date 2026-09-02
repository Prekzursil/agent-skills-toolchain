#!/usr/bin/env python3
"""Executable-test override of a council majority (CNL-0068).

A failing load-bearing test bound to the decided claim overturns any
tentative YES, including unanimous YES. A failing test that is not bound
to that claim cannot veto. Voting seats and post-close declarations
cannot make a test load-bearing.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ACCEPTING = frozenset({"YES", "ACCEPT", "APPROVE", "PASS", "TRUE"})
REJECTING = frozenset({"NO", "REJECT", "DENY", "FALSE"})
PERMITTED_BINDER_ROLES = frozenset(
    {"owner", "charter", "protocol-preset", "registrar"}
)
FORBIDDEN_BINDER_ROLES = frozenset(
    {"seat", "majority", "chair-after-close", "tally"}
)

NEGATIVE_CONTROL_VERBATIM = (
    "On the state the check is meant to reject -- a council whose recorded "
    "ballots are unanimous YES for claim C, with a load-bearing test bound to C "
    "that exits non-zero -- adjudicate() must set outcome to REFUTED and must "
    "not emit a binding decision in {YES, ACCEPT, APPROVE, PASS}. The same "
    "check must stay silent (leave a sound YES standing) when the failing test "
    "is bound to a different claim."
)

OVERRIDE_RULE = (
    "If tentative_outcome is YES and any legal load-bearing binding whose "
    "claim_id equals the decided claim has an executable result of FAIL, "
    "recorded outcome is REFUTED (not YES). ERROR on a legal bound test "
    "yields NOT-CHECKED and does not fall back to the tally as a binding YES."
)


def parse_ts(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_fixture(name: str) -> dict[str, Any]:
    path = HERE / "fixtures" / name
    if not path.suffix:
        path = path.with_suffix(".json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fixture {path} is not an object")
    return data


def tally(votes: list[dict[str, Any]]) -> dict[str, Any]:
    yes = no = abstain = 0.0
    ballots: list[str] = []
    for vote in votes:
        weight = float(vote.get("weight", 1.0))
        ballot = str(vote.get("ballot") or "").upper()
        ballots.append(ballot)
        if ballot in ACCEPTING:
            yes += weight
        elif ballot in REJECTING:
            no += weight
        else:
            abstain += weight
    if yes > no:
        tentative = "YES"
    elif no > yes:
        tentative = "NO"
    else:
        tentative = "TIE"
    return {
        "yes_weight": yes,
        "no_weight": no,
        "abstain_weight": abstain,
        "unanimous_yes": yes > 0 and no == 0,
        "tentative_outcome": tentative,
        "ballots": ballots,
    }


def voter_ids(votes: list[dict[str, Any]]) -> set[str]:
    return {str(v.get("seat") or "") for v in votes if v.get("seat")}


def execute_invocation(invocation: dict[str, Any]) -> dict[str, Any]:
    kind = str(invocation.get("kind") or "")
    if kind == "subprocess":
        rel = str(invocation.get("command") or "")
        script = REPO / rel
        if not script.is_file():
            return {
                "status": "ERROR",
                "returncode": 127,
                "stderr": f"missing:{rel}",
            }
        proc = subprocess.run(
            [sys.executable, "-B", str(script)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
        )
        status = "PASS" if proc.returncode == 0 else "FAIL"
        return {
            "status": status,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip()[-500:],
            "stderr": (proc.stderr or "").strip()[-500:],
        }
    if kind == "recorded":
        status = str(invocation.get("status") or "ERROR").upper()
        if status not in {"PASS", "FAIL", "ERROR"}:
            status = "ERROR"
        return {"status": status, "returncode": None, "recorded": True}
    return {"status": "ERROR", "returncode": 126, "stderr": f"unknown-kind:{kind}"}


def classify_binding(
    binding: dict[str, Any],
    *,
    claim_id: str,
    ballot_close: datetime,
    voters: set[str],
) -> dict[str, Any]:
    role = str(binding.get("binder_role") or "")
    binder_id = str(binding.get("binder_id") or "")
    bound_claim = str(binding.get("claim_id") or "")
    reasons: list[str] = []
    if role in FORBIDDEN_BINDER_ROLES or role not in PERMITTED_BINDER_ROLES:
        reasons.append(f"binder-role-forbidden:{role}")
    try:
        declared = parse_ts(str(binding.get("declared_at") or ""))
        if declared >= ballot_close:
            reasons.append("declared-at-or-after-ballot-close")
    except ValueError:
        reasons.append("declared-at-unparseable")
    if role == "registrar" and binder_id in voters:
        reasons.append("registrar-is-voting-seat")
    if binding.get("declared_by_majority") is True:
        reasons.append("majority-cannot-declare-load-bearing")
    legal = not reasons
    applicable = legal and bound_claim == claim_id
    return {
        "test_id": binding.get("test_id"),
        "claim_id": bound_claim,
        "binder_role": role,
        "binder_id": binder_id,
        "legal": legal,
        "applicable": applicable,
        "reject_reasons": reasons,
    }


def adjudicate(state: dict[str, Any]) -> dict[str, Any]:
    claim_id = str(state.get("claim_id") or "")
    votes = list(state.get("votes") or [])
    bindings = list(state.get("bindings") or [])
    counted = tally(votes)
    close = parse_ts(str(state.get("ballot_close") or ""))
    voters = voter_ids(votes)
    classified: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    overriding: list[dict[str, Any]] = []
    irrelevant_failures: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for binding in bindings:
        row = classify_binding(
            binding, claim_id=claim_id, ballot_close=close, voters=voters
        )
        classified.append(row)
        executed = execute_invocation(dict(binding.get("invocation") or {}))
        record = {
            "test_id": row["test_id"],
            "claim_id": row["claim_id"],
            "legal": row["legal"],
            "applicable": row["applicable"],
            **executed,
        }
        results.append(record)
        if not row["legal"]:
            rejected.append({**row, "status": executed.get("status")})
            continue
        if executed.get("status") == "ERROR" and row["applicable"]:
            errors.append(record)
            continue
        if executed.get("status") == "FAIL" and row["applicable"]:
            overriding.append(record)
            continue
        if executed.get("status") == "FAIL" and not row["applicable"]:
            irrelevant_failures.append(record)

    tentative = counted["tentative_outcome"]
    outcome = tentative
    reason = "tally"
    if errors:
        outcome = "NOT-CHECKED"
        reason = "load-bearing-test-error"
    elif overriding and tentative in ACCEPTING:
        outcome = "REFUTED"
        reason = "executable-test-override"
    elif overriding and tentative not in ACCEPTING:
        reason = "tally-already-non-accepting"
    elif irrelevant_failures and not overriding:
        reason = "tally-irrelevant-failures-ignored"

    binding_yes = outcome in ACCEPTING
    return {
        "council_id": state.get("id"),
        "claim_id": claim_id,
        "tally": counted,
        "tentative_outcome": tentative,
        "outcome": outcome,
        "reason": reason,
        "binding_yes": binding_yes,
        "overriding_tests": overriding,
        "irrelevant_failures": irrelevant_failures,
        "rejected_bindings": rejected,
        "errors": errors,
        "test_results": results,
        "classified_bindings": classified,
        "negative_control_verbatim": NEGATIVE_CONTROL_VERBATIM,
    }


def fixture_result(name: str) -> dict[str, Any]:
    return adjudicate(load_fixture(name))


def main() -> int:
    names = sys.argv[1:] or [
        "unanimous_refuted.json",
        "known_good.json",
        "irrelevant_fail.json",
    ]
    for name in names:
        result = fixture_result(name)
        print(json.dumps({"fixture": name, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
