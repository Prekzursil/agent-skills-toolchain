"""``mcp_source`` — a :class:`~monitorcore.contract.MonitorSource` over the MCP INVENTORY.

The cockpit's MCP pane answers exactly one question: *which MCP servers are declared, in
which config scopes, and which of them a disable list names.* It answers it from the config
documents alone — it never reads a process table, never opens a socket and never performs an
MCP handshake — so every LIVENESS column (``tool_count``, ``last_error``) stays ``None``,
which the pane renders as **not measured**. ``None`` is not ``0`` and not "dead": an
unmeasured tool count must never be painted as a health verdict.

**What this module deliberately does NOT do.** The sibling package ``tools/mcpctl`` resolves
the real five-scope precedence (including the counter-intuitive rule that an approval list
sits *below* both disable lists). Replicating that here would either duplicate a measured
policy or, worse, get it subtly wrong and report a dead server as live. It is also not
importable: ``mcpctl`` is not mirrored into either vendored skill tree, so a static import
would ``ImportError`` in every deployed copy of this package. So this source reports the RAW
facts per document — ``declared_in`` and ``disabled_in`` — and derives only a three-valued
:attr:`McpServer.state` (``enabled`` / ``disabled`` / ``conflict``) that is a faithful
reading of those facts with **no invented precedence**. A name declared in one scope and
disabled in another is reported as ``conflict``, not silently resolved.

``poll`` never raises. When no config document can be read at all, the snapshot is
unreachable and the pane says *not measured* rather than "0 servers". Stdlib-only.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .contract import Alert, Snapshot, SourceState
from .redact import redact
from .report_doc import ReportDoc, Section, Table
from .textsafe import strip_controls

__all__ = [
    "DocInventory",
    "McpPayload",
    "McpServer",
    "McpSource",
    "build_servers",
    "default_paths",
    "parse_doc",
    "read_config",
    "transport_of",
]

_ID = "mcp"


def _scrub(value: object) -> str:
    """Strip control bytes, THEN mask secrets / collapse home paths (fail-closed).

    Same ingest floor and same ORDER as :func:`monitorcore.codex_tail._scrub` — a config
    document is attacker-influenceable (an MCP server name is free text), and stripping
    first stops a spliced control byte from splitting a secret pattern past the mask.
    """
    text = "" if value is None else str(value)
    return redact(strip_controls(text), enabled=True)[0]


@dataclass(frozen=True)
class McpServer:
    """One declared MCP server. Health columns are ``None`` == NOT MEASURED, never ``0``."""

    name: str
    declared_in: tuple[str, ...] = ()
    disabled_in: tuple[str, ...] = ()
    transport: str = "unknown"
    tool_count: int | None = None
    last_error: str | None = None

    @property
    def state(self) -> str:
        """``enabled`` / ``disabled`` / ``conflict`` — a raw reading, never a resolution.

        ``conflict`` means the declaring scopes and the disabling scopes disagree; resolving
        that needs ``mcpctl``'s measured precedence table, which this module does not own.
        """
        if not self.disabled_in:
            return "enabled"
        if set(self.declared_in) <= set(self.disabled_in):
            return "disabled"
        return "conflict"


@dataclass(frozen=True)
class DocInventory:
    """What ONE config document declared (already scrubbed); ``problem`` when it was bad."""

    scope: str
    declared: tuple[tuple[str, str], ...] = ()
    disabled: frozenset[str] = frozenset()
    problem: str = ""


@dataclass(frozen=True)
class McpPayload:
    """Typed per-adapter payload — the merged inventory plus the documents behind it."""

    servers: tuple[McpServer, ...] = ()
    docs_read: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


def default_paths() -> tuple[str, ...]:
    """The config documents an MCP inventory is normally spread across, widest scope first."""
    home = os.path.expanduser("~")
    return (
        os.path.join(home, ".mcp.json"),
        os.path.join(home, ".claude.json"),
        os.path.join(os.getcwd(), ".mcp.json"),
    )


def read_config(path: str) -> str | None:
    """The document's text, or ``None`` when it is absent / unreadable (NOT an error).

    An absent scope is the normal case (few boxes carry all of them), so it yields ``None``
    and is simply skipped; only "no document at all" degrades the whole source.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def transport_of(entry: object) -> str:
    """The server's transport: its declared ``type``/``transport``, else inferred, else unknown."""
    if not isinstance(entry, dict):
        return "unknown"
    declared = entry.get("type") or entry.get("transport")
    if isinstance(declared, str) and declared:
        return _scrub(declared)
    if entry.get("url"):
        return "http"
    if entry.get("command"):
        return "stdio"
    return "unknown"


def parse_doc(scope: str, text: str) -> DocInventory:
    """Fold one config document's text into a scrubbed :class:`DocInventory` (pure).

    A malformed document becomes a ``problem`` row rather than an exception, so one broken
    config never blinds the other scopes.
    """
    label = _scrub(scope)
    try:
        doc = json.loads(text)
    except ValueError as exc:
        return DocInventory(scope=label, problem=_scrub(f"unparsable json: {exc}"))
    if not isinstance(doc, dict):
        return DocInventory(scope=label, problem="not a json object")
    raw_servers = doc.get("mcpServers")
    declared: list[tuple[str, str]] = []
    if isinstance(raw_servers, dict):
        for name, entry in raw_servers.items():
            declared.append((_scrub(name), transport_of(entry)))
    raw_disabled = doc.get("disabledMcpServers")
    names = raw_disabled if isinstance(raw_disabled, list) else []
    disabled = frozenset(_scrub(n) for n in names if isinstance(n, str))
    return DocInventory(
        scope=label, declared=tuple(declared), disabled=disabled, problem=""
    )


def build_servers(docs: Sequence[DocInventory]) -> tuple[McpServer, ...]:
    """Merge per-document inventories into one name-sorted server list (pure).

    A name keeps the FIRST non-``unknown`` transport any document gave it; the declaring and
    disabling scopes accumulate so :attr:`McpServer.state` can report a cross-scope conflict
    instead of picking a winner.
    """
    declared_in: dict[str, list[str]] = {}
    disabled_in: dict[str, list[str]] = {}
    transports: dict[str, str] = {}
    for doc in docs:
        for name, transport in doc.declared:
            declared_in.setdefault(name, []).append(doc.scope)
            if transports.get(name, "unknown") == "unknown":
                transports[name] = transport
        for name in sorted(doc.disabled):
            disabled_in.setdefault(name, []).append(doc.scope)
    names = sorted(set(declared_in) | set(disabled_in))
    return tuple(
        McpServer(
            name=name,
            declared_in=tuple(declared_in.get(name, ())),
            disabled_in=tuple(disabled_in.get(name, ())),
            transport=transports.get(name, "unknown"),
        )
        for name in names
    )


class McpSource:
    """A :class:`~monitorcore.contract.MonitorSource` over the declared MCP inventory."""

    id = _ID

    def __init__(
        self,
        *,
        paths: Sequence[str] | None = None,
        read_text: Callable[[str], str | None] = read_config,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._paths = tuple(paths) if paths else default_paths()
        self._read = read_text
        self._clock = clock
        self._last: Snapshot[McpPayload] | None = None

    # ───────────────────────── poll (never throws) ─────────────────────────
    def poll(self) -> Snapshot[McpPayload]:
        ts = self._clock()
        try:
            docs: list[DocInventory] = []
            for path in self._paths:
                text = self._read(path)
                if text is None:
                    continue
                docs.append(parse_doc(path, text))
        # NEVER raise out of poll (BaseException still propagates by design).
        except Exception as exc:
            return self._unreachable(ts, str(exc))
        if not docs:
            return self._unreachable(ts, "no MCP config document found")

        servers = build_servers(docs)
        problems = tuple(d.problem for d in docs if d.problem)
        payload = McpPayload(
            servers=servers,
            docs_read=tuple(d.scope for d in docs),
            problems=problems,
        )
        state = _derive_state(payload)
        snap = Snapshot(
            source_id=self.id,
            ts=ts,
            reachable=True,
            stale=False,
            state=state,
            headline=_headline(payload, state),
            payload=payload,
            # Config carries NO freshness signal — ``None`` is "not measured", not "0s old".
            age_s=None,
            error=None,
        )
        self._last = snap
        return snap

    def _unreachable(self, ts: float, error: str) -> Snapshot[McpPayload]:
        """A stale/unreachable snapshot retaining the last-good payload (never a fake zero)."""
        payload = self._last.payload if self._last is not None else McpPayload()
        text = _scrub(error)
        snap = Snapshot(
            source_id=self.id,
            ts=ts,
            reachable=False,
            stale=True,
            state=SourceState.UNREACHABLE,
            headline=f"mcp [unreachable] {text}",
            payload=payload,
            age_s=None,
            error=text,
        )
        self._last = snap
        return snap

    # ───────────────────────── contract surface ─────────────────────────
    def render_native(self, snap: Snapshot[McpPayload]) -> object:
        """The mcp-native lines (falls back to the headline when nothing was declared)."""
        servers = snap.payload.servers
        if not servers:
            return snap.headline
        return "\n".join(f"{s.state} {s.name} {s.transport}" for s in servers)

    def export_model(self, snap: Snapshot[McpPayload]) -> ReportDoc:
        """Map the snapshot onto the shared ``ReportDoc`` — ONE inventory table, no health."""
        payload = snap.payload
        generated = datetime.fromtimestamp(snap.ts, tz=timezone.utc).isoformat()
        table = Table(
            headers=("server", "state", "transport", "declared in", "tools"),
            rows=tuple(
                (
                    s.name,
                    s.state,
                    s.transport,
                    " ".join(s.declared_in),
                    "?" if s.tool_count is None else str(s.tool_count),
                )
                for s in payload.servers
            ),
        )
        counts = _counts(payload.servers)
        return ReportDoc(
            title="mcp",
            generated_at=generated,
            blocks=(
                Section(
                    title="declared MCP servers",
                    anchor="mcp-inventory",
                    lead="health columns are NOT MEASURED (config inventory only)",
                    children=(table,),
                ),
            ),
            subtitle=snap.headline,
            meta=(("source", self.id), ("configs", " ".join(payload.docs_read))),
            rollup=(
                ("total", len(payload.servers)),
                ("running", counts["enabled"]),
                ("idle", counts["disabled"]),
                ("error", counts["conflict"]),
            ),
            active=False,
            redaction_mode="strict",
        )

    def headline(self, snap: Snapshot[McpPayload]) -> str:
        """The redaction-safe one-liner (computed at poll time)."""
        return snap.headline

    def alert(self, snap: Snapshot[McpPayload]) -> Alert | None:
        """``error`` → critical, ``unreachable`` / ``stalled`` → warn, else ``None``."""
        if snap.state in (
            SourceState.ERROR,
            SourceState.UNREACHABLE,
            SourceState.STALLED,
        ):
            level = "critical" if snap.state == SourceState.ERROR else "warn"
            return Alert(
                source_id=snap.source_id,
                level=level,
                headline=_scrub(snap.headline),
                detail=_scrub(snap.error or ""),
                ts=snap.ts,
            )
        return None


def _counts(servers: Sequence[McpServer]) -> dict[str, int]:
    """Per-state tallies (always carries every key, so a renderer never KeyErrors)."""
    out = {"enabled": 0, "disabled": 0, "conflict": 0}
    for server in servers:
        out[server.state] = out.get(server.state, 0) + 1
    return out


def _derive_state(payload: McpPayload) -> SourceState:
    """A broken document or a cross-scope conflict is an ``error``; otherwise ``idle``.

    Never ``running``: a config inventory has no work in flight to report.
    """
    if payload.problems or _counts(payload.servers)["conflict"]:
        return SourceState.ERROR
    return SourceState.IDLE


def _headline(payload: McpPayload, state: SourceState) -> str:
    """The one-liner — it says ``health not measured`` out loud so nobody infers a probe."""
    counts = _counts(payload.servers)
    return (
        f"mcp [{state}] {counts['enabled']} enabled / {counts['disabled']} disabled / "
        f"{counts['conflict']} conflict of {len(payload.servers)} declared in "
        f"{len(payload.docs_read)} config(s); health not measured"
    )
