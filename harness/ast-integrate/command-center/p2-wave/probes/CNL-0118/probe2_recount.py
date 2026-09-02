#!/usr/bin/env python3
"""Probe 2: independent recount from fixtures + event kinds.

Mechanism B: role-matrix tabulation over script.turns (no runtime summary
booleans) compared to counts of TURN/BALLOT_COMMITTED/TERMINAL events.
A disagreement in any number blocks. Also jsonschema-validates the artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import load_json, run  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0118-role-enforcement-and-participant-replacement-simulation.md"
)
SCHEMA = REPO / "command-center/schema/council-simulation-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0118/probe1_replay.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0118/probe2_recount.py"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0118-probe2 {msg}")
    return 1


def fixture_verdict(role: dict, action: str) -> str:
    """Recount from role fields. Does not call harness.evaluate_action."""
    if action in (role.get("forbidden") or []):
        return "REJECT"
    if action == "VOTE" and not role.get("may_vote", False):
        return "REJECT"
    if action == "VETO" and not role.get("may_veto", False):
        return "REJECT"
    allowed = set(role.get("permissions") or [])
    allowed |= set(role.get("rights") or [])
    allowed |= set(role.get("obligations") or [])
    if role.get("may_vote"):
        allowed.update({"VOTE", "ABSTAIN"})
    if role.get("may_veto"):
        allowed.add("VETO")
    return "ALLOW" if action in allowed else "REJECT"


def expected_from_fixtures(roles: dict, script: dict) -> dict:
    seats = {s["seat_id"]: s for s in script["seats"]}
    by_seat: dict[str, list[str]] = {}
    for turn in script["turns"]:
        sid = turn["seat_id"]
        role = roles[seats[sid]["role"]]
        by_seat.setdefault(sid, []).append(fixture_verdict(role, turn["action"]))
    vote_order = list(script["vote_round"]["order"])
    dying = next(s["seat_id"] for s in script["seats"] if s.get("die_mid_vote"))
    expected_voters = [s for s in vote_order if s != dying]
    expected_voters.append(script["replacement"]["seat_id"])
    return {
        "carol_rejects": sum(1 for v in by_seat.get("carol", []) if v == "REJECT"),
        "bob_rejects": sum(1 for v in by_seat.get("bob", []) if v == "REJECT"),
        "erin_rejects": sum(1 for v in by_seat.get("erin", []) if v == "REJECT"),
        "expected_ballot_seats": expected_voters,
        "dying": dying,
        "replacement": script["replacement"]["seat_id"],
        "dying_intended": seats[dying].get("intended_ballot"),
        "replacement_ballot": script["replacement"]["ballot"],
        "timeout_ticks": int(script["declared_timeout_ticks"]),
    }


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("schema errors:")
        for e in errs[:12]:
            print(" ", list(e.path), e.message)
        return fail("artifact fails schema")
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            return fail(f"schema accepted garbage {list(garbage)[:2]}")

    roles = load_json("roles.json")
    script = load_json("script.json")
    exp = expected_from_fixtures(roles, script)
    if exp["carol_rejects"] < 2:
        return fail("fixture matrix does not predict carol violations")
    if exp["bob_rejects"] != 0 or exp["erin_rejects"] != 0:
        return fail("fixture matrix flags compliant/mention")
    if exp["replacement_ballot"] == exp["dying_intended"]:
        return fail("fixture cannot detect inheritance (ballots equal)")

    live = run(enforce=True)
    turns = [e for e in live["events"] if e["kind"] == "TURN"]
    ballots = [e for e in live["events"] if e["kind"] == "BALLOT_COMMITTED"]
    dead = [e for e in live["events"] if e["kind"] == "SEAT_DEAD"]
    swapped = [e for e in live["events"] if e["kind"] == "SEAT_REPLACED"]
    terminals = [e for e in live["events"] if e["kind"] == "TERMINAL"]

    carol_live = sum(
        1 for e in turns if e["seat_id"] == "carol" and e["verdict"] == "REJECT"
    )
    bob_live = sum(
        1 for e in turns if e["seat_id"] == "bob" and e["verdict"] == "REJECT"
    )
    erin_live = sum(
        1 for e in turns if e["seat_id"] == "erin" and e["verdict"] == "REJECT"
    )
    if carol_live != exp["carol_rejects"]:
        return fail(f"carol recount {carol_live} vs fixture {exp['carol_rejects']}")
    if bob_live != exp["bob_rejects"]:
        return fail(f"bob recount {bob_live} vs fixture {exp['bob_rejects']}")
    if erin_live != exp["erin_rejects"]:
        return fail(f"erin recount {erin_live} vs fixture {exp['erin_rejects']}")

    ballot_seats = [e["seat_id"] for e in ballots]
    if sorted(ballot_seats) != sorted(exp["expected_ballot_seats"]):
        return fail(f"ballot seats {ballot_seats} vs {exp['expected_ballot_seats']}")
    if exp["dying"] in ballot_seats:
        return fail("dying seat present in BALLOT_COMMITTED")
    frank_rows = [e for e in ballots if e["seat_id"] == exp["replacement"]]
    if len(frank_rows) != 1:
        return fail(f"replacement ballot rows {len(frank_rows)}")
    if frank_rows[0]["ballot"] == exp["dying_intended"]:
        return fail("replacement ballot equals predecessor intended")
    if frank_rows[0].get("inherited") is True:
        return fail("inherited flag set")
    if len(dead) != 1 or dead[0]["seat_id"] != exp["dying"]:
        return fail(f"SEAT_DEAD {dead}")
    if not swapped or swapped[0].get("inherited_ballot") is True:
        return fail(f"SEAT_REPLACED {swapped}")
    if not terminals or terminals[-1]["terminal_state"] != "COMPLETED_AFTER_REPLACEMENT":
        return fail(f"TERMINAL {terminals}")
    ticks = terminals[-1].get("tick")
    if ticks is None or ticks > exp["timeout_ticks"]:
        return fail(f"ticks {ticks} vs timeout {exp['timeout_ticks']}")

    mr = doc.get("measured_results") or {}
    checks = {
        "violator_rejection_count": carol_live,
        "compliant_rejection_count": bob_live,
        "mention_rejection_count": erin_live,
        "ballots_committed": len(ballots),
        "dying_seat_ballot_present": False,
        "replacement_inherited_predecessor_ballot": False,
        "terminal_state": "COMPLETED_AFTER_REPLACEMENT",
        "violator_caught": True,
        "compliant_flagged": False,
        "mention_flagged": False,
        "within_declared_timeout": True,
        "hung": False,
        "two_run_events_byte_identical": True,
    }
    if mr.get("ticks") != ticks:
        return fail(f"artifact ticks={mr.get('ticks')} recount={ticks}")
    for key, want in checks.items():
        got = mr.get(key)
        if got != want:
            return fail(f"artifact {key}={got} recount={want}")

    named = {t["id"]: t for t in doc.get("tests") or [] if isinstance(t, dict)}
    for tid, cmd in (("probe1-replay", P1), ("probe2-recount", P2)):
        row = named.get(tid) or {}
        if row.get("command") != cmd:
            return fail(f"tests[{tid}].command mismatch")
        if row.get("result") != "PASS":
            return fail(f"tests[{tid}].result {row.get('result')}")

    print(
        json.dumps(
            {
                "probe": "probe2-recount",
                "unit_id": "CNL-0118",
                "carol_rejects_fixture": exp["carol_rejects"],
                "carol_rejects_events": carol_live,
                "bob_rejects_events": bob_live,
                "erin_rejects_events": erin_live,
                "ballot_seats": ballot_seats,
                "ticks": ticks,
                "timeout_ticks": exp["timeout_ticks"],
                "schema_ok": True,
                "garbage_rejected": 3,
                "artifact_agrees": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:CNL-0118-probe2 independent recount agrees "
        f"carol_rejects={carol_live} ballots={len(ballots)} ticks={ticks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
