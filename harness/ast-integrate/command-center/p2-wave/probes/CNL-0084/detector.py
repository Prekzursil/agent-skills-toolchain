"""CNL-0084 deadlock detector.

A council is DEADLOCKED only when two mechanically different signals agree:

1. Ledger freeze: the deliberation fingerprint (claim ids, evidence hashes,
   vote tally, dissent briefs, open questions) is identical across the last
   `stuck_windows` observation windows.
2. Wait-for cycle: the seat await-graph on the latest window contains a cycle.

Wall-clock elapsed time is recorded and is NOT a predicate. Slow-but-progressing
runs keep changing the fingerprint. A hung seat that never returns is
STALLED_RUNTIME, not deadlock. Frozen ledger without a wait-for cycle is
FROZEN_WITHOUT_CYCLE (circular debate; CNL-0090), not this detector.

Escalation is a strictly ordered ladder: recruit -> replace -> reframe ->
escalate_to_owner. Recruit may be recorded inapplicable (full roster and
dissent already present) and then replace is the first applied rung.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
RUNGS = ("recruit", "replace", "reframe", "escalate_to_owner")


def load_run(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def ledger_fingerprint(window: dict[str, Any]) -> tuple:
    votes = window.get("vote_tally") or {}
    return (
        tuple(sorted(str(x) for x in (window.get("claim_ids") or []))),
        tuple(sorted(str(x) for x in (window.get("evidence_hashes") or []))),
        tuple(sorted((str(k), str(v)) for k, v in votes.items())),
        tuple(sorted(str(x) for x in (window.get("dissent_brief_ids") or []))),
        tuple(sorted(str(x) for x in (window.get("open_questions") or []))),
    )


def fingerprint_hex(fp: tuple) -> str:
    return hashlib.sha256(repr(fp).encode("utf-8")).hexdigest()[:16]


def wait_for_cycle(awaiting: dict[str, Any] | None) -> list[str] | None:
    graph: dict[str, list[str]] = {
        str(k): [str(x) for x in (v or [])]
        for k, v in (awaiting or {}).items()
    }
    visiting: set[str] = set()
    done: set[str] = set()
    stack: list[str] = []

    def dfs(node: str) -> list[str] | None:
        if node in visiting:
            if node in stack:
                i = stack.index(node)
                return stack[i:] + [node]
            return [node]
        if node in done:
            return None
        visiting.add(node)
        stack.append(node)
        for nxt in graph.get(node, []):
            found = dfs(nxt)
            if found:
                return found
        stack.pop()
        visiting.remove(node)
        done.add(node)
        return None

    for name in graph:
        found = dfs(name)
        if found:
            return found
    return None


def classify(run: dict[str, Any]) -> dict[str, Any]:
    windows = list(run.get("windows") or [])
    stuck_n = int(run.get("stuck_windows") or 2)
    min_turns = int(run.get("min_turns") or 2)
    if not windows:
        return {
            "label": "INSUFFICIENT_OBSERVATION",
            "deadlocked": False,
            "fired": False,
            "silent": True,
            "frozen": False,
            "cycle": None,
            "missing_seats": [],
            "turns": 0,
            "stopping_satisfied": False,
            "wall_ms": None,
            "fingerprint_hexes": [],
            "reason": "no-windows",
        }
    last = windows[-1]
    expected = set(str(x) for x in (last.get("seats_expected") or []))
    returned_ever: set[str] = set()
    for window in windows:
        returned_ever |= set(str(x) for x in (window.get("seats_returned") or []))
    missing = sorted(expected - returned_ever)
    fps = [ledger_fingerprint(w) for w in windows]
    hexes = [fingerprint_hex(fp) for fp in fps]
    frozen = len(windows) >= stuck_n and len(set(fps[-stuck_n:])) == 1
    cycle = wait_for_cycle(last.get("awaiting") or {})
    turns = int(last.get("turns_emitted") or 0)
    stopping = bool(last.get("stopping_satisfied"))
    wall_ms = last.get("wall_ms")

    if stopping:
        label, reason = "STOPPED", "stopping-expression-already-true"
    elif missing:
        label, reason = "STALLED_RUNTIME", "expected-seat-never-returned"
    elif len(windows) < stuck_n or turns < min_turns:
        label, reason = "INSUFFICIENT_OBSERVATION", "below-stuck-window-or-turn-floor"
    elif frozen and cycle:
        label, reason = "DEADLOCKED", "frozen-ledger-and-wait-for-cycle"
    elif not frozen:
        label, reason = "PROGRESSING", "ledger-fingerprint-changed"
    else:
        label, reason = "FROZEN_WITHOUT_CYCLE", "defer-to-CNL-0090-circular-debate"

    deadlocked = label == "DEADLOCKED"
    return {
        "label": label,
        "deadlocked": deadlocked,
        "fired": deadlocked,
        "silent": not deadlocked,
        "frozen": frozen,
        "cycle": cycle,
        "missing_seats": missing,
        "turns": turns,
        "stopping_satisfied": stopping,
        "wall_ms": wall_ms,
        "fingerprint_hexes": hexes,
        "reason": reason,
        "fixture_id": run.get("id"),
    }


def owner_packet(run: dict[str, Any], last: dict[str, Any]) -> dict[str, str]:
    qs = last.get("open_questions") or ["unnamed-proposition"]
    return {
        "question": (
            "May this council stop, with the deadlocked proposition named, "
            "using the recorded recommendation?"
        ),
        "deadlocked_proposition": str(qs[0]),
        "recommendation": (
            "Declare the proposition UNRESOLVED; keep the ledger; do not "
            "spend remaining deliberation budget."
        ),
        "default_if_silent": "UNRESOLVED-AND-FREEZE",
    }


def vacant_roles(run: dict[str, Any], last: dict[str, Any]) -> list[str]:
    required = [str(x) for x in (run.get("required_roles") or [])]
    present = set(str(x) for x in (last.get("roles_present") or []))
    return [r for r in required if r not in present]


def dissent_present(last: dict[str, Any]) -> bool:
    votes = last.get("vote_tally") or {}
    if not votes:
        return False
    return len(set(str(v) for v in votes.values())) >= 2


def next_rung(run: dict[str, Any], verdict: dict[str, Any] | None = None) -> dict[str, Any]:
    verdict = verdict if verdict is not None else classify(run)
    if not verdict.get("deadlocked"):
        return {
            "rung": None,
            "reason": "not-deadlocked",
            "label": verdict.get("label"),
        }
    applied = [str(x) for x in (run.get("rungs_already_applied") or [])]
    last = (run.get("windows") or [{}])[-1]
    vacant = vacant_roles(run, last)
    dissent = dissent_present(last)

    if "escalate_to_owner" in applied:
        return {"rung": None, "reason": "owner-already-asked"}
    if "reframe" in applied:
        return {
            "rung": "escalate_to_owner",
            "trigger": "deadlock-persists-after-reframe",
            "owner_packet": owner_packet(run, last),
        }
    if "replace" in applied:
        return {
            "rung": "reframe",
            "trigger": "deadlock-persists-after-replace-same-proposition",
            "open_questions": list(last.get("open_questions") or []),
        }
    if "recruit" in applied:
        return {
            "rung": "replace",
            "trigger": "deadlock-persists-after-recruit-same-cycle-seats",
            "cycle_seats": verdict.get("cycle"),
        }
    if vacant or not dissent:
        return {
            "rung": "recruit",
            "trigger": "deadlock-with-vacant-role-or-no-dissent",
            "vacant_roles": vacant,
            "dissent_present": dissent,
        }
    return {
        "rung": "replace",
        "trigger": "deadlock-full-roster-recruit-inapplicable",
        "cycle_seats": verdict.get("cycle"),
        "recruit_inapplicable": True,
    }


def classify_path(path: Path | str) -> dict[str, Any]:
    run = load_run(path)
    verdict = classify(run)
    rung = next_rung(run, verdict)
    verdict["next_rung"] = rung
    verdict["path"] = str(Path(path).as_posix())
    return verdict


def all_fixture_paths() -> list[Path]:
    return sorted(FIXTURES.glob("*.json"))
