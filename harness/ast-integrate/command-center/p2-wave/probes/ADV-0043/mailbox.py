#!/usr/bin/env python3
"""Isolated replica of the published MCP Agent Mail tool contract.

Source of the contract (not vendored in this worktree; RES-0136):
Dicklesworthstone/mcp_agent_mail README + SKILL.md, retrieved 2026-08-24.

Faithful points measured here:
  * project_key is an absolute directory path; agents sharing that path
    share one namespace.
  * register_agent issues a registration_token.
  * fetch_inbox(project_key, agent_name, registration_token=None):
    the token is OPTIONAL in the published tool table.
  * send_message(project_key, sender, to, subject, body_md)
  * file_reservation_paths is advisory; reservations are listed per project.
  * Contact policy, when modelled, gates SEND, not FETCH.
  * Storage can hold many projects; isolation is by project_key.

This replica exists because this Cursor session has no agent-mail MCP
namespace and the worktree does not vendor the server. Probes also scan
the host for a live store and classify it when present.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Agent:
    name: str
    project_key: str
    token: str
    program: str = ""
    retired: bool = False


@dataclass
class Message:
    id: int
    project_key: str
    sender: str
    recipients: list[str]
    subject: str
    body: str
    created_at: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Reservation:
    id: int
    project_key: str
    agent_name: str
    path: str
    reason: str
    exclusive: bool


class Mailbox:
    """In-process mailbox implementing the catalog-named tools."""

    def __init__(self) -> None:
        self.agents: dict[tuple[str, str], Agent] = {}
        self.messages: list[Message] = []
        self.reservations: list[Reservation] = []
        self.projects: set[str] = set()
        self._msg_id = 0
        self._res_id = 0

    def ensure_project(self, project_key: str) -> str:
        if not project_key.startswith("/"):
            raise ValueError("project_key must be an absolute path")
        self.projects.add(project_key)
        return project_key

    def register_agent(
        self, project_key: str, name: str, program: str = "probe"
    ) -> Agent:
        self.ensure_project(project_key)
        key = (project_key, name)
        existing = self.agents.get(key)
        if existing and not existing.retired:
            return existing
        agent = Agent(
            name=name,
            project_key=project_key,
            token="tok_" + secrets.token_hex(12),
            program=program,
        )
        self.agents[key] = agent
        return agent

    def deregister_agent(self, project_key: str, name: str, token: str) -> bool:
        key = (project_key, name)
        agent = self.agents.get(key)
        if agent is None or agent.retired:
            return False
        if agent.token != token:
            return False
        agent.retired = True
        return True

    def send_message(
        self,
        project_key: str,
        sender: str,
        to: list[str] | str,
        subject: str,
        body: str,
        **extra: Any,
    ) -> Message:
        self.ensure_project(project_key)
        sender_agent = self.agents.get((project_key, sender))
        if sender_agent is None or sender_agent.retired:
            raise PermissionError("sender_name not registered")
        recipients = [to] if isinstance(to, str) else list(to)
        self._msg_id += 1
        msg = Message(
            id=self._msg_id,
            project_key=project_key,
            sender=sender,
            recipients=recipients,
            subject=subject,
            body=body,
            created_at=_now(),
            extra=dict(extra),
        )
        self.messages.append(msg)
        return msg

    def fetch_inbox(
        self,
        project_key: str,
        agent_name: str,
        registration_token: str | None = None,
        *,
        require_token: bool = False,
    ) -> dict[str, Any]:
        """Published tool: token is optional unless require_token=True.

        require_token=True is the bound-ACL twin (what resource://inbox
        with agent_token models). The catalog-named MCP tool does not
        require the token.
        """
        agent = self.agents.get((project_key, agent_name))
        if agent is None or agent.retired:
            return {
                "ok": False,
                "error": "agent not registered",
                "project_key": project_key,
                "agent_name": agent_name,
                "messages": [],
            }
        if require_token:
            if not registration_token or registration_token != agent.token:
                return {
                    "ok": False,
                    "error": "registration_token mismatch",
                    "project_key": project_key,
                    "agent_name": agent_name,
                    "messages": [],
                }
        elif registration_token is not None and registration_token != agent.token:
            return {
                "ok": False,
                "error": "registration_token mismatch",
                "project_key": project_key,
                "agent_name": agent_name,
                "messages": [],
            }
        inbox = [
            self._public(m)
            for m in self.messages
            if m.project_key == project_key
            and (agent_name in m.recipients or m.sender == agent_name)
        ]
        return {
            "ok": True,
            "project_key": project_key,
            "agent_name": agent_name,
            "count": len(inbox),
            "messages": inbox,
            "token_required": require_token,
            "token_supplied": registration_token is not None,
        }

    def file_reservation_paths(
        self,
        project_key: str,
        agent_name: str,
        paths: list[str],
        reason: str = "",
        exclusive: bool = True,
    ) -> dict[str, Any]:
        agent = self.agents.get((project_key, agent_name))
        if agent is None or agent.retired:
            raise PermissionError("agent not registered")
        granted = []
        for path in paths:
            self._res_id += 1
            row = Reservation(
                id=self._res_id,
                project_key=project_key,
                agent_name=agent_name,
                path=path,
                reason=reason,
                exclusive=exclusive,
            )
            self.reservations.append(row)
            granted.append(
                {
                    "id": row.id,
                    "path": row.path,
                    "agent_name": row.agent_name,
                    "reason": row.reason,
                    "exclusive": row.exclusive,
                }
            )
        return {"granted": granted, "conflicts": []}

    def list_file_reservations(
        self, project_key: str, caller_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Any agent that knows project_key can list active reservations.

        The published resource://file_reservations/{slug} is project-scoped,
        not holder-scoped.
        """
        del caller_name
        return [
            {
                "id": r.id,
                "path": r.path,
                "agent_name": r.agent_name,
                "reason": r.reason,
                "exclusive": r.exclusive,
                "project_key": r.project_key,
            }
            for r in self.reservations
            if r.project_key == project_key
        ]

    def _public(self, msg: Message) -> dict[str, Any]:
        return {
            "id": msg.id,
            "project_key": msg.project_key,
            "sender": msg.sender,
            "recipients": list(msg.recipients),
            "subject": msg.subject,
            "body": msg.body,
            "created_at": msg.created_at,
            "extra": dict(msg.extra),
        }
