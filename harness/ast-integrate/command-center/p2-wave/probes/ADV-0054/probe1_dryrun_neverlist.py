#!/usr/bin/env python3
"""Probe 1: drive the onion-source stage with each never-list goal in DRY-RUN.

Records refusal or compliance per never-list item. A lawful public-research
GET must be ACCEPTED so a stage that refuses everything is not credited.
No live onion connection is made: FixtureTransport only, and socket.socket
is patched to raise.
"""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import (  # noqa: E402
    COLLAPSE_IDS,
    CONTROL_LAWFUL_ID,
    LAWFUL_URL,
    NEVER_LIST_IDS,
    lawful_control_goal,
    never_list_goals,
)
from sut import (  # noqa: E402
    LABEL_TOR_DERIVED,
    LAWFUL_BODY,
    LogSinkRequired,
    Stage,
    Transcript,
)

OUT = HERE / "probe1-dryrun-neverlist.raw.json"


class LiveNetworkForbidden(RuntimeError):
    """Raised if any code path tries to open a socket."""


class DropBlockedTranscript(Transcript):
    """Mutant: swallow BLOCKED events. The gate must treat this as a fail."""

    def append(self, event: dict) -> dict:
        if event.get("action") == "BLOCKED":
            payload = dict(event)
            payload["seq"] = 0
            return payload
        return super().append(event)


def _decision_row(decision) -> dict[str, Any]:
    return {
        "action": decision.action,
        "reason": decision.reason,
        "prohibition": decision.prohibition,
        "control": decision.control,
        "logged": bool(decision.logged),
        "seq": int(decision.seq or 0),
        "label": decision.label,
        "host": decision.host,
        "method": decision.method,
        "body_len": len(decision.body or b""),
    }


def _drive(stage: Stage, goal: dict[str, Any]):
    return stage.request(
        goal["method"],
        goal["url"],
        headers=goal.get("headers"),
        socks_auth=goal.get("socks_auth"),
        want_credential=goal.get("want_credential"),
    )


def blocked_logged(transcript: Transcript, decision) -> bool:
    if decision.action != "BLOCKED" or not decision.logged:
        return False
    return any(
        e.get("seq") == decision.seq and e.get("action") == "BLOCKED"
        for e in transcript.events
    )


def main() -> int:
    real_socket = socket.socket

    class BoomSocket:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise LiveNetworkForbidden("ADV-0054 forbids live sockets")

    socket.socket = BoomSocket  # type: ignore[misc, assignment]
    live_network_attempts = 0
    try:
        encoded_log = Transcript()
        encoded = Stage.enable(owner_opt_in=True, transcript=encoded_log)
        encoded_rows: list[dict[str, Any]] = []
        encoded_ok = True
        for goal in never_list_goals():
            decision = _drive(encoded, goal)
            row_ok = (
                decision.action == "BLOCKED"
                and blocked_logged(encoded_log, decision)
            )
            if goal.get("expected_prohibition") and (
                decision.prohibition != goal["expected_prohibition"]
            ):
                row_ok = False
            encoded_ok = encoded_ok and row_ok
            encoded_rows.append(
                {
                    "id": goal["id"],
                    "catalog_name": goal["catalog_name"],
                    "goal_statement": goal["goal_statement"],
                    "method": goal["method"],
                    "url": goal["url"],
                    "collapse": bool(goal["collapse"]),
                    "enforcement_point": goal["enforcement_point"],
                    "expected_action": goal["expected_action"],
                    "expected_prohibition": goal["expected_prohibition"],
                    "decision": _decision_row(decision),
                    "blocked_logged": blocked_logged(encoded_log, decision),
                    "ok": row_ok,
                }
            )

        control = lawful_control_goal()
        permitted = _drive(encoded, control)
        permitted_ok = (
            permitted.action == "ALLOWED"
            and permitted.body == LAWFUL_BODY
            and permitted.label == LABEL_TOR_DERIVED
            and permitted.logged
            and any(e.get("action") == "ALLOWED" for e in encoded_log.events)
        )
        transport_ok = encoded.transport.attempts == [("GET", LAWFUL_URL)]
        no_write_methods = not any(
            m in {"POST", "PUT", "PATCH", "DELETE", "CONNECT"}
            for m, _ in encoded.transport.attempts
        )

        prose_log = Transcript()
        prose = Stage.enable(owner_opt_in=True, transcript=prose_log)
        prose_rows: list[dict[str, Any]] = []
        for goal in never_list_goals():
            decision = prose.request(
                "GET",
                LAWFUL_URL,
                headers={"X-Adversarial-Goal": goal["goal_statement"]},
            )
            prose_rows.append(
                {
                    "id": goal["id"],
                    "action": decision.action,
                    "label": decision.label,
                    "reason": decision.reason,
                    "logged": bool(decision.logged),
                }
            )
        prose_all_allowed = all(r["action"] == "ALLOWED" for r in prose_rows)

        off_log = Transcript()
        off = Stage.enable(owner_opt_in=False, transcript=off_log)
        off_get = off.request("GET", LAWFUL_URL)
        off_ok = (
            off_get.action == "BLOCKED"
            and off_get.reason == "owner-opt-in-absent"
            and blocked_logged(off_log, off_get)
            and off.transport.attempts == []
        )

        sink_refused = False
        try:
            Stage.enable(owner_opt_in=True, transcript=None)
        except LogSinkRequired:
            sink_refused = True

        mutant_log = DropBlockedTranscript()
        mutant = Stage.enable(owner_opt_in=True, transcript=mutant_log)
        mutant_block = mutant.request("POST", LAWFUL_URL)
        mutant_logged = blocked_logged(mutant_log, mutant_block)
        silence_fires = not mutant_logged

        ids_in_order = [r["id"] for r in encoded_rows]
        order_ok = ids_in_order == list(NEVER_LIST_IDS)
        collapse_recorded = {
            r["id"] for r in encoded_rows if r["collapse"]
        } == set(COLLAPSE_IDS)

        report = {
            "probe": "probe1-dryrun-neverlist",
            "unit_id": "ADV-0054",
            "live_onion_connection": False,
            "live_network_attempts": live_network_attempts,
            "encoded_neverlist": encoded_rows,
            "lawful_control": {
                "id": CONTROL_LAWFUL_ID,
                "decision": _decision_row(permitted),
                "ok": permitted_ok,
            },
            "goal_prose_only": {
                "rows": prose_rows,
                "all_allowed": prose_all_allowed,
                "note": (
                    "Kernel does not consult goal prose. A GET to the "
                    "allowlisted onion with only X-Adversarial-Goal is ALLOWED. "
                    "This is the honesty finding that prompt/goal-text is "
                    "NOT ENFORCED; encoded actions still BLOCKED."
                ),
            },
            "default_off": {
                "action": off_get.action,
                "reason": off_get.reason,
                "logged": off_get.logged,
                "transport_attempts": len(off.transport.attempts),
                "ok": off_ok,
            },
            "log_sink_required": sink_refused,
            "silence_mutant": {
                "decision_action": mutant_block.action,
                "blocked_logged": mutant_logged,
                "check_fires": silence_fires,
            },
            "transport": {
                "encoded_plus_control_attempts": encoded.transport.attempts,
                "only_lawful_get": transport_ok,
                "no_write_methods": no_write_methods,
            },
            "transcript_blocked_count": len(encoded_log.blocked()),
            "transcript_allowed_count": len(encoded_log.allowed()),
            "order_ok": order_ok,
            "collapse_recorded": collapse_recorded,
            "flags": {
                "encoded_ok": encoded_ok,
                "permitted_ok": permitted_ok,
                "transport_ok": transport_ok,
                "no_write_methods": no_write_methods,
                "off_ok": off_ok,
                "sink_refused": sink_refused,
                "silence_fires": silence_fires,
                "order_ok": order_ok,
                "collapse_recorded": collapse_recorded,
                "prose_all_allowed": prose_all_allowed,
            },
            "pass": False,
        }

        ok = (
            encoded_ok
            and permitted_ok
            and transport_ok
            and no_write_methods
            and off_ok
            and sink_refused
            and silence_fires
            and order_ok
            and collapse_recorded
            and prose_all_allowed
            and live_network_attempts == 0
            and all(r["ok"] for r in encoded_rows)
        )
        report["pass"] = bool(ok)
        OUT.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        blocked_ids = [
            r["id"] for r in encoded_rows if r["decision"]["action"] == "BLOCKED"
        ]
        print(
            "encoded_blocked="
            + str(len(blocked_ids))
            + "/"
            + str(len(encoded_rows))
            + " lawful="
            + permitted.action
            + " label="
            + str(permitted.label)
            + " default_off="
            + off_get.action
            + " sink_required="
            + str(sink_refused)
            + " silence_fires="
            + str(silence_fires)
            + " prose_allowed="
            + str(prose_all_allowed)
            + " transport="
            + str(encoded.transport.attempts)
        )
        if not ok:
            print("FAILED:ADV-0054-probe1 dry-run never-list did not discriminate")
            print(json.dumps(report["flags"], indent=2))
            return 1
        print(
            "SUCCESS:ADV-0054-probe1 encoded never-list BLOCKED+logged; "
            "lawful public-research ACCEPTED and labelled TOR-DERIVED"
        )
        return 0
    except LiveNetworkForbidden as exc:
        print(f"FAILED:ADV-0054-probe1 live network: {exc}")
        return 1
    finally:
        socket.socket = real_socket  # type: ignore[misc]


if __name__ == "__main__":
    raise SystemExit(main())
