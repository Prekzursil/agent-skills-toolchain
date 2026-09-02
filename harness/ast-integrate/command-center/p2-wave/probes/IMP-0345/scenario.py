#!/usr/bin/env python3
"""IMP-0345 fixtures: mixed roster, hand-computed tallies, unit paths.

Hand computation (exclude abstention from denominator):

  H1 human  APPROVE (in window)
  H2 human  ABSTAIN (explicit)
  H3 human  silence → proxy REJECT (marked)
  H4 human  REJECT (in window)
  A1 agent  APPROVE (sync, not window-bound)

  WITH proxy:    A=2 R=2 abstain=1 denom=4 winner=TIE
  WITHOUT proxy: A=2 R=1 abstain=2 denom=3 winner=APPROVE
  Outcome flips. Unmarked silence would have been the WITHOUT column.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from council.participants.human import (
    ABSTAIN,
    APPROVE,
    KIND_AGENT,
    KIND_HUMAN,
    POLICY_EXCLUDE_ABSTENTION,
    PROXY_ORIGIN_MARKER,
    REJECT,
    DeterministicClock,
    HybridCouncil,
    HumanOnlyViolation,
    Seat,
    WindowError,
    classify_kind,
    scan_proxy_markers,
    strip_proxy_markers,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HUMAN_SRC = REPO / "tools" / "council" / "participants" / "human.py"

EXPECTED_WITH = {
    "approve": 2,
    "reject": 2,
    "abstain": 1,
    "denominator": 4,
    "winner": "TIE",
}
EXPECTED_WITHOUT = {
    "approve": 2,
    "reject": 1,
    "abstain": 2,
    "denominator": 3,
    "winner": APPROVE,
}


def mixed_seats() -> list[Seat]:
    return [
        Seat("H1", KIND_HUMAN, "human-one", proxy_choice=REJECT),
        Seat("H2", KIND_HUMAN, "human-two", proxy_choice=REJECT),
        Seat("H3", KIND_HUMAN, "human-three", proxy_choice=REJECT),
        Seat("H4", KIND_HUMAN, "human-four", proxy_choice=APPROVE),
        Seat("A1", KIND_AGENT, "agent-one", proxy_choice=REJECT),
    ]


def play_mixed(clock: DeterministicClock | None = None) -> HybridCouncil:
    clock = clock or DeterministicClock(0.0)
    council = HybridCouncil(
        seats=mixed_seats(),
        window_seconds=100.0,
        reminder_offset=60.0,
        human_only=False,
        abstention_policy_id=POLICY_EXCLUDE_ABSTENTION,
        motion="ship-the-widget",
        clock=clock,
    )
    council.open_round()
    # Agent may vote immediately — not bound by the human async window.
    council.submit("A1", APPROVE)
    clock.advance(10.0)
    council.submit("H1", APPROVE)
    council.submit("H2", ABSTAIN)
    council.submit("H4", REJECT)
    # H3 remains silent. Reminder at t=60, timeout at t=100.
    clock.advance(50.0)  # t=60
    council.tick()
    clock.advance(40.0)  # t=100
    council.close_round()
    return council


def tally_slice(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "approve": t["approve"],
        "reject": t["reject"],
        "abstain": t["abstain"],
        "denominator": t["denominator"],
        "winner": t["winner"],
    }


def evaluate_mixed() -> dict[str, Any]:
    council = play_mixed()
    art = council.artifact()
    with_p = tally_slice(art["tally_with_proxy"])
    without_p = tally_slice(art["tally_without_proxy"])
    scan = art["proxy_marker_scan"]
    h3 = next(t for t in art["turns"] if t["seat_id"] == "H3")
    reminded_ids = [r["seat_id"] for r in art["reminders"]]
    ok = (
        with_p == EXPECTED_WITH
        and without_p == EXPECTED_WITHOUT
        and art["outcome_shifted"] is True
        and scan["all_marked"] is True
        and scan["proxied_count"] == 1
        and h3["origin"] == "proxy"
        and h3["proxy_origin_marker"] == PROXY_ORIGIN_MARKER
        and h3["choice"] == REJECT
        and h3["reason"] == "timeout-to-proxy"
        and reminded_ids == ["H3"]
        and art["abstention_policy_id"] == POLICY_EXCLUDE_ABSTENTION
    )
    return {
        "pass": ok,
        "with_proxy": with_p,
        "without_proxy": without_p,
        "expected_with": EXPECTED_WITH,
        "expected_without": EXPECTED_WITHOUT,
        "outcome_shifted": art["outcome_shifted"],
        "scan": scan,
        "h3": h3,
        "reminded_ids": reminded_ids,
        "artifact": art,
    }


def evaluate_unit_paths() -> dict[str, Any]:
    """Async window, reminder, timeout, proxy, human-only, late-submit."""
    rows: list[dict[str, Any]] = []

    # 1. Submit before open.
    c = HybridCouncil(seats=mixed_seats(), clock=DeterministicClock(0.0))
    before_open = False
    try:
        c.submit("H1", APPROVE)
    except WindowError as exc:
        before_open = "round-not-open" in str(exc)
    rows.append({"id": "submit-before-open", "pass": before_open})

    # 2. Human submit after close is refused; agent already voted inside window.
    clock = DeterministicClock(0.0)
    c = HybridCouncil(seats=mixed_seats(), clock=clock)
    c.open_round()
    c.submit("A1", APPROVE)
    c.submit("H1", APPROVE)
    c.submit("H2", ABSTAIN)
    c.submit("H4", REJECT)
    clock.advance(100.0)
    c.tick()
    late = False
    try:
        c.submit("H3", APPROVE)
    except WindowError as exc:
        late = "human-window-closed" in str(exc) or "already-submitted" in str(
            exc
        )
    # H3 was proxied by tick, so already-submitted is also a correct refuse.
    rows.append({"id": "human-submit-after-close", "pass": late})

    # 3. Reminder fires once for the silent human only.
    mixed = evaluate_mixed()
    reminder_ok = mixed["reminded_ids"] == ["H3"]
    rows.append({"id": "reminder-silent-human-only", "pass": reminder_ok})

    # 4. Timeout path is proxy with marker, not unmarked abstention.
    h3 = mixed["h3"]
    timeout_ok = (
        h3["proxied"] is True
        and h3["origin"] == "proxy"
        and h3["proxy_origin_marker"] == PROXY_ORIGIN_MARKER
        and h3["choice"] == REJECT
        and classify_kind(h3) == "proxy"
    )
    rows.append({"id": "timeout-to-proxy-marked", "pass": timeout_ok})

    # 5. Agent vote during the human window is accepted (not async-bound).
    clock = DeterministicClock(0.0)
    c = HybridCouncil(seats=mixed_seats(), clock=clock)
    c.open_round()
    rec = c.submit("A1", REJECT)
    agent_ok = rec.origin == "agent" and rec.choice == REJECT
    rows.append({"id": "agent-sync-during-human-window", "pass": agent_ok})

    # 6. Human-only mode refuses an agent seat.
    refused = False
    try:
        HybridCouncil(seats=mixed_seats(), human_only=True)
    except HumanOnlyViolation:
        refused = True
    humans = [
        Seat("H1", KIND_HUMAN, proxy_choice=APPROVE),
        Seat("H2", KIND_HUMAN, proxy_choice=REJECT),
    ]
    clock = DeterministicClock(0.0)
    only = HybridCouncil(seats=humans, human_only=True, clock=clock)
    only.open_round()
    only.submit("H1", APPROVE)
    clock.advance(100.0)
    art = only.close_round()
    h2 = next(t for t in art["turns"] if t["seat_id"] == "H2")
    human_only_ok = (
        refused
        and only.human_only is True
        and h2["origin"] == "proxy"
        and h2["proxy_origin_marker"] == PROXY_ORIGIN_MARKER
    )
    rows.append({"id": "human-only-refuses-agent-still-proxies", "pass": human_only_ok})

    # 7. Double-submit refused.
    clock = DeterministicClock(0.0)
    c = HybridCouncil(seats=mixed_seats(), clock=clock)
    c.open_round()
    c.submit("H1", APPROVE)
    dup = False
    try:
        c.submit("H1", REJECT)
    except WindowError as exc:
        dup = "already-submitted" in str(exc)
    rows.append({"id": "double-submit-refused", "pass": dup})

    return {
        "pass": all(r["pass"] for r in rows),
        "rows": rows,
        "failed": [r["id"] for r in rows if not r["pass"]],
    }


def evaluate_negative_control() -> dict[str, Any]:
    """Strip the marker: timeout silence classifies as abstention (both-states)."""
    mixed = evaluate_mixed()
    turns = mixed["artifact"]["turns"]
    h2 = next(t for t in turns if t["seat_id"] == "H2")
    h3 = next(t for t in turns if t["seat_id"] == "H3")
    good_scan = scan_proxy_markers(mixed["artifact"])
    good_kinds = {
        "H2": classify_kind(h2),
        "H3": classify_kind(h3),
    }

    stripped = strip_proxy_markers(turns)
    stripped_art = {"turns": stripped}
    bad_scan = scan_proxy_markers(stripped_art)
    h2s = next(t for t in stripped if t["seat_id"] == "H2")
    h3s = next(t for t in stripped if t["seat_id"] == "H3")
    bad_kinds = {
        "H2": classify_kind(h2s),
        "H3": classify_kind(h3s),
    }
    indistinguishable = bad_kinds["H2"] == "abstention" and bad_kinds["H3"] == "abstention"
    both_states = (
        good_scan["all_marked"] is True
        and good_kinds["H3"] == "proxy"
        and good_kinds["H2"] == "abstention"
        and bad_scan["all_marked"] is False
        and bad_scan["missing_marker_count"] >= 1
        and indistinguishable
    )
    return {
        "pass": both_states,
        "good_scan": good_scan,
        "bad_scan": bad_scan,
        "good_kinds": good_kinds,
        "bad_kinds": bad_kinds,
        "indistinguishable_after_strip": indistinguishable,
        "fired_on_bad_state": bad_scan["all_marked"] is False,
        "silent_on_good_state": good_scan["all_marked"] is True,
    }


def timeout_path_assigns_marker(source: str | None = None) -> dict[str, Any]:
    """Reviewer check: _apply_timeout_proxy assigns PROXY_ORIGIN_MARKER."""
    src = source if source is not None else HUMAN_SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    assigned = False
    method_found = False
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "HybridCouncil":
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            if item.name != "_apply_timeout_proxy":
                continue
            method_found = True
            for sub in ast.walk(item):
                if isinstance(sub, ast.keyword) and sub.arg == "proxy_origin_marker":
                    val = sub.value
                    if isinstance(val, ast.Name) and val.id == "PROXY_ORIGIN_MARKER":
                        assigned = True
                if isinstance(sub, ast.Constant) and sub.value == PROXY_ORIGIN_MARKER:
                    assigned = True
    return {
        "method_found": method_found,
        "assigns_marker": assigned,
        "pass": method_found and assigned,
        "path": str(HUMAN_SRC.relative_to(REPO).as_posix()),
    }
