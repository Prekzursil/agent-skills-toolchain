"""Agent-mail bus client via raw JSON-RPC HTTP (stable; avoids streamablehttp hang)."""

from __future__ import annotations

import json
import re
import sqlite3
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_URL = "http://127.0.0.1:8812/mcp"
DEFAULT_DB = Path.home() / ".local/opt/mcp_agent_mail/storage.sqlite3"
DEFAULT_PROJECT = str(Path.home() / "source" / "agent-skills-toolchain")


class AgentMailRpc:
    def __init__(self, url: str = DEFAULT_URL, timeout: float = 30.0):
        self.url = url
        self.timeout = timeout
        self.session_id: str | None = None
        self._id = 0

    def call(
        self,
        method: str,
        params: dict | None = None,
        *,
        is_notification: bool = False,
    ) -> dict | None:
        self._id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not is_notification:
            payload["id"] = self._id
        if params is not None:
            payload["params"] = params
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
            if sid:
                self.session_id = sid
            body = resp.read().decode("utf-8", "replace")
            if body.lstrip().startswith("event:") or body.startswith("data:"):
                chunks = [
                    line[5:].strip()
                    for line in body.splitlines()
                    if line.startswith("data:")
                ]
                body = "\n".join(chunks) if chunks else body
            if is_notification or not body.strip():
                return None
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                for line in body.splitlines():
                    line = line.strip()
                    if line.startswith("{"):
                        return json.loads(line)
                raise

    def initialize(self) -> dict | None:
        result = self.call(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "crcp-bus", "version": "0.2"},
            },
        )
        self.call("notifications/initialized", {}, is_notification=True)
        return result


def _tool_text(rpc_result: dict | None) -> str:
    if not rpc_result:
        return ""
    if "error" in rpc_result:
        raise RuntimeError(json.dumps(rpc_result["error"])[:500])
    result = rpc_result.get("result") or {}
    parts: list[str] = []
    for c in result.get("content") or []:
        if isinstance(c, dict) and c.get("text"):
            parts.append(c["text"])
    if result.get("structuredContent") is not None:
        parts.append(json.dumps(result["structuredContent"]))
    return "\n".join(parts)


def tool_call(rpc: AgentMailRpc, name: str, arguments: dict) -> Any:
    res = rpc.call("tools/call", {"name": name, "arguments": arguments})
    raw = _tool_text(res)
    try:
        return json.loads(raw)
    except Exception:
        return raw


def extract_agent(reg: Any) -> tuple[str | None, str | None]:
    if isinstance(reg, dict):
        for nk, tk in (
            ("name", "registration_token"),
            ("agent_name", "registration_token"),
            ("codename", "token"),
        ):
            if reg.get(nk) and reg.get(tk):
                return reg[nk], reg[tk]
        for v in reg.values():
            if isinstance(v, dict):
                n, t = extract_agent(v)
                if n:
                    return n, t
    if isinstance(reg, str):
        m = re.search(r"([A-Z][a-z]+[A-Z][a-z]+)", reg)
        t = re.search(r"(?:registration_token|token)[\"'=\s:]+([A-Za-z0-9_\-]{8,})", reg)
        if m and t:
            return m.group(1), t.group(1)
    return None, None


def load_or_register_bridge_agent(
    rpc: AgentMailRpc,
    project: str,
    *,
    program: str = "crcp-bridge",
    model: str = "crcp-0.2",
    db: Path = DEFAULT_DB,
) -> tuple[str, str]:
    """Reuse existing crcp-bridge agent for project or register a new one."""
    tool_call(rpc, "ensure_project", {"human_key": project})
    if db.is_file():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        row = con.execute(
            """
            select a.name, a.registration_token
            from agents a join projects p on p.id=a.project_id
            where p.human_key=? and a.program=? and a.retired_at is null
            order by a.id desc limit 1
            """,
            (project, program),
        ).fetchone()
        con.close()
        if row and row[0] and row[1]:
            return row[0], row[1]

    reg = tool_call(
        rpc,
        "register_agent",
        {"project_key": project, "program": program, "model": model},
    )
    name, tok = extract_agent(reg)
    if not name or not tok:
        # try sqlite again after register
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            row = con.execute(
                """
                select a.name, a.registration_token
                from agents a join projects p on p.id=a.project_id
                where p.human_key=? and a.program=? and a.retired_at is null
                order by a.id desc limit 1
                """,
                (project, program),
            ).fetchone()
            con.close()
            if row and row[0] and row[1]:
                return row[0], row[1]
        raise RuntimeError(f"could not register bridge agent: {reg!r}"[:400])
    return name, tok


def ensure_contact(
    rpc: AgentMailRpc,
    project: str,
    sender: str,
    sender_tok: str,
    recipient: str,
    recipient_tok: str | None = None,
) -> None:
    """Best-effort contact handshake (ignore already-linked errors)."""
    try:
        tool_call(
            rpc,
            "request_contact",
            {
                "project_key": project,
                "from_agent": sender,
                "to_agent": recipient,
                "registration_token": sender_tok,
            },
        )
    except Exception:
        pass
    if recipient_tok:
        try:
            tool_call(
                rpc,
                "respond_contact",
                {
                    "project_key": project,
                    "to_agent": recipient,
                    "from_agent": sender,
                    "accept": True,
                    "registration_token": recipient_tok,
                },
            )
        except Exception:
            pass


def publish_envelope(
    envelope: dict[str, Any],
    *,
    project: str = DEFAULT_PROJECT,
    to_agents: list[str] | None = None,
    url: str = DEFAULT_URL,
    worker: Any | None = None,
) -> dict[str, Any]:
    """Publish now, or durably enqueue when a delivery worker is supplied."""
    if worker is not None:
        return worker.enqueue(
            envelope,
            project=project,
            to_agents=to_agents,
            url=url,
        )
    rpc = AgentMailRpc(url=url)
    rpc.initialize()
    sender, sender_tok = load_or_register_bridge_agent(rpc, project)

    # Prefer explicit recipients; else fan to known orchestrator/executor on project
    recipients = list(to_agents or [])
    if not recipients and DEFAULT_DB.is_file():
        con = sqlite3.connect(f"file:{DEFAULT_DB}?mode=ro", uri=True)
        rows = con.execute(
            """
            select a.name, a.registration_token, a.program
            from agents a join projects p on p.id=a.project_id
            where p.human_key=? and a.retired_at is null
              and a.program in ('claude-orchestrator','codex-executor')
            order by a.id desc
            """,
            (project,),
        ).fetchall()
        con.close()
        seen: set[str] = set()
        for name, tok, prog in rows:
            if name in seen or name == sender:
                continue
            seen.add(name)
            recipients.append(name)
            ensure_contact(rpc, project, sender, sender_tok, name, tok)

    if not recipients:
        # self-inbox so message still lands in bus storage
        recipients = [sender]

    subject = (
        f"CRCP {envelope.get('intent', 'message')} "
        f"{envelope.get('from_rail', '?')}→{envelope.get('to_rail', '?')}"
    )
    body_md = (
        "```json\n"
        + json.dumps(envelope, indent=2, default=str)[:12000]
        + "\n```\n"
    )
    if envelope.get("payload_ref"):
        body_md = f"payload_ref: `{envelope['payload_ref']}`\n\n" + body_md

    result = tool_call(
        rpc,
        "send_message",
        {
            "project_key": project,
            "sender_name": sender,
            "sender_token": sender_tok,
            "to": recipients,
            "subject": subject[:500],
            "body_md": body_md,
        },
    )
    return {
        "ok": True,
        "sender": sender,
        "recipients": recipients,
        "subject": subject,
        "envelope_id": envelope.get("id"),
        "send_result_preview": str(result)[:300],
    }
