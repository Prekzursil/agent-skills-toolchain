#!/usr/bin/env python
"""
agent_mail_probe.py — live MCP-client smoke test for mcp_agent_mail.

Connects to a running `serve-http` instance as an MCP client and proves, over the
REAL shared channel that both Claude and Codex use:
  1. symmetric_a_to_b : a message sent as agent A is readable in agent B's inbox.
  2. symmetric_b_to_a : and vice-versa.
  3. file_lease_roundtrip : an advisory file reservation acquires and releases.

Two agents stand in for Claude and Codex. Real mcp_agent_mail semantics handled here:
  - ensure_project(human_key=...) must run FIRST (creates the namespace).
  - Bare role names ("claude"/"codex") are rejected in strict mode -> register with the role
    in `program` and use the server-ASSIGNED codename as the address.
  - Each register_agent returns a `registration_token`; because ONE MCP session drives BOTH
    identities, every send/fetch/lease passes that agent's token explicitly (sender_token /
    registration_token) rather than relying on single-agent session binding.

Prints terminal-state lines: SUCCESS:<id> / FAILED:<id> <reason>. Exit code = failed checks.

Env in: AM_URL, AM_TOKEN (server bearer, may be empty), AM_PROJECT (abs path key), AM_MARK.
Run from inside the mcp_agent_mail repo via `uv run python agent_mail_probe.py`.
"""
import os
import re
import sys
import json
import asyncio

AM_URL = os.environ.get("AM_URL", "http://127.0.0.1:8812/mcp")
AM_TOKEN = os.environ.get("AM_TOKEN", "")
AM_PROJECT = os.environ.get("AM_PROJECT", os.getcwd())
AM_MARK = os.environ.get("AM_MARK", "mark0")

FAILURES = 0


def ok(check_id):
    print(f"SUCCESS:{check_id}", flush=True)


def bad(check_id, reason):
    global FAILURES
    FAILURES += 1
    print(f"FAILED:{check_id} {reason}", flush=True)


def _text(res):
    out = []
    for c in getattr(res, "content", None) or []:
        t = getattr(c, "text", None)
        if t:
            out.append(t)
        elif isinstance(c, dict) and c.get("text"):
            out.append(c["text"])
    return "\n".join(out)


def _is_error(res):
    return bool(getattr(res, "isError", False))


def _field(txt, key):
    """Extract a string field from a tool result (JSON first, then loose regex)."""
    try:
        data = json.loads(txt)
        if isinstance(data, dict):
            return data.get(key) or (data.get("agent") or {}).get(key)
    except Exception:  # noqa: BLE001
        pass
    m = re.search(rf'"{key}"\s*[:=]\s*"([^"]+)"', txt)
    return m.group(1) if m else None


async def _connect():
    from mcp.client.streamable_http import streamablehttp_client
    from mcp import ClientSession

    headers = {"Authorization": f"Bearer {AM_TOKEN}"} if AM_TOKEN else {}
    return streamablehttp_client(AM_URL, headers=headers), ClientSession


async def _register(s, role):
    """Register a stand-in agent for `role`; return (assigned_name, registration_token)."""
    r = await s.call_tool(
        "register_agent",
        {"project_key": AM_PROJECT, "program": role, "model": "probe", "format": "json"},
    )
    if _is_error(r):
        bad(f"register_{role}", _text(r)[:180])
        return None, None
    txt = _text(r)
    name = _field(txt, "name")
    tok = _field(txt, "registration_token")
    if not name:
        bad(f"register_{role}", f"no assigned name in result: {txt[:150]}")
        return None, None
    print(f"note: role={role} -> agent={name} token={'yes' if tok else 'NONE'}", file=sys.stderr)
    return name, tok


async def _establish_contact(s, frm, frm_tok, to, to_tok):
    """First contact between two agents is gated (anti-spam): the sender requests and the
    recipient accepts. Tolerant of 'already connected' on re-runs."""
    try:
        await s.call_tool(
            "request_contact",
            {"project_key": AM_PROJECT, "from_agent": frm, "to_agent": to, "reason": "probe", "registration_token": frm_tok},
        )
    except Exception as e:  # noqa: BLE001
        print(f"note: request_contact({frm}->{to}) {e!r}", file=sys.stderr)
    try:
        await s.call_tool(
            "respond_contact",
            {"project_key": AM_PROJECT, "to_agent": to, "from_agent": frm, "accept": True, "registration_token": to_tok},
        )
    except Exception as e:  # noqa: BLE001
        print(f"note: respond_contact({to} accepts {frm}) {e!r}", file=sys.stderr)


async def _send_and_check(s, check_id, sender, sender_tok, recipient, recipient_tok):
    try:
        snd = await s.call_tool(
            "send_message",
            {
                "project_key": AM_PROJECT,
                "sender_name": sender,
                "sender_token": sender_tok,
                "to": [recipient],
                "subject": f"probe-{check_id}-{AM_MARK}",
                "body_md": f"hello {recipient} {AM_MARK}",
            },
        )
        if _is_error(snd):
            bad(check_id, f"send errored: {_text(snd)[:200]}")
            return
        inbox = _text(
            await s.call_tool(
                "fetch_inbox",
                {
                    "project_key": AM_PROJECT,
                    "agent_name": recipient,
                    "registration_token": recipient_tok,
                    "include_bodies": True,
                    "limit": 25,
                },
            )
        )
        if AM_MARK in inbox:
            ok(check_id)
        else:
            bad(check_id, f"marker not found in {recipient} inbox")
    except Exception as e:  # noqa: BLE001
        bad(check_id, f"exception {e!r}")


async def main():
    try:
        client_cm_factory, ClientSession = await _connect()
    except Exception as e:  # noqa: BLE001
        bad("mcp_sdk_import", f"cannot import mcp client SDK: {e!r}")
        return 1

    try:
        async with client_cm_factory as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as s:
                await s.initialize()

                try:
                    ep = await s.call_tool("ensure_project", {"human_key": AM_PROJECT})
                    if _is_error(ep):
                        bad("ensure_project", _text(ep)[:200])
                    else:
                        ok("ensure_project")
                except Exception as e:  # noqa: BLE001
                    bad("ensure_project", f"exception {e!r}")

                agent_a, tok_a = await _register(s, "claude")
                agent_b, tok_b = await _register(s, "codex")
                if not (agent_a and agent_b):
                    bad("registration", "could not register two distinct agents; skipping messaging")
                    return FAILURES

                # Establish mutual accepted contact both ways before messaging.
                await _establish_contact(s, agent_a, tok_a, agent_b, tok_b)
                await _establish_contact(s, agent_b, tok_b, agent_a, tok_a)

                await _send_and_check(s, "symmetric_a_to_b", agent_a, tok_a, agent_b, tok_b)
                await _send_and_check(s, "symmetric_b_to_a", agent_b, tok_b, agent_a, tok_a)

                lease_path = f"probe/{AM_MARK}.txt"
                try:
                    acq = await s.call_tool(
                        "file_reservation_paths",
                        {
                            "project_key": AM_PROJECT,
                            "agent_name": agent_a,
                            "registration_token": tok_a,
                            "paths": [lease_path],
                            "ttl_seconds": 120,
                            "exclusive": True,
                            "reason": "smoke",
                        },
                    )
                    rel = await s.call_tool(
                        "release_file_reservations",
                        {
                            "project_key": AM_PROJECT,
                            "agent_name": agent_a,
                            "registration_token": tok_a,
                            "paths": [lease_path],
                        },
                    )
                    if _is_error(acq):
                        bad("file_lease_roundtrip", f"acquire errored: {_text(acq)[:200]}")
                    elif _is_error(rel):
                        bad("file_lease_roundtrip", f"release errored: {_text(rel)[:200]}")
                    else:
                        ok("file_lease_roundtrip")
                except Exception as e:  # noqa: BLE001
                    bad("file_lease_roundtrip", f"exception {e!r}")
    except Exception as e:  # noqa: BLE001
        bad("mcp_session", f"could not open session to {AM_URL}: {e!r}")

    return FAILURES


if __name__ == "__main__":
    rc = asyncio.run(main())
    if rc == 0:
        print("SUCCESS:all_checks_passed", flush=True)
    else:
        print(f"FAILED:overall {rc} check(s) failed", flush=True)
    sys.exit(min(rc, 125))
