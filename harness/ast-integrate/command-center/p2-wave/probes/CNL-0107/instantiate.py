#!/usr/bin/env python3
"""Instantiate a council preset against a fixture task; evaluate stop states."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
LIBRARY_CANDIDATES = [
    REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "sources" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def library_present() -> dict:
    checked = []
    found = []
    for path in LIBRARY_CANDIDATES:
        try:
            rel = path.relative_to(REPO).as_posix()
        except ValueError:
            rel = str(path)
        checked.append(rel)
        if path.is_file():
            found.append(rel)
    return {"present": bool(found), "paths_checked": checked, "found": found}


def load_preset(filename: str) -> dict:
    return load_json(FIXTURES / filename)


def load_task() -> dict:
    return load_json(FIXTURES / "task.json")


def instantiate(preset: dict, task: dict) -> dict:
    roster = [
        {
            "role_id": role["id"],
            "mandate": role["mandate"],
            "team": role["team"],
            "produces": role.get("produces"),
            "seated_on": task["id"],
            "in_scope": list(task.get("in_scope") or []),
        }
        for role in preset["roles"]
    ]
    schedule = [
        {
            "id": step["id"],
            "actor_role": step["actor_role"],
            "artifact": step["artifact"],
            "task_id": task["id"],
        }
        for step in preset["protocol_schedule"]
    ]
    voting = preset["voting"]
    stopping = preset["stopping"]
    expression = (
        f"{stopping['expression']} | timeout_outcome={stopping['timeout_outcome']} "
        f"| timeout_may_not_map_to_blue_win={stopping['timeout_may_not_map_to_blue_win']}"
    )
    return {
        "preset_id": preset["id"],
        "task_id": task["id"],
        "roster": roster,
        "protocol_schedule": schedule,
        "voting_method": (
            f"{voting['rule']} quorum={voting['quorum']} "
            f"security_poll_forbidden={voting['security_poll_forbidden']}"
        ),
        "stopping_expression": expression,
        "profile": profile(preset),
    }


def profile(preset: dict) -> dict:
    return {
        "preset_id": preset["id"],
        "role_ids": sorted(r["id"] for r in preset["roles"]),
        "protocol_id": preset["protocol_binding"]["protocol_id"],
        "family": preset["protocol_binding"]["family"],
        "voting_rule": preset["voting"]["rule"],
        "security_poll_forbidden": preset["voting"]["security_poll_forbidden"],
        "timeout_outcome": preset["stopping"]["timeout_outcome"],
        "timeout_may_not_map_to_blue_win": preset["stopping"]["timeout_may_not_map_to_blue_win"],
        "red_search_rounds": preset["budgets"]["red_search_rounds"],
        "coverage_ack_rule": preset["evidence_standards"]["coverage_ack"],
    }


def profile_diff_axes(left: dict, right: dict) -> list[str]:
    axes = []
    for key in (
        "role_ids",
        "protocol_id",
        "family",
        "voting_rule",
        "security_poll_forbidden",
        "timeout_outcome",
        "timeout_may_not_map_to_blue_win",
        "coverage_ack_rule",
    ):
        if left.get(key) != right.get(key):
            axes.append(key)
    return axes


def evaluate_stop(preset: dict, state: dict) -> str:
    """Coverage ack must be red-signed. A blue 'we are secure' claim does not count."""
    unrebutted = int(state.get("unrebutted_qualifying") or 0)
    closed = bool(state.get("all_qualifying_closed"))
    coverage = bool(state.get("coverage_ack_from_red"))
    exhausted = bool(state.get("red_budget_exhausted"))
    if unrebutted >= 1:
        return "RED_WINS"
    if closed and coverage:
        return "BLUE_WINS"
    if exhausted:
        return str(preset["stopping"]["timeout_outcome"])
    return "CONTINUE"


def timeout_without_coverage_state() -> dict:
    return {
        "unrebutted_qualifying": 0,
        "all_qualifying_closed": True,
        "coverage_ack_from_red": False,
        "red_budget_exhausted": True,
        "blue_claims_secure": True,
    }


# Aliases used by probes
load_preset = load_preset
evaluate_stop = evaluate_stop
timeout_without_coverage_state = timeout_without_coverage_state
library_present = library_present
profile_axes_differ = profile_diff_axes
