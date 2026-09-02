"""MCP adapter under test (conforming) and named policy mutants.

The suite is written BEFORE broad implementation: this adapter is the
executable contract, not a claim about a shipped production MCP client.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from classify import classify
from protocol import (
    MalformedResult,
    namespaced,
    parse_call_tool_result,
    schemas_equal,
    split_namespaced,
)
from servers import MockServer

SCOPE_ORDER = ("local", "project", "user")
STDIO_CAP = 8


@dataclass
class Policy:
    name: str
    namespace: bool = True
    drift_schema: bool = False
    empty_success_on_malformed: bool = False
    require_declaration: bool = True
    record_transport: bool = True
    stdio_cap: int | None = STDIO_CAP
    any_scope_disable: bool = False
    preserve_enable_on_migrate: bool = True
    reap_on_unmount: bool = True


CONFORMING = Policy(name="conforming")
EMPTY_SUCCESS = Policy(name="empty_success", empty_success_on_malformed=True)
SCHEMA_DRIFT = Policy(name="schema_drift", drift_schema=True)
BARE_NAMES = Policy(name="bare_names", namespace=False)
NO_DECLARATION = Policy(name="no_declaration", require_declaration=False)
NO_TRANSPORT = Policy(name="no_transport", record_transport=False)
NO_CAP = Policy(name="no_stdio_cap", stdio_cap=None)
ANY_SCOPE_DISABLE = Policy(name="any_scope_disable", any_scope_disable=True)
DESTROY_ENABLE = Policy(name="destroy_enable", preserve_enable_on_migrate=False)
LEAK_REAP = Policy(name="leak_reap", reap_on_unmount=False)


@dataclass
class Adapter:
    policy: Policy
    servers: dict[str, MockServer] = field(default_factory=dict)
    enable: dict[str, dict[str, bool]] = field(default_factory=dict)
    _seq: int = 0

    def __post_init__(self) -> None:
        self.enable = {s: {} for s in SCOPE_ORDER}

    def _next_id(self) -> str:
        self._seq += 1
        return f"{self.policy.name}-call-{self._seq:04d}"

    def mount(self, server: MockServer, *, declaration: dict | None) -> dict:
        if self.policy.require_declaration:
            if not isinstance(declaration, dict) or not declaration:
                raise ValueError("server declaration required")
            if not declaration.get("command") and not declaration.get("url"):
                raise ValueError("declaration must name command (stdio) or url (http)")
        transport = server.transport if self.policy.record_transport else ""
        if self.policy.record_transport and transport not in {"stdio", "http"}:
            raise ValueError(f"unknown transport {transport!r}")
        if (
            server.transport == "stdio"
            and self.policy.stdio_cap is not None
        ):
            n_stdio = sum(
                1
                for s in self.servers.values()
                if s.transport == "stdio" and s.spawned
            )
            if n_stdio >= self.policy.stdio_cap:
                raise ValueError(
                    f"stdio process cap {self.policy.stdio_cap} per session"
                )
        if not self._enabled(server.server_id):
            return {
                "mounted": False,
                "reason": "disabled-at-effective-scope",
                "transport": transport or None,
            }
        self.servers[server.server_id] = server
        server.start()
        return {
            "mounted": True,
            "server_id": server.server_id,
            "transport": transport or None,
            "lifecycle_owner": "adapter",
        }

    def unmount(self, server_id: str) -> None:
        server = self.servers.pop(server_id, None)
        if server is None:
            return
        if self.policy.reap_on_unmount:
            server.reap()

    def set_enabled(self, server_id: str, enabled: bool, *, scope: str) -> None:
        if scope not in SCOPE_ORDER:
            raise ValueError(f"unknown scope {scope!r}")
        self.enable[scope][server_id] = enabled

    def _enabled(self, server_id: str) -> bool:
        if self.policy.any_scope_disable:
            for scope in SCOPE_ORDER:
                if self.enable[scope].get(server_id) is False:
                    return False
            for scope in SCOPE_ORDER:
                if server_id in self.enable[scope]:
                    return bool(self.enable[scope][server_id])
            return True
        for scope in SCOPE_ORDER:
            if server_id in self.enable[scope]:
                return bool(self.enable[scope][server_id])
        return True

    def snapshot_enable(self) -> dict:
        return deepcopy(self.enable)

    def migrate(self, snapshot: dict) -> None:
        if self.policy.preserve_enable_on_migrate:
            self.enable = deepcopy(snapshot)
        else:
            self.enable = {s: {} for s in SCOPE_ORDER}

    def list_tools(self) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for sid, server in self.servers.items():
            if not server.spawned:
                continue
            for tool in server.list_tools():
                name = str(tool["name"])
                exposed = namespaced(sid, name) if self.policy.namespace else name
                schema = deepcopy(tool.get("inputSchema"))
                if self.policy.drift_schema:
                    schema = deepcopy(schema) if isinstance(schema, dict) else {}
                    extra = schema.setdefault("properties", {})
                    if isinstance(extra, dict):
                        extra["_drifted"] = {"type": "boolean"}
                if exposed in seen:
                    raise ValueError(f"tool name collision {exposed!r}")
                seen.add(exposed)
                out.append(
                    {
                        "name": exposed,
                        "server_id": sid,
                        "bare_name": name,
                        "description": tool.get("description"),
                        "inputSchema": schema,
                    }
                )
        return sorted(out, key=lambda t: t["name"])

    def schema_fidelity_ok(self) -> tuple[bool, str]:
        if self.policy.drift_schema:
            return False, "policy drifts schemas"
        if not self.policy.namespace:
            names = [t["name"] for t in self.list_tools()]
            if len(names) != len(set(names)):
                return False, "un-namespaced collision"
        try:
            exposed = self.list_tools()
        except ValueError as exc:
            return False, str(exc)
        advertised: dict[str, dict] = {}
        for sid, server in self.servers.items():
            if not server.spawned:
                continue
            for tool in server.advertised_tools():
                key = namespaced(sid, str(tool["name"])) if self.policy.namespace else str(tool["name"])
                advertised[key] = tool
        if {t["name"] for t in exposed} != set(advertised):
            return False, "exposed names != advertised names"
        for item in exposed:
            adv = advertised[item["name"]]
            if item.get("description") != adv.get("description"):
                return False, f"description drift {item['name']}"
            expect_schema = adv.get("inputSchema")
            if not schemas_equal(item.get("inputSchema"), expect_schema):
                return False, f"inputSchema drift {item['name']}"
        return True, "byte-faithful namespaced schemas"

    def call(self, tool: str, arguments: dict | None = None) -> dict:
        arguments = arguments or {}
        if self.policy.namespace:
            server_id, bare = split_namespaced(tool)
        else:
            matches = [
                sid
                for sid, server in self.servers.items()
                if any(t["name"] == tool for t in server.advertised_tools())
            ]
            if len(matches) != 1:
                return self._failed("blocked", f"unresolvable bare name {tool!r}")
            server_id, bare = matches[0], tool
        server = self.servers.get(server_id)
        if server is None or not server.spawned:
            return self._failed("blocked", f"server {server_id!r} not mounted")
        raw = server.call_raw(bare, arguments)
        try:
            parsed = parse_call_tool_result(raw)
        except MalformedResult as exc:
            if self.policy.empty_success_on_malformed:
                return {
                    "status": "SUCCESS",
                    "id": None,
                    "failure_class": None,
                    "reason": None,
                    "content": [],
                    "is_error": False,
                }
            return {
                "status": "FAILED",
                "id": self._next_id(),
                "failure_class": "schema-invalid",
                "reason": f"malformed CallToolResult: {exc.code}",
                "content": [
                    {"type": "text", "text": f"MALFORMED:{exc.code}"}
                ],
                "is_error": True,
            }
        rid = self._next_id()
        if parsed.get("isError"):
            return {
                "status": "FAILED",
                "id": rid,
                "failure_class": "tool-error",
                "reason": "server isError=true",
                "content": parsed["content"],
                "is_error": True,
            }
        return {
            "status": "SUCCESS",
            "id": rid,
            "failure_class": None,
            "reason": None,
            "content": parsed["content"],
            "is_error": False,
        }

    def _failed(self, fclass: str, reason: str) -> dict:
        return {
            "status": "FAILED",
            "id": self._next_id(),
            "failure_class": fclass,
            "reason": reason,
            "content": [{"type": "text", "text": reason}],
            "is_error": True,
        }

    def classify_call(self, tool: str, arguments: dict | None = None) -> dict:
        terminal = self.call(tool, arguments)
        graded = classify(terminal)
        return {"terminal": terminal, "classification": graded}


def bind(policy: Policy, servers: list[MockServer]) -> Adapter:
    adapter = Adapter(policy=policy)
    for server in servers:
        decl = (
            {"command": ["mock", server.server_id]}
            if server.transport == "stdio"
            else {"url": f"http://127.0.0.1/mcp/{server.server_id}"}
        )
        adapter.mount(server, declaration=decl)
    return adapter
