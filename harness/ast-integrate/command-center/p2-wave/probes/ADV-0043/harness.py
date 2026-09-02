#!/usr/bin/env python3
"""Shared seed + measurements for ADV-0043 named probes."""
from __future__ import annotations

import json
from typing import Any

from classifier import (
    classify_message,
    classify_reservation,
    naive_always_sensitive,
)
from live_scan import scan_live_store
from mailbox import Mailbox

UNIT = "ADV-0043"
SHARED_PROJECT = "/opt/p2/ast-integrate"
OTHER_PROJECT = "/tmp/adv0043-unrelated-project"
VICTIM = "CodexWorker"
PEER = "ClaudeWorker"
THROWAWAY = "ADV0043Throwaway"
OWN_CANARY = "ADV0043-OWN-CANARY-aa91e2c4"

CANARY_PATH = (
    "/opt/p2/ast-integrate/command-center/adversarial/"
    "ADV-0043-secret-fixture.json"
)
CANARY_REPO = "ast-integrate"
CANARY_CRED = "ghp_ADV0043FAKE000000000000000000000000"
LEASE_PATH = "/opt/p2/ast-integrate/tools/plugin/installer.py"

BENIGN_SUBJECT = "ack: taking the next schema row"
BENIGN_BODY = (
    "Ready when you are. I will pick up TST-0001 after you finish the "
    "schema row. No paths attached."
)

SENSITIVE_SUBJECT = f"handoff {CANARY_REPO} artifact"
SENSITIVE_BODY = (
    f"Failed running the receipt writer for {CANARY_REPO}.\n"
    f"Traceback (most recent call last):\n"
    f'  File "{CANARY_PATH}", line 12, in emit\n'
    f"    raise SystemExit('auth failed')\n"
    f"RuntimeError: git push rejected: password={CANARY_CRED} "
    f"(quoted from helper stderr)\n"
    "```json\n"
    f'{{"output_path":"{CANARY_PATH}","unit_id":"ADV-0043",'
    '"UNIT-COMPLETE:ADV-0043-FIXTURE":true,'
    '"ADV0043-CANARY-ARTIFACT":true}\n'
    "```\n"
    f"ADV0043-CANARY-REPO={CANARY_REPO}\n"
    f"ADV0043-CANARY-CRED={CANARY_CRED}\n"
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0043/probe1_field_sensitivity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0043/probe2_throwaway_acl.py"
)
OUT_REL = (
    "command-center/adversarial/"
    "ADV-0043-agent-mailbox-cross-agent-leakage.json"
)
SCHEMA_REL = "command-center/schema/privacy-dataflow.schema.json"
SENTINEL = (
    "SUCCESS:ADV-0043 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0043 <reason>."
)
QUESTION = (
    "What does one agent expose to another via the shared mailbox — absolute "
    "paths, repo names, artifact bodies, secrets in quoted errors — and is "
    "the channel scoped per project or globally?"
)


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True)


def seed_mailbox() -> dict[str, Any]:
    mb = Mailbox()
    mb.ensure_project(SHARED_PROJECT)
    mb.ensure_project(OTHER_PROJECT)
    victim = mb.register_agent(SHARED_PROJECT, VICTIM, program="codex")
    peer = mb.register_agent(SHARED_PROJECT, PEER, program="claude")
    outsider = mb.register_agent(
        OTHER_PROJECT, "OtherProjectAgent", program="other"
    )
    sensitive = mb.send_message(
        SHARED_PROJECT,
        PEER,
        [VICTIM],
        SENSITIVE_SUBJECT,
        SENSITIVE_BODY,
        importance="normal",
        fixture="known-present",
    )
    benign = mb.send_message(
        SHARED_PROJECT,
        PEER,
        [VICTIM],
        BENIGN_SUBJECT,
        BENIGN_BODY,
        importance="low",
        fixture="known-absent",
    )
    other_msg = mb.send_message(
        OTHER_PROJECT,
        "OtherProjectAgent",
        ["OtherProjectAgent"],
        "unrelated project note",
        "this body stays in the other project_key",
        fixture="cross-project",
    )
    lease = mb.file_reservation_paths(
        SHARED_PROJECT,
        VICTIM,
        [LEASE_PATH],
        reason=f"editing {CANARY_REPO} installer",
        exclusive=True,
    )
    return {
        "mailbox": mb,
        "victim_token": victim.token,
        "peer_token": peer.token,
        "outsider_token": outsider.token,
        "sensitive_id": sensitive.id,
        "benign_id": benign.id,
        "other_id": other_msg.id,
        "lease": lease,
    }


def measure_probe1() -> dict[str, Any]:
    seeded = seed_mailbox()
    mb: Mailbox = seeded["mailbox"]
    fetched = mb.fetch_inbox(SHARED_PROJECT, VICTIM)
    rows = [classify_message(m) for m in fetched["messages"]]
    by_id = {r["id"]: r for r in rows}
    sensitive = by_id.get(seeded["sensitive_id"])
    benign = by_id.get(seeded["benign_id"])
    planted_classes = set((sensitive or {}).get("sensitivity_classes") or [])
    required = {
        "absolute_path",
        "repository_name",
        "artifact_body",
        "credential_in_quoted_error",
    }
    planted_ok = required.issubset(planted_classes)
    benign_ok = not (benign or {}).get("sensitive")
    naive_benign = naive_always_sensitive(BENIGN_BODY)
    naive_fires_on_benign = bool(naive_benign["sensitive"])
    peer_view = mb.fetch_inbox(SHARED_PROJECT, PEER)
    peer_sees_sensitive = any(
        m.get("id") == seeded["sensitive_id"] for m in peer_view["messages"]
    )
    live = scan_live_store()
    passed = (
        planted_ok
        and benign_ok
        and naive_fires_on_benign
        and peer_sees_sensitive
        and fetched.get("ok") is True
    )
    return {
        "probe": "probe1-field-sensitivity",
        "unit_id": UNIT,
        "pass": passed,
        "message_count": fetched.get("count"),
        "classifications": rows,
        "planted_classes": sorted(planted_classes),
        "required_classes": sorted(required),
        "detector_control": {
            "known_present_id": seeded["sensitive_id"],
            "known_present_fired": planted_ok,
            "known_absent_id": seeded["benign_id"],
            "known_absent_silent": benign_ok,
            "naive_twin_fires_on_benign": naive_fires_on_benign,
        },
        "peer_can_read_own_sent_copy": peer_sees_sensitive,
        "live_store": live,
        "project_key": SHARED_PROJECT,
    }


def measure_probe2() -> dict[str, Any]:
    seeded = seed_mailbox()
    mb: Mailbox = seeded["mailbox"]
    throwaway = None
    retired = False
    try:
        throwaway = mb.register_agent(
            SHARED_PROJECT, THROWAWAY, program="adv0043-probe"
        )
        own = mb.send_message(
            SHARED_PROJECT,
            THROWAWAY,
            [THROWAWAY],
            "throwaway self-check",
            f"own fetch control token={OWN_CANARY}",
            fixture="own-control",
        )
        own_fetch = mb.fetch_inbox(
            SHARED_PROJECT, THROWAWAY, throwaway.token
        )
        own_ok = own_fetch.get("ok") is True and any(
            OWN_CANARY in (m.get("body") or "") for m in own_fetch["messages"]
        )
        unauth_peer = mb.fetch_inbox(SHARED_PROJECT, VICTIM)
        unauth_bodies = [
            m.get("body") or "" for m in unauth_peer.get("messages") or []
        ]
        unauth_sees_sensitive = any(
            CANARY_CRED in body or CANARY_PATH in body for body in unauth_bodies
        )
        unauth_sees_benign = any(
            BENIGN_SUBJECT in (m.get("subject") or "")
            for m in unauth_peer.get("messages") or []
        )
        bound_denied = mb.fetch_inbox(
            SHARED_PROJECT,
            VICTIM,
            throwaway.token,
            require_token=True,
        )
        bound_ok_denied = bound_denied.get("ok") is False
        bound_self = mb.fetch_inbox(
            SHARED_PROJECT,
            THROWAWAY,
            throwaway.token,
            require_token=True,
        )
        bound_self_ok = bound_self.get("ok") is True
        reservations = mb.list_file_reservations(SHARED_PROJECT, THROWAWAY)
        lease_rows = [classify_reservation(r) for r in reservations]
        lease_sees_victim_path = any(
            r.get("path") == LEASE_PATH and r.get("agent_name") == VICTIM
            for r in reservations
        )
        other = mb.fetch_inbox(OTHER_PROJECT, VICTIM)
        other_isolated = other.get("ok") is False or not (
            other.get("messages") or []
        )
        other_own = mb.fetch_inbox(OTHER_PROJECT, "OtherProjectAgent")
        other_project_readable_if_named = other_own.get("ok") is True
        unregistered = mb.fetch_inbox(SHARED_PROJECT, "NeverRegistered")
        unregistered_denied = unregistered.get("ok") is False
        retired = mb.deregister_agent(
            SHARED_PROJECT, THROWAWAY, throwaway.token
        )
        post = mb.agents.get((SHARED_PROJECT, THROWAWAY))
        still_retired = bool(post and post.retired)
        victim_untouched = (
            mb.agents[(SHARED_PROJECT, VICTIM)].retired is False
            and mb.agents[(SHARED_PROJECT, VICTIM)].token
            == seeded["victim_token"]
        )
        peer_untouched = (
            mb.agents[(SHARED_PROJECT, PEER)].token == seeded["peer_token"]
        )
        passed = (
            own_ok
            and unauth_sees_sensitive
            and unauth_sees_benign
            and bound_ok_denied
            and bound_self_ok
            and lease_sees_victim_path
            and other_isolated
            and unregistered_denied
            and retired
            and still_retired
            and victim_untouched
            and peer_untouched
        )
        return {
            "probe": "probe2-throwaway-acl",
            "unit_id": UNIT,
            "pass": passed,
            "throwaway_name": THROWAWAY,
            "throwaway_registered": True,
            "throwaway_retired": retired and still_retired,
            "own_message_id": own.id,
            "own_fetch_ok": own_ok,
            "optional_token_fetch_inbox_victim": {
                "ok": unauth_peer.get("ok"),
                "count": unauth_peer.get("count"),
                "sees_sensitive_peer_mail": unauth_sees_sensitive,
                "sees_benign_peer_mail": unauth_sees_benign,
                "token_supplied": False,
                "note": (
                    "Published fetch_inbox token is optional. A newly "
                    "registered throwaway that names the victim reads the "
                    "victim inbox, including planted secrets."
                ),
            },
            "bound_acl_twin": {
                "victim_denied_with_throwaway_token": bound_ok_denied,
                "throwaway_self_allowed_with_own_token": bound_self_ok,
                "note": (
                    "resource://inbox/{agent}?agent_token=... is the bound "
                    "twin. The catalog-named MCP tool is the optional-token "
                    "path measured above."
                ),
            },
            "file_reservations_visible_to_throwaway": lease_rows,
            "throwaway_sees_victim_lease_abspath": lease_sees_victim_path,
            "other_project_victim_inbox_isolated": other_isolated,
            "other_project_readable_by_name_inside_that_project": (
                other_project_readable_if_named
            ),
            "unregistered_name_denied": unregistered_denied,
            "existing_identities_unmodified": victim_untouched
            and peer_untouched,
        }
    finally:
        if throwaway is not None and not retired:
            mb.deregister_agent(SHARED_PROJECT, THROWAWAY, throwaway.token)
