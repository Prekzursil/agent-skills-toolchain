"""The stream-json ``control_request`` channel, behind an injected TRANSPORT port.

A host session started with ``--input-format stream-json`` accepts control frames on
stdin. Everything in this module above :class:`Transport` is pure request-building and
response-parsing, so the hermetic suite drives a fake and **no real session is ever
spawned by the gated tests**. :class:`SubprocessTransport` is the production port; its
process spawn is itself injected (``spawn``), and the test that binds the real default
drives a short-lived Python child, never the host binary.

Wire facts, all taken from the recorded evidence run and re-checked against the
installed binary's schemas -- do NOT re-derive them:

* Response payloads are DOUBLE nested: ``msg["response"]["response"]``. Reading
  ``msg["response"]["mcpServers"]`` yields ``None`` and produced a confident FALSE
  NEGATIVE in the original run.
* ``response`` is optional and is ABSENT on ``mcp_reconnect`` / ``mcp_toggle`` -- the
  caller must re-issue ``mcp_status`` to observe the effect.
* ``mcp_set_servers`` REPLACES the dynamically-managed set; a caller must read the
  current dynamic set and re-send it, minus/plus the one server it means to change.
* A partial failure is a ``success`` frame with a populated ``errors`` map, not an
  error frame.
* Frames interleave with ``assistant``/``user``/``system``/``result`` traffic, and
  responses may arrive OUT OF ORDER, so the reader is a demultiplexer keyed on
  ``request_id`` -- never a sequential consumer.
* Naming is inconsistent on purpose in the protocol: ``serverName`` on reconnect and
  toggle, ``server_name`` on ``mcp_message``.

Two corrections to the folklore, both load-bearing for what the UI may offer:

* ``mcp_toggle`` is **not "any scope"**. Project scope (``.mcp.json``) is a recorded
  CLEAN NEGATIVE -- the server was ``connected`` before the disable and ``connected``
  after. Dynamic is proven twice, user scope once (sandbox). See :data:`AFFORDANCES`.
* ``mcp_toggle`` is a **persistent config write**, not an in-memory flip: it edits
  ``~/.claude.json`` -> ``projects[<the control session's cwd>].disabledMcpServers``.
  So the live lane mutates the same file the config lane does, it cannot be previewed
  through the control channel (issuing it IS the write), and the write lands under the
  CONTROL SESSION's cwd -- which is why :class:`SubprocessTransport` takes an explicit
  ``cwd`` instead of inheriting the GUI's.
"""

from __future__ import annotations

import json
import subprocess  # noqa: S404 -- spawning the host session is this module's purpose.
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, cast

from mcpctl.matrix import Liveness
from mcpctl.safety import safe
from mcpctl.scopes import ScopeId

__all__ = [
    "AFFORDANCES",
    "Affordance",
    "ControlError",
    "LiveClient",
    "LiveOp",
    "Proof",
    "SubprocessTransport",
    "Transport",
    "affordance",
    "control_frame",
    "kick_frame",
    "liveness_from_status",
    "parse_frame",
    "session_argv",
    "status_servers",
]

#: A session started for control does NOT emit ``system/init`` until it has received
#: its FIRST USER MESSAGE. Waiting for init before writing to stdin deadlocks forever
#: (it cost two dead runs in the evidence campaign). Send this first, then control.
_KICK_TEXT = "Reply with exactly: READY"


class LiveOp(str, Enum):
    """The control subtypes this package uses."""

    STATUS = "mcp_status"
    SET_SERVERS = "mcp_set_servers"
    RECONNECT = "mcp_reconnect"
    TOGGLE = "mcp_toggle"


class Proof(str, Enum):
    """How well a (scope, operation) pair is evidenced. Not a guess -- a record."""

    #: Demonstrated working, with a status transition observed.
    PROVEN = "proven"
    #: Demonstrated once, in a sandbox only. Offer, but label it.
    PROVISIONAL = "provisional"
    #: Never demonstrated. Do not advertise as working.
    UNPROVEN = "unproven"
    #: Demonstrated NOT to work: a clean negative, not a flake.
    DISPROVEN = "disproven"


@dataclass(frozen=True)
class Affordance:
    """What the UI may offer for one (scope, operation) pair, and why."""

    scope: ScopeId
    op: LiveOp
    proof: Proof
    note: str

    @property
    def offer(self) -> bool:
        """True when a control may be enabled in the UI at all."""
        return self.proof in (Proof.PROVEN, Proof.PROVISIONAL)


#: The measured per-scope matrix. ``dynamic`` is not a config scope so it is keyed by
#: ``None``; every config scope uses its :class:`~mcpctl.scopes.ScopeId`.
AFFORDANCES: tuple[Affordance, ...] = (
    Affordance(
        ScopeId.CLAUDE_USER,
        LiveOp.TOGGLE,
        Proof.PROVISIONAL,
        "passed once, in a sandbox (n=1); offer it, but label it provisional",
    ),
    Affordance(
        ScopeId.CLAUDE_USER,
        LiveOp.RECONNECT,
        Proof.DISPROVEN,
        "failed with 'Server not found' against a user-scope name",
    ),
    Affordance(
        ScopeId.MCP_JSON,
        LiveOp.TOGGLE,
        Proof.DISPROVEN,
        "CLEAN NEGATIVE: connected before the disable, connected after. The toggle "
        "path writes disabledMcpServers, which does not govern a .mcp.json server; "
        "edit disabledMcpjsonServers on disk and reconnect instead",
    ),
    Affordance(
        ScopeId.MCP_JSON,
        LiveOp.RECONNECT,
        Proof.UNPROVEN,
        "passed in a sandbox but returned 'MCP error -32000: Connection closed' "
        "against the real fleet; project-scope control was never demonstrated working",
    ),
)

_UNKNOWN = Affordance(
    ScopeId.CLAUDE_USER,
    LiveOp.STATUS,
    Proof.UNPROVEN,
    "no recorded evidence for this scope/operation pair",
)


def affordance(scope: ScopeId, op: LiveOp) -> Affordance:
    """Look up the recorded affordance, defaulting to UNPROVEN rather than to yes."""
    for entry in AFFORDANCES:
        if entry.scope is scope and entry.op is op:
            return entry
    return Affordance(scope=scope, op=op, proof=_UNKNOWN.proof, note=_UNKNOWN.note)


class ControlError(RuntimeError):
    """A ``subtype: "error"`` control response, or a transport-level failure."""


class Transport(Protocol):
    """The injected session port: write one JSON line, read JSON lines."""

    def send(self, line: str) -> None: ...

    def lines(self) -> Iterator[str]: ...


def session_argv(binary: str, *, strict_config: str | None = None) -> tuple[str, ...]:
    """The exact argv for a control session.

    ``--verbose`` is REQUIRED with ``--output-format stream-json`` under ``-p``.

    ``--strict-mcp-config`` (with an empty config) is the isolation harness for
    experiments -- but it is mutually exclusive with the persistent-config path,
    because a string server spec resolves from the DISK config the flag ignores. So it
    is opt-in and never the default.
    """
    argv = [
        binary,
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "bypassPermissions",
    ]
    if strict_config is not None:
        argv += ["--strict-mcp-config", "--mcp-config", strict_config]
    return tuple(argv)


def kick_frame() -> str:
    """The first user message. Without it the session never emits ``system/init``."""
    return json.dumps(
        {"type": "user", "message": {"role": "user", "content": _KICK_TEXT}}
    )


def control_frame(request_id: str, request: Mapping[str, object]) -> str:
    """Serialise one ``control_request`` as a newline-free JSON line."""
    return json.dumps(
        {"type": "control_request", "request_id": request_id, "request": dict(request)}
    )


@dataclass(frozen=True)
class _Parsed:
    """One decoded inbound frame."""

    request_id: str = ""
    payload: Mapping[str, object] = field(default_factory=dict)
    error: str = ""
    is_control: bool = False


def parse_frame(line: str) -> _Parsed:
    """Decode one inbound line. A non-control or unparseable line is NOT an error.

    Unparseable lines are skipped rather than raised on: the stream carries the
    session's ordinary traffic and a stray partial line must not kill a control run.
    """
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return _Parsed()
    if not isinstance(message, dict):
        return _Parsed()
    envelope = cast("dict[str, object]", message)
    if envelope.get("type") != "control_response":
        return _Parsed()
    inner = envelope.get("response")
    if not isinstance(inner, dict):
        return _Parsed()
    body = cast("dict[str, object]", inner)
    request_id = body.get("request_id") or envelope.get("request_id") or ""
    if body.get("subtype") == "error":
        return _Parsed(
            request_id=str(request_id),
            error=safe(str(body.get("error", "unspecified control error"))),
            is_control=True,
        )
    # DOUBLE nesting, and `response` is optional -- reconnect/toggle omit it entirely.
    payload = body.get("response")
    return _Parsed(
        request_id=str(request_id),
        payload=cast("Mapping[str, object]", payload)
        if isinstance(payload, dict)
        else {},
        is_control=True,
    )


def status_servers(payload: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    """Extract ``mcpServers`` from an ``mcp_status`` payload, null-guarded.

    The un-guarded form is the documented false-negative bug: it renders "no servers"
    for a shape mismatch, which reads as a working probe reporting an empty fleet.
    """
    servers = payload.get("mcpServers")
    if not isinstance(servers, list):
        return ()
    return tuple(
        cast("Mapping[str, object]", s)
        for s in cast("list[object]", servers)
        if isinstance(s, dict)
    )


def liveness_from_status(payload: Mapping[str, object]) -> dict[str, Liveness]:
    """Project an ``mcp_status`` payload onto mcpctl's injected liveness seam.

    ``tools`` is ABSENT for a failed or needs-auth server (measured: 4 of 64 on the
    live fleet). Those rows get ``tool_count=None`` -- "not measured" -- and never
    ``0``: a broken server has an unknown tool count, not zero tools.
    """
    out: dict[str, Liveness] = {}
    for server in status_servers(payload):
        name = server.get("name")
        if not isinstance(name, str):
            continue
        tools = server.get("tools")
        status = server.get("status")
        out[safe(name)] = Liveness(
            tool_count=len(cast("list[object]", tools))
            if isinstance(tools, list)
            else None,
            last_error=safe(str(status))
            if status in ("failed", "needs-auth")
            else None,
        )
    return out


class LiveClient:
    """Correlate control requests with responses over an injected transport."""

    def __init__(
        self,
        transport: Transport,
        *,
        new_id: Callable[[], str],
        max_frames: int = 10_000,
    ) -> None:
        self._transport = transport
        self._new_id = new_id
        self._max_frames = max_frames
        #: Every request line sent, in order. The dry-run test asserts this is EMPTY.
        self.sent: list[str] = []

    def kick(self) -> None:
        """Send the first user message. Must precede any control frame."""
        line = kick_frame()
        self.sent.append(line)
        self._transport.send(line)

    def request(self, request: Mapping[str, object]) -> Mapping[str, object]:
        """Send one control request and return its (possibly empty) payload."""
        request_id = self._new_id()
        line = control_frame(request_id, request)
        self.sent.append(line)
        self._transport.send(line)
        seen = 0
        for raw in self._transport.lines():
            seen += 1
            if seen > self._max_frames:
                break
            parsed = parse_frame(raw)
            if not parsed.is_control or parsed.request_id != request_id:
                continue
            if parsed.error:
                raise ControlError(parsed.error)
            return parsed.payload
        raise ControlError(
            f"no control response for {request_id} before the stream ended; the "
            "session may still be booting (a cold fleet boot measured 104-275 s)"
        )

    def status(self) -> tuple[Mapping[str, object], ...]:
        """List every server the session knows about."""
        return status_servers(self.request({"subtype": LiveOp.STATUS.value}))

    def reconnect(self, name: str) -> None:
        """Reconnect ``name``. Returns no payload; re-issue :meth:`status` to verify."""
        self.request({"subtype": LiveOp.RECONNECT.value, "serverName": name})

    def toggle(self, name: str, *, enabled: bool) -> None:
        """Enable/disable ``name``. THIS WRITES ``~/.claude.json`` -- see the module docstring."""
        self.request(
            {"subtype": LiveOp.TOGGLE.value, "serverName": name, "enabled": enabled}
        )

    def set_dynamic_servers(
        self, servers: Mapping[str, Mapping[str, object]]
    ) -> Mapping[str, object]:
        """REPLACE the dynamically-managed set. Config-scope servers are unaffected."""
        return self.request(
            {
                "subtype": LiveOp.SET_SERVERS.value,
                "servers": {k: dict(v) for k, v in servers.items()},
            }
        )


class _Process(Protocol):
    """The subset of ``Popen`` this transport uses."""

    stdin: object
    stdout: object

    def kill(self) -> None: ...


Spawn = Callable[[Sequence[str], str], _Process]


def default_spawn(argv: Sequence[str], cwd: str) -> _Process:
    """Spawn a real child process with piped stdio.

    ``cwd`` is EXPLICIT, never inherited. ``mcp_toggle`` persists its write to
    ``projects[<the control session's cwd>]``, so a session launched from the GUI's
    own directory would land the disable under the wrong project row.
    """
    return cast(
        "_Process",
        subprocess.Popen(  # noqa: S603 -- argv is built by session_argv, not user text.
            list(argv),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            bufsize=1,
        ),
    )


class SubprocessTransport:
    """The production transport. Newline-delimited JSON over a child's stdio."""

    def __init__(
        self,
        argv: Sequence[str],
        *,
        cwd: str,
        spawn: Spawn = default_spawn,
    ) -> None:
        self._process = spawn(argv, cwd)

    def send(self, line: str) -> None:
        stdin = cast("object", self._process.stdin)
        if stdin is None:
            raise ControlError("the control session has no stdin pipe")
        writer = cast("Callable[[str], object]", getattr(stdin, "write"))
        writer(line + "\n")
        cast("Callable[[], object]", getattr(stdin, "flush"))()

    def lines(self) -> Iterator[str]:
        stdout = self._process.stdout
        if stdout is None:
            raise ControlError("the control session has no stdout pipe")
        for raw in cast("Iterator[str]", stdout):
            yield raw.rstrip("\n")

    def close(self) -> None:
        self._process.kill()
