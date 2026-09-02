#!/usr/bin/env python3
"""Probe 1: both-states control on the dry-run onion stage.

A prohibited method is BLOCKED and logged. A permitted public GET
succeeds and is labelled TOR-DERIVED. A stage that swallows BLOCKED
log events fails this gate. No live onion connection is made.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from controls import (  # noqa: E402
    LAWFUL_PUBLIC_ONION,
    STOLEN_DATA_MARKET_ONION,
)
from stage import (  # noqa: E402
    LAWFUL_BODY,
    LogSinkRequired,
    Stage,
    Transcript,
)

OUT = HERE / "probe1-both-states.raw.json"
LAWFUL_URL = f"http://{LAWFUL_PUBLIC_ONION}/index"
STOLEN_URL = f"http://{STOLEN_DATA_MARKET_ONION}/leak"
CHECKOUT_URL = f"http://{LAWFUL_PUBLIC_ONION}/checkout"


class DropBlockedTranscript(Transcript):
    """Mutant: swallow BLOCKED events. The gate must treat this as a fail."""

    def append(self, event: dict) -> dict:
        if event.get("action") == "BLOCKED":
            payload = dict(event)
            payload["seq"] = 0
            return payload
        return super().append(event)


def blocked_logged(transcript: Transcript, decision) -> bool:
    if decision.action != "BLOCKED":
        return False
    if not decision.logged:
        return False
    return any(
        e.get("seq") == decision.seq and e.get("action") == "BLOCKED"
        for e in transcript.events
    )


def main() -> int:
    report: dict = {"probe": "probe1-both-states", "unit_id": "RES-0138"}

    enabled_log = Transcript()
    enabled = Stage.enable(owner_opt_in=True, transcript=enabled_log)
    permitted = enabled.request("GET", LAWFUL_URL)
    transact = enabled.request("POST", CHECKOUT_URL)
    stolen = enabled.request("GET", STOLEN_URL)
    buy = enabled.request("PUT", CHECKOUT_URL)
    bypass = enabled.request(
        "GET", LAWFUL_URL, headers={"Authorization": "Bearer planted"}
    )
    deanon = enabled.request("RESOLVE_PTR", LAWFUL_URL)
    socks = enabled.request("GET", LAWFUL_URL, socks_auth=("operator@example", "x"))
    connect = enabled.request("CONNECT", LAWFUL_URL)
    cred = enabled.request("GET", LAWFUL_URL, want_credential="wallet")
    clearnet = enabled.request("GET", "https://example.com/")

    off_log = Transcript()
    off = Stage.enable(owner_opt_in=False, transcript=off_log)
    off_get = off.request("GET", LAWFUL_URL)

    sink_refused = False
    try:
        Stage.enable(owner_opt_in=True, transcript=None)
    except LogSinkRequired:
        sink_refused = True

    mutant_log = DropBlockedTranscript()
    mutant = Stage.enable(owner_opt_in=True, transcript=mutant_log)
    mutant_block = mutant.request("POST", CHECKOUT_URL)
    mutant_logged = blocked_logged(mutant_log, mutant_block)
    check_fires_on_silence = not mutant_logged

    transport_saw_post = any(m == "POST" for m, _ in enabled.transport.attempts)
    transport_saw_only_get = all(m == "GET" for m, _ in enabled.transport.attempts)

    permitted_ok = (
        permitted.action == "ALLOWED"
        and permitted.body == LAWFUL_BODY
        and permitted.label == "TOR-DERIVED"
        and permitted.logged
        and any(e.get("action") == "ALLOWED" for e in enabled_log.events)
    )
    transact_ok = transact.action == "BLOCKED" and blocked_logged(
        enabled_log, transact
    )
    stolen_ok = (
        stolen.action == "BLOCKED"
        and stolen.prohibition == "stolen_data"
        and blocked_logged(enabled_log, stolen)
    )
    buy_ok = buy.action == "BLOCKED" and blocked_logged(enabled_log, buy)
    bypass_ok = (
        bypass.action == "BLOCKED"
        and bypass.prohibition == "access_control_bypass"
        and blocked_logged(enabled_log, bypass)
    )
    deanon_ok = (
        deanon.action == "BLOCKED"
        and deanon.prohibition == "deanonymise"
        and blocked_logged(enabled_log, deanon)
    )
    socks_ok = (
        socks.action == "BLOCKED"
        and socks.prohibition == "deanonymise"
        and blocked_logged(enabled_log, socks)
    )
    connect_ok = connect.action == "BLOCKED" and blocked_logged(
        enabled_log, connect
    )
    cred_ok = (
        cred.action == "BLOCKED"
        and cred.prohibition == "buy_sell"
        and blocked_logged(enabled_log, cred)
    )
    clearnet_ok = clearnet.action == "BLOCKED" and blocked_logged(
        enabled_log, clearnet
    )
    off_ok = (
        off_get.action == "BLOCKED"
        and off_get.reason == "owner-opt-in-absent"
        and blocked_logged(off_log, off_get)
        and off.transport.attempts == []
    )

    report.update(
        {
            "permitted_read": {
                "action": permitted.action,
                "label": permitted.label,
                "logged": permitted.logged,
                "body_len": len(permitted.body or b""),
            },
            "prohibited_transact": {
                "action": transact.action,
                "reason": transact.reason,
                "logged": transact.logged,
                "seq": transact.seq,
            },
            "stolen_data": {"action": stolen.action, "prohibition": stolen.prohibition},
            "buy_sell": {"action": buy.action, "reason": buy.reason},
            "access_control_bypass": {
                "action": bypass.action,
                "prohibition": bypass.prohibition,
            },
            "deanonymise_resolve_ptr": {
                "action": deanon.action,
                "prohibition": deanon.prohibition,
            },
            "deanonymise_socks_auth": {
                "action": socks.action,
                "prohibition": socks.prohibition,
            },
            "connect": {"action": connect.action, "reason": connect.reason},
            "credential_lookup": {"action": cred.action, "prohibition": cred.prohibition},
            "clearnet": {"action": clearnet.action, "reason": clearnet.reason},
            "default_off": {
                "action": off_get.action,
                "reason": off_get.reason,
                "logged": off_get.logged,
                "transport_attempts": len(off.transport.attempts),
            },
            "log_sink_required": sink_refused,
            "silence_mutant": {
                "decision_action": mutant_block.action,
                "blocked_logged": mutant_logged,
                "check_fires": check_fires_on_silence,
            },
            "transport": {
                "attempts": enabled.transport.attempts,
                "saw_post": transport_saw_post,
                "only_get": transport_saw_only_get,
            },
            "transcript_blocked_count": len(enabled_log.blocked()),
            "transcript_allowed_count": len(enabled_log.allowed()),
        }
    )

    ok = (
        permitted_ok
        and transact_ok
        and stolen_ok
        and buy_ok
        and bypass_ok
        and deanon_ok
        and socks_ok
        and connect_ok
        and cred_ok
        and clearnet_ok
        and off_ok
        and sink_refused
        and check_fires_on_silence
        and (not transport_saw_post)
        and transport_saw_only_get
        and enabled.transport.attempts == [("GET", LAWFUL_URL)]
        and transact.prohibition == "transact"
    )
    report["pass"] = bool(ok)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "permitted="
        + permitted.action
        + " transact="
        + transact.action
        + " logged_block="
        + str(transact.logged)
        + " silence_fires="
        + str(check_fires_on_silence)
        + " default_off="
        + off_get.action
        + " sink_required="
        + str(sink_refused)
        + " transport="
        + str(enabled.transport.attempts)
    )
    if not ok:
        print("FAILED:RES-0138-probe1 both-states did not discriminate")
        print(json.dumps({k: report[k] for k in report if k != "pass"}, indent=2)[:4000])
        return 1
    print("SUCCESS:RES-0138-probe1 prohibited BLOCKED+logged; permitted read succeeds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
