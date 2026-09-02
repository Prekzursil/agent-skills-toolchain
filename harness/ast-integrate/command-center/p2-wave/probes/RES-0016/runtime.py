"""Local Agent-tool spawn runtime for RES-0016.

Implements the published Claude Code Agent/Task spawn contract as frozen in
fixtures/docs/*.excerpt.md. This is a mechanical model of the documented
refusal and inheritance rules, not a live LLM spawn.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

STICKY_PARENT_MODES = frozenset({"bypassPermissions", "acceptEdits", "auto"})
ENV_DEPTH = "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"
ENV_CONCURRENT = "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS"
DEFAULT_DEPTH = 3
DEFAULT_CONCURRENT = 20
CONCURRENT_REFUSAL = "Concurrent subagent limit reached"
DEPTH_WITHHOLD_REFUSAL = "Agent tool withheld at spawn depth limit"
FORK_DEPTH_REFUSAL = "the tool returns an error instead of spawning"
NON_DIGIT_IGNORED = True


class SpawnRefused(Exception):
    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind


def parse_positive_whole_digits(raw: Optional[str], default: int) -> int:
    """Docs: accept a positive whole number in plain digits; anything else is ignored."""
    if raw is None:
        return default
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return default


def normalize_mode(mode: Optional[str]) -> Optional[str]:
    if mode is None:
        return None
    if mode == "manual":
        return "default"
    return mode


def resolve_permission_mode(
    parent_mode: str,
    explicit: Optional[str],
    *,
    disable_bypass_permissions_mode: bool = False,
) -> str:
    parent = normalize_mode(parent_mode) or "default"
    requested = normalize_mode(explicit)
    if disable_bypass_permissions_mode and requested == "bypassPermissions":
        requested = None
    if parent in STICKY_PARENT_MODES:
        return parent
    if requested is not None:
        return requested
    return parent


@dataclass
class Spawned:
    depth: int
    permission_mode: str
    fork: bool
    tools: tuple[str, ...]
    running_slot: int


class Session:
    def __init__(
        self,
        *,
        max_depth: int = DEFAULT_DEPTH,
        max_concurrent: int = DEFAULT_CONCURRENT,
        parent_permission_mode: str = "default",
        disable_bypass_permissions_mode: bool = False,
        ultracode: bool = False,
    ) -> None:
        if max_depth < 1 or max_concurrent < 1:
            raise ValueError("limits must be positive")
        self.max_depth = max_depth
        self.max_concurrent = max_concurrent
        self.parent_permission_mode = normalize_mode(parent_permission_mode) or "default"
        self.disable_bypass_permissions_mode = disable_bypass_permissions_mode
        self.ultracode = ultracode
        self.running = 0
        self.spawned: list[Spawned] = []

    @classmethod
    def from_env(cls, **kwargs) -> "Session":
        env = kwargs.pop("env", os.environ)
        max_depth = parse_positive_whole_digits(env.get(ENV_DEPTH), DEFAULT_DEPTH)
        max_concurrent = parse_positive_whole_digits(
            env.get(ENV_CONCURRENT), DEFAULT_CONCURRENT
        )
        return cls(max_depth=max_depth, max_concurrent=max_concurrent, **kwargs)

    def spawn(
        self,
        *,
        parent_depth: int = 0,
        permission_mode: Optional[str] = None,
        fork: bool = False,
        parent_permission_mode: Optional[str] = None,
    ) -> Spawned:
        child_depth = parent_depth + 1
        if child_depth > self.max_depth:
            if fork:
                raise SpawnRefused(FORK_DEPTH_REFUSAL, kind="depth-fork")
            raise SpawnRefused(DEPTH_WITHHOLD_REFUSAL, kind="depth-withhold")
        if (not self.ultracode) and self.running >= self.max_concurrent:
            raise SpawnRefused(CONCURRENT_REFUSAL, kind="concurrent")
        parent_mode = parent_permission_mode or self.parent_permission_mode
        resolved = resolve_permission_mode(
            parent_mode,
            permission_mode,
            disable_bypass_permissions_mode=self.disable_bypass_permissions_mode,
        )
        tools = ("Read", "Grep", "Glob", "Bash")
        if child_depth < self.max_depth or fork:
            tools = tools + ("Agent",)
        self.running += 1
        agent = Spawned(
            depth=child_depth,
            permission_mode=resolved,
            fork=fork,
            tools=tools,
            running_slot=self.running,
        )
        self.spawned.append(agent)
        return agent

    def finish(self, agent: Spawned) -> None:
        if self.running <= 0:
            raise RuntimeError("finish with no running agents")
        self.running -= 1
        agent.running_slot = 0

    def agent_tool_available(self, agent: Spawned) -> bool:
        return "Agent" in agent.tools
