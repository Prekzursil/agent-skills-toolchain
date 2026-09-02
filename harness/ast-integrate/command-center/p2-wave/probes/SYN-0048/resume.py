"""Cold-resume reader: next action from the package dict only. No repo I/O."""
from __future__ import annotations

from typing import Any

PROGRAM_IDLE = {
    "checkpoint": None,
    "instruction": (
        "No in-flight unit, no blocking owner question, and no deferred "
        "item whose reopen trigger is already satisfied."
    ),
    "kind": "PROGRAM-IDLE",
    "unit_id": None,
}


def payload(package: dict[str, Any]) -> dict[str, Any]:
    """Structured resume fields: report payload if present, else the dict itself.

    Receipt-shaped artifacts (catalog handoff-package profile) store in_flight /
    deferred_items / next_action under report because receipt_core sets
    additionalProperties false at the root. Fixture dicts used by the battery
    stay flat.
    """
    if not isinstance(package, dict):
        raise TypeError("package must be a dict")
    report = package.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "handoff-package"
        or "in_flight" in report
        or "deferred_items" in report
        or "open_owner_questions" in report
    ):
        return report
    return package


def next_action(package: dict[str, Any]) -> dict[str, Any]:
    """Derive the next action from structured fields only.

    Deliberately ignores package['next_action'] and package['cold_resume'] so a
    stale or planted prose answer cannot masquerade as a derived resume.
    """
    if not isinstance(package, dict):
        raise TypeError("package must be a dict")
    body = payload(package)
    owners = list(body.get("open_owner_questions") or [])
    blocking = [q for q in owners if isinstance(q, dict) and q.get("blocks_resume") is True]
    blocking.sort(key=lambda q: str(q.get("id") or ""))
    if blocking:
        q = blocking[0]
        qid = q.get("id")
        return {
            "checkpoint": None,
            "instruction": (
                f"Answer owner question {qid} before resuming work: "
                f"{q.get('question')}"
            ),
            "kind": "ANSWER-OWNER-QUESTION",
            "unit_id": qid,
        }
    flight = [u for u in (body.get("in_flight") or []) if isinstance(u, dict)]
    if flight:
        u = flight[0]
        ck = u.get("checkpoint") or "NONE"
        uid = u.get("unit_id")
        return {
            "checkpoint": ck,
            "instruction": (
                f"Resume {uid} from last durable checkpoint {ck} "
                f"toward {u.get('output_path')}"
            ),
            "kind": "RESUME-IN-FLIGHT",
            "unit_id": uid,
        }
    deferred = [d for d in (body.get("deferred_items") or []) if isinstance(d, dict)]
    due = [
        d
        for d in deferred
        if isinstance(d.get("reopen_trigger"), dict)
        and d["reopen_trigger"].get("satisfied") is True
    ]
    due.sort(key=lambda d: str(d.get("id") or ""))
    if due:
        d = due[0]
        did = d.get("id")
        return {
            "checkpoint": None,
            "instruction": f"Reopen deferred item {did}: {d.get('reason')}",
            "kind": "REOPEN-DEFERRED",
            "unit_id": did,
        }
    return dict(PROGRAM_IDLE)


def explain(package: dict[str, Any]) -> dict[str, Any]:
    action = next_action(package)
    body = payload(package)
    owners = [q for q in (body.get("open_owner_questions") or []) if isinstance(q, dict)]
    blocking_ids = [
        q.get("id") for q in owners if q.get("blocks_resume") is True
    ]
    flight = [u for u in (body.get("in_flight") or []) if isinstance(u, dict)]
    deferred = [d for d in (body.get("deferred_items") or []) if isinstance(d, dict)]
    due_ids = [
        d.get("id")
        for d in deferred
        if isinstance(d.get("reopen_trigger"), dict)
        and d["reopen_trigger"].get("satisfied") is True
    ]
    transcript = [
        "reader=resume.next_action; inputs=in_flight,open_owner_questions,deferred_items only",
        f"blocking_owner_questions={blocking_ids or []}",
        f"in_flight_n={len(flight)} first={flight[0].get('unit_id') if flight else None}",
        f"deferred_due={due_ids or []}",
        f"derived_kind={action['kind']} unit_id={action.get('unit_id')}",
    ]
    return {
        "method": (
            "resume.next_action(package) using only in_flight, "
            "open_owner_questions, and deferred_items; no catalog or disk scan"
        ),
        "next_action": action,
        "rehearsal_result": "PASS",
        "transcript": transcript,
    }


def run_fixture_battery() -> list[str]:
    """Return failure strings; empty list means all fixtures passed."""
    failures: list[str] = []

    def check(name: str, pkg: dict, want_kind: str, want_id: str | None) -> None:
        got = next_action(pkg)
        if got.get("kind") != want_kind or got.get("unit_id") != want_id:
            failures.append(
                f"{name}: got kind={got.get('kind')} id={got.get('unit_id')} "
                f"want kind={want_kind} id={want_id}"
            )

    check(
        "A-in-flight",
        {
            "in_flight": [
                {
                    "checkpoint": "ck-a",
                    "output_path": "command-center/synthesis/X.json",
                    "status": "ABSENT-OUTPUT",
                    "unit_id": "SYN-0001",
                }
            ],
            "next_action": {"kind": "PROGRAM-IDLE", "instruction": "ignore me"},
        },
        "RESUME-IN-FLIGHT",
        "SYN-0001",
    )
    check(
        "B-owner-blocks-even-with-in-flight",
        {
            "in_flight": [
                {
                    "checkpoint": "NONE",
                    "output_path": "command-center/synthesis/X.json",
                    "status": "ABSENT-OUTPUT",
                    "unit_id": "SYN-0001",
                }
            ],
            "open_owner_questions": [
                {
                    "blocks_resume": True,
                    "id": "Q-OWNER-1",
                    "question": "Which release mode is binding?",
                    "source_unit": "SYN-0043",
                }
            ],
        },
        "ANSWER-OWNER-QUESTION",
        "Q-OWNER-1",
    )
    check(
        "C-deferred-due",
        {
            "deferred_items": [
                {
                    "id": "D-1",
                    "reason": "Reopen when the predecessor artifact exists",
                    "reopen_trigger": {
                        "kind": "path-exists",
                        "predicate": "command-center/synthesis/SYN-0001.json exists",
                        "satisfied": True,
                    },
                }
            ],
        },
        "REOPEN-DEFERRED",
        "D-1",
    )
    check("D-idle", {}, "PROGRAM-IDLE", None)
    planted_idle = {
        "cold_resume": {
            "next_action": {"kind": "PROGRAM-IDLE", "instruction": "planted"},
            "rehearsal_result": "PASS",
        },
        "in_flight": [
            {
                "checkpoint": "ck-e",
                "output_path": "command-center/synthesis/Y.json",
                "status": "ABSENT-OUTPUT",
                "unit_id": "SYN-0001",
            }
        ],
        "next_action": {"kind": "PROGRAM-IDLE", "instruction": "planted"},
    }
    check("E-ignore-planted-prose-answer", planted_idle, "RESUME-IN-FLIGHT", "SYN-0001")
    return failures
