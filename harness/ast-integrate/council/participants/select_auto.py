"""Auto-compose council seats from a task description (IMP-0267)."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

BOILERPLATE_MARKERS = (
    "standard council role seated for expertise",
    "generic specialist",
    "as appropriate",
)

ROLE_CUES: list[tuple[str, tuple[str, ...]]] = [
    (
        "legal",
        (
            "msa",
            "indemnif",
            "liability",
            "gdpr",
            "subpoena",
            "cfaa",
            "export-control",
            "counsel",
            "contract",
            "processor",
            "clause",
        ),
    ),
    (
        "security",
        ("threat-model", "cve", "oauth", "session fixation", "injection", "token storage"),
    ),
    (
        "clinical",
        ("clinical trial", "phase ii", "patient consent", "adverse-event", "protocol"),
    ),
    (
        "finance",
        ("10-k", "revenue-recognition", "sox", "audit committee"),
    ),
    (
        "architect",
        ("kubernetes", "multi-region", "consistent hashing", "failure-domain"),
    ),
    (
        "statistician",
        ("p-value", "multiple-comparison", "a/b experiment", "correction"),
    ),
    ("implementer", ("refactor", "unit tests", "css", "cli", "readme", "logging", "ship", "feature")),
]


def _spans(task: str, cues: Sequence[str]) -> list[str]:
    low = task.lower()
    hits: list[str] = []
    for cue in cues:
        idx = low.find(cue)
        if idx >= 0:
            hits.append(task[idx : idx + len(cue)])
    return hits


def compose(task: str) -> dict[str, Any]:
    seats: list[dict[str, Any]] = []
    seen: set[str] = set()
    for role, cues in ROLE_CUES:
        spans = _spans(task, cues)
        if not spans:
            continue
        if role in seen:
            continue
        seen.add(role)
        quoted = ", ".join(f'"{s}"' for s in spans[:3])
        seats.append(
            {
                "role": role,
                "id": f"auto-{role}",
                "reason": f"{role} seated because the task names {quoted}",
                "task_spans": list(spans),
                "source": "auto",
                "grounding": "task-feature",
            }
        )
    if "implementer" not in seen:
        token = task.split()[0] if task.split() else "task"
        seats.insert(
            0,
            {
                "role": "implementer",
                "id": "auto-implementer",
                "reason": f'implementer seated to carry the work described by "{token}"',
                "task_spans": [token],
                "source": "auto",
                "grounding": "task-feature",
            },
        )
    return {
        "task": task,
        "roles": [s["role"] for s in seats],
        "seats": seats,
        "seat_count": len(seats),
        "owner_overrides": [],
    }


def roles_of(composition: Mapping[str, Any]) -> set[str]:
    roles = composition.get("roles")
    found: set[str] = set()
    if isinstance(roles, (list, tuple, set)):
        found.update(str(r) for r in roles)
    for seat in composition.get("seats") or []:
        if isinstance(seat, Mapping) and seat.get("role"):
            found.add(str(seat["role"]))
        elif isinstance(seat, str):
            found.add(seat)
    return found


def apply_owner_override(
    composition: Mapping[str, Any],
    directives: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    seats = [dict(s) if isinstance(s, Mapping) else s for s in (composition.get("seats") or [])]
    log: list[dict[str, Any]] = []
    for directive in directives:
        action = str(directive.get("action") or "")
        role = str(directive.get("role") or "")
        auto_seat = next((s for s in seats if isinstance(s, Mapping) and s.get("role") == role), None)
        had = auto_seat is not None
        auto_reason = str((auto_seat or {}).get("reason") or "")
        if action == "remove":
            seats = [s for s in seats if not (isinstance(s, Mapping) and s.get("role") == role)]
            result = "removed" if had else "absent"
        elif action == "add":
            if not had:
                seats.append({"role": role, "id": f"owner-{role}", "reason": str(directive.get("owner_reason") or ""), "task_spans": [], "source": "owner"})
            result = "added"
        else:
            result = "ignored"
        log.append(
            {
                "action": action,
                "role": role,
                "result": result,
                "visible": True,
                "auto_had_role": had,
                "auto_reason": auto_reason,
                "owner_reason": directive.get("owner_reason"),
                "applied": True,
            }
        )
    return {
        "task": composition.get("task"),
        "roles": [s["role"] for s in seats if isinstance(s, Mapping)],
        "seats": seats,
        "seat_count": len(seats),
        "owner_overrides": log,
    }


def reason_diversity_report(seats: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reasons = [str(s.get("reason") or "") for s in seats]
    unique = set(reasons)
    dupes = [r for r in unique if reasons.count(r) > 1]
    return {
        "ok": len(unique) == len(reasons) and len(reasons) == len(seats),
        "n_seats": len(seats),
        "n_unique": len(unique),
        "duplicate_reasons": dupes,
    }


def grounding_report(task: str, seats: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    ok = True
    low = task.lower()
    for seat in seats:
        spans = [str(s) for s in (seat.get("task_spans") or [])]
        reason = str(seat.get("reason") or "")
        grounded = bool(spans) and all(s.lower() in low for s in spans)
        boilerplate = any(m in reason.lower() for m in BOILERPLATE_MARKERS)
        if not grounded or boilerplate or not spans:
            ok = False
        rows.append({"role": seat.get("role"), "grounded": grounded and not boilerplate, "spans": spans})
    return {"ok": ok, "rows": rows}


def legal_false_positive_report(tasks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    fired: list[str] = []
    n = 0
    for item in tasks:
        n += 1
        if "legal" in roles_of(compose(str(item.get("task") or ""))):
            fired.append(str(item.get("id") or ""))
    return {"n": n, "fires": len(fired), "rate": (len(fired) / n) if n else 0.0, "fired_ids": fired, "ok": len(fired) == 0}
