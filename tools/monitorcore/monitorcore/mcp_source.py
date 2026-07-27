"""``mcp_source`` — a :class:`~monitorcore.contract.MonitorSource` over the MCP INVENTORY.

The cockpit's MCP pane answers exactly one question: *which MCP servers are declared, in
which config scopes, and what do the verdict scopes say about them.* It answers it from the
config documents alone — it never reads a process table, never opens a socket and never
performs an MCP handshake — so every LIVENESS column (``tool_count``, ``last_error``) stays
``None``, which the pane renders as **not measured**. ``None`` is not ``0`` and not "dead":
an unmeasured tool count must never be painted as a health verdict.

**Where the scope table comes from.** The sibling package ``tools/mcpctl`` owns the MEASURED
five-scope precedence (``mcpctl/scopes.py``) and the resolver that applies it
(``mcpctl/resolve.py``). It is not importable here — ``mcpctl`` is not mirrored into either
vendored skill tree, so a static import would ``ImportError`` in every deployed copy of this
package — so :data:`PRECEDENCE_NOTE` records the provenance and this module mirrors that
table's SHAPE rather than inventing one:

* every scope that can suppress a server is READ, including the two a naive reader misses —
  ``~/.claude/settings.json → deniedMcpServers`` (a list of **objects**, not strings) and
  ``~/.claude.json → projects[<exact cwd>].disabledMcpServers`` (an ancestor row does NOT
  apply). Skipping either is the single-scope read ``mcpctl/scopes.py`` exists to prevent:
  an unread scope produces no disagreement, so the server silently renders ``enabled``.
* the resolved state is DEFINITE (``enabled`` / ``disabled`` / ``denied`` /
  ``pending-approval`` / ``undefined``) and a scope disagreement is kept as an audit
  ``note``, never as the state and never as an ``ERROR``. Measured on this box,
  ``ghidra-mcp`` / ``hexstrike-ai`` / ``ida-pro-mcp`` appear in ``enabledMcpjsonServers``
  AND in the root ``disabledMcpServers``, and none of the three is live — approval does not
  override a disable. Painting that correctly-curated fleet as a ``critical`` alert every
  tick is alert fatigue, not a signal.

``~/.claude/.mcp-disabled-defaults.json`` is deliberately NOT read: ``mcpctl`` labels it
``ADVISORY`` (a loadout template a tool copies INTO a project list) and never lets it decide
a state, so reading it here could only add noise.

**A document that cannot be parsed is a measurement failure, not a zero.** Its ``problem``
reaches the headline, the pane body and ``snap.error``; the declared-in count reports
``parsed / attempted``; and when NO document parses, the snapshot is unreachable. Silently
dropping 66 servers because one config lost a byte is the failure mode this guards.

``poll`` never raises. Stdlib-only.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .contract import Alert, Snapshot, SourceState
from .redact import scrub
from .report_doc import ReportDoc, Section, Table
from .textsafe import strip_controls

__all__ = [
    "PRECEDENCE_NOTE",
    "STATES",
    "DocInventory",
    "McpPayload",
    "McpServer",
    "McpSource",
    "build_servers",
    "default_paths",
    "parse_doc",
    "read_config",
    "resolve",
    "transport_of",
]

_ID = "mcp"

#: Provenance of the precedence this module mirrors — the drift check for a future reader.
PRECEDENCE_NOTE = (
    "precedence mirrors the MEASURED table in tools/mcpctl/mcpctl/scopes.py "
    "(settings-denied > project-disabled > user-disabled > mcpjson-approved); "
    "the loadout template is advisory and is not read"
)

#: Every state a server can resolve to, in report order. Fixed, so a renderer never KeyErrors.
STATES: tuple[str, ...] = (
    "enabled",
    "disabled",
    "denied",
    "pending-approval",
    "undefined",
)

# The keys each config document may carry. Reading them from EVERY document is deliberate:
# a key that is absent simply yields nothing, and a scope that grows a key later is picked
# up without a code change — the opposite failure mode to a hard-coded per-file key list.
_K_SERVERS = "mcpServers"
_K_DISABLED = "disabledMcpServers"
_K_DENIED = "deniedMcpServers"
_K_APPROVED = "enabledMcpjsonServers"
_K_ENABLE_ALL = "enableAllProjectMcpServers"
_K_PROJECTS = "projects"


@dataclass(frozen=True)
class McpServer:
    """One declared MCP server. Health columns are ``None`` == NOT MEASURED, never ``0``."""

    name: str
    #: Scopes that DEFINE the server (supply its command/url).
    declared_in: tuple[str, ...] = ()
    #: Scopes that SUPPRESS it (a disable list or the host denial list).
    disabled_in: tuple[str, ...] = ()
    #: The resolved state — one of :data:`STATES`, never a bare boolean.
    state: str = "undefined"
    #: The scope labels that produced ``state`` (``mcpctl.resolve.Resolution.basis``).
    basis: tuple[str, ...] = ()
    #: Audit notes — a scope DISAGREEMENT lands here, never in ``state``.
    notes: tuple[str, ...] = ()
    transport: str = "unknown"
    tool_count: int | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class DocInventory:
    """What ONE config document declared (already scrubbed); ``problem`` when it was bad."""

    scope: str
    declared: tuple[tuple[str, str], ...] = ()
    #: ``disabledMcpServers`` at the document ROOT.
    disabled: frozenset[str] = frozenset()
    #: ``projects[<exact cwd>].disabledMcpServers`` — an ancestor row does NOT apply.
    project_disabled: frozenset[str] = frozenset()
    #: ``deniedMcpServers`` — a list of ``{"serverName": ...}`` OBJECTS, not strings.
    denied: frozenset[str] = frozenset()
    #: ``enabledMcpjsonServers`` — the approval list, which sits BELOW both disable lists.
    approved: frozenset[str] = frozenset()
    enable_all: bool = False
    #: True for a ``.mcp.json`` (project-scope definition, subject to approval).
    project_scope: bool = False
    problem: str = ""


@dataclass(frozen=True)
class McpPayload:
    """Typed per-adapter payload — the merged inventory plus the documents behind it."""

    servers: tuple[McpServer, ...] = ()
    #: Documents that PARSED (the only ones whose contents are in ``servers``).
    docs_read: tuple[str, ...] = ()
    #: One entry per document that was found but could NOT be understood.
    problems: tuple[str, ...] = ()
    #: How many documents were opened, parsed or not — the denominator of the count.
    docs_attempted: int = 0


def default_paths(cwd: str | None = None) -> tuple[str, ...]:
    """The MEASURED config scope set, widest first, de-duplicated.

    Mirrors the file column of ``tools/mcpctl/mcpctl/scopes.py``. De-duplication matters:
    when the session's cwd IS the home directory, ``<cwd>/.mcp.json`` and ``~/.mcp.json``
    are the same document, and reading it twice double-counts every scope it declares.
    """
    home = os.path.expanduser("~")
    here = os.getcwd() if cwd is None else cwd
    candidates = (
        os.path.join(home, ".mcp.json"),
        os.path.join(home, ".claude.json"),
        os.path.join(home, ".claude", "settings.json"),
        os.path.join(home, ".claude", "settings.local.json"),
        os.path.join(here, ".mcp.json"),
    )
    seen: dict[str, str] = {}
    for path in candidates:
        seen.setdefault(os.path.normcase(os.path.normpath(path)), path)
    return tuple(seen.values())


def read_config(path: str) -> str | None:
    """The document's text, or ``None`` when it is absent / unreadable (NOT an error).

    An absent scope is the normal case (few boxes carry all of them), so it yields ``None``
    and is simply skipped; only "no document at all" degrades the whole source. An
    unparsable document is a DIFFERENT case — see :func:`parse_doc`.
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
        return scrub(declared)
    if entry.get("url"):
        return "http"
    if entry.get("command"):
        return "stdio"
    return "unknown"


def _names(raw: object) -> frozenset[str]:
    """A ``list[str]`` key folded into a scrubbed name set (anything else yields nothing)."""
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(scrub(n) for n in raw if isinstance(n, str))


def _denied_names(raw: object) -> frozenset[str]:
    """``deniedMcpServers`` folded into a name set — it holds OBJECTS, not strings.

    Measured element shape: ``{"serverName": "markitdown"}``. A reader that treats this key
    as ``list[str]`` yields NOTHING and silently paints every host-denied server ``enabled``
    (``tools/mcp-manager`` has exactly that blind spot). Plain strings are tolerated too, so
    a future shape change degrades to a partial read rather than to zero.
    """
    if not isinstance(raw, list):
        return frozenset()
    out: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            out.add(scrub(item))
        elif isinstance(item, dict):
            name = item.get("serverName")
            if isinstance(name, str):
                out.add(scrub(name))
    return frozenset(out)


def _project_disabled(projects: object, cwd: str) -> frozenset[str]:
    """``projects[<exact cwd>].disabledMcpServers`` — matched on the NORMALISED cwd.

    ``projects`` is keyed by the session's exact working directory and an ancestor row does
    NOT apply, so attributing a parent's list to this session would be wrong in both
    directions. The key is stored in either separator style, hence the normalised compare.
    """
    if not cwd or not isinstance(projects, dict):
        return frozenset()
    want = os.path.normcase(os.path.normpath(cwd))
    for key, row in projects.items():
        if not isinstance(key, str) or not isinstance(row, dict):
            continue
        if os.path.normcase(os.path.normpath(key)) == want:
            return _names(row.get(_K_DISABLED))
    return frozenset()


def parse_doc(scope: str, text: str, *, cwd: str = "") -> DocInventory:
    """Fold one config document's text into a scrubbed :class:`DocInventory` (pure).

    A malformed document becomes a ``problem`` row rather than an exception, so one broken
    config never blinds the other scopes — but the problem is CARRIED, not swallowed.
    """
    label = scrub(scope)
    project_scope = os.path.basename(scope) == ".mcp.json"
    try:
        doc = json.loads(text)
    except ValueError as exc:
        return DocInventory(
            scope=label,
            project_scope=project_scope,
            problem=scrub(f"{label}: unparsable json: {exc}"),
        )
    if not isinstance(doc, dict):
        return DocInventory(
            scope=label,
            project_scope=project_scope,
            problem=f"{label}: not a json object",
        )
    raw_servers = doc.get(_K_SERVERS)
    declared: list[tuple[str, str]] = []
    if isinstance(raw_servers, dict):
        for name, entry in raw_servers.items():
            declared.append((scrub(name), transport_of(entry)))
    return DocInventory(
        scope=label,
        declared=tuple(declared),
        disabled=_names(doc.get(_K_DISABLED)),
        project_disabled=_project_disabled(doc.get(_K_PROJECTS), cwd),
        denied=_denied_names(doc.get(_K_DENIED)),
        approved=_names(doc.get(_K_APPROVED)),
        enable_all=doc.get(_K_ENABLE_ALL) is True,
        project_scope=project_scope,
        problem="",
    )


def resolve(
    *,
    definitions: Sequence[tuple[str, bool]],
    denied_in: Sequence[str],
    project_disabled_in: Sequence[str],
    user_disabled_in: Sequence[str],
    approved: bool,
    enable_all: bool,
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Resolve ONE server to ``(state, basis, notes)`` — pure, no ambient state.

    Mirrors ``mcpctl.resolve.resolve_state``; see :data:`PRECEDENCE_NOTE`. ``definitions`` is
    ``(scope_label, is_project_scope)`` per defining document. The one counter-intuitive step
    is that approval sits BELOW both disable lists — a disagreement becomes a ``note``.
    """
    notes: list[str] = []
    suppressors = (
        tuple(f"{s}:{_K_DENIED}" for s in denied_in)
        + tuple(f"{s}:projects[cwd].{_K_DISABLED}" for s in project_disabled_in)
        + tuple(f"{s}:{_K_DISABLED}" for s in user_disabled_in)
    )
    if suppressors:
        if approved:
            notes.append(
                f"approved in {_K_APPROVED} but suppressed by "
                f"{', '.join(suppressors)}; MEASURED on this box the suppression wins"
            )
        state = "denied" if denied_in else "disabled"
        return state, suppressors, tuple(notes)
    if not definitions:
        notes.append("named by a verdict scope but defined by none")
        return "undefined", (), tuple(notes)
    basis = tuple(f"{label}:{_K_SERVERS}" for label, _ in definitions)
    project_only = all(is_project for _, is_project in definitions)
    if project_only and not approved and not enable_all:
        notes.append(
            f"project-scope definition awaiting approval "
            f"(absent from {_K_APPROVED}, {_K_ENABLE_ALL} is false)"
        )
        return "pending-approval", basis, tuple(notes)
    return "enabled", basis, tuple(notes)


def build_servers(docs: Sequence[DocInventory]) -> tuple[McpServer, ...]:
    """Merge per-document inventories into one name-sorted, RESOLVED server list (pure).

    A name keeps the FIRST non-``unknown`` transport any document gave it. Only documents
    that PARSED contribute — a ``problem`` document is surfaced separately rather than being
    read as "declares nothing", which would understate the fleet.
    """
    definitions: dict[str, list[tuple[str, bool]]] = {}
    denied: dict[str, list[str]] = {}
    proj_off: dict[str, list[str]] = {}
    user_off: dict[str, list[str]] = {}
    transports: dict[str, str] = {}
    approved: set[str] = set()
    enable_all = False
    for doc in docs:
        if doc.problem:
            continue
        for name, transport in doc.declared:
            definitions.setdefault(name, []).append((doc.scope, doc.project_scope))
            if transports.get(name, "unknown") == "unknown":
                transports[name] = transport
        for bucket, source in (
            (denied, doc.denied),
            (proj_off, doc.project_disabled),
            (user_off, doc.disabled),
        ):
            for name in sorted(source):
                bucket.setdefault(name, []).append(doc.scope)
        approved |= doc.approved
        enable_all = enable_all or doc.enable_all
    # ``approved`` is folded into the NAME set too: an approval that names a server no
    # scope defines is a stale entry worth surfacing (mcpctl's ``UNDEFINED``), and dropping
    # it would make that state unreachable rather than absent.
    names = sorted(
        set(definitions) | set(denied) | set(proj_off) | set(user_off) | approved
    )
    out: list[McpServer] = []
    for name in names:
        defs = definitions.get(name, [])
        state, basis, notes = resolve(
            definitions=defs,
            denied_in=denied.get(name, ()),
            project_disabled_in=proj_off.get(name, ()),
            user_disabled_in=user_off.get(name, ()),
            approved=name in approved,
            enable_all=enable_all,
        )
        out.append(
            McpServer(
                name=name,
                declared_in=tuple(label for label, _ in defs),
                disabled_in=(
                    tuple(denied.get(name, ()))
                    + tuple(proj_off.get(name, ()))
                    + tuple(user_off.get(name, ()))
                ),
                state=state,
                basis=basis,
                notes=notes,
                transport=transports.get(name, "unknown"),
            )
        )
    return tuple(out)


class McpSource:
    """A :class:`~monitorcore.contract.MonitorSource` over the declared MCP inventory."""

    id = _ID

    def __init__(
        self,
        *,
        paths: Sequence[str] | None = None,
        cwd: str | None = None,
        read_text: Callable[[str], str | None] = read_config,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._cwd = os.getcwd() if cwd is None else cwd
        self._paths = tuple(paths) if paths else default_paths(self._cwd)
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
                docs.append(parse_doc(path, text, cwd=self._cwd))
        # NEVER raise out of poll (BaseException still propagates by design).
        except Exception as exc:
            return self._unreachable(ts, str(exc))
        if not docs:
            return self._unreachable(ts, "no MCP config document found")
        problems = tuple(d.problem for d in docs if d.problem)
        if len(problems) == len(docs):
            # Every document was found but NONE could be understood: nothing was measured,
            # so the pane must say "not measured" rather than print a confident zero.
            return self._unreachable(ts, "; ".join(problems))

        payload = McpPayload(
            servers=build_servers(docs),
            docs_read=tuple(d.scope for d in docs if not d.problem),
            problems=problems,
            docs_attempted=len(docs),
        )
        state = SourceState.ERROR if problems else SourceState.IDLE
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
            # A partial read is a MEASUREMENT FAILURE, so it reaches the badge's ``err=``
            # instead of hiding behind a bare ``[error]`` token.
            error="; ".join(problems) if problems else None,
        )
        self._last = snap
        return snap

    def _unreachable(self, ts: float, error: str) -> Snapshot[McpPayload]:
        """A stale/unreachable snapshot retaining the last-good payload (never a fake zero)."""
        payload = self._last.payload if self._last is not None else McpPayload()
        text = scrub(error)
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
        """Map the snapshot onto the shared ``ReportDoc`` — ONE inventory table, no health.

        ``rollup`` is EMPTY on purpose. The shared rollup line is agent-shaped
        (``total/done/error/running/idle/tokens``) and a config inventory measures none of
        those: mapping ``enabled -> running`` would claim N servers are running when not one
        was probed. Both renderers already skip the line when ``rollup`` is empty, and the
        honest counts live in ``subtitle`` (the headline) and in the table.
        """
        payload = snap.payload
        generated = datetime.fromtimestamp(snap.ts, tz=timezone.utc).isoformat()
        table = Table(
            headers=("server", "state", "transport", "basis", "tools", "notes"),
            rows=tuple(
                (
                    s.name,
                    s.state,
                    s.transport,
                    " ".join(s.basis),
                    "?" if s.tool_count is None else str(s.tool_count),
                    "; ".join(s.notes),
                )
                for s in payload.servers
            ),
        )
        blocks: tuple[Section, ...] = (
            Section(
                title="declared MCP servers",
                anchor="mcp-inventory",
                lead="health columns are NOT MEASURED (config inventory only); "
                + PRECEDENCE_NOTE,
                children=(table,),
            ),
        )
        if payload.problems:
            blocks += (
                Section(
                    title="unreadable config documents",
                    anchor="mcp-problems",
                    lead="these scopes were found but could NOT be parsed — the inventory "
                    "above is PARTIAL",
                    children=(
                        Table(
                            headers=("problem",),
                            rows=tuple((p,) for p in payload.problems),
                        ),
                    ),
                ),
            )
        return ReportDoc(
            title="mcp",
            generated_at=generated,
            blocks=blocks,
            subtitle=snap.headline,
            meta=(("source", self.id), ("configs", " ".join(payload.docs_read))),
            rollup=(),
            active=False,
            redaction_mode="strict",
        )

    def headline(self, snap: Snapshot[McpPayload]) -> str:
        """The redaction-safe one-liner (computed at poll time)."""
        return snap.headline

    def alert(self, snap: Snapshot[McpPayload]) -> Alert | None:
        """``error`` → critical, ``unreachable`` / ``stalled`` → warn, else ``None``.

        ``error`` here means a config document could not be READ — a real measurement
        failure. A cross-scope DISAGREEMENT is never an error: it is resolved by the
        measured precedence and recorded in :attr:`McpServer.notes`.
        """
        if snap.state in (
            SourceState.ERROR,
            SourceState.UNREACHABLE,
            SourceState.STALLED,
        ):
            level = "critical" if snap.state == SourceState.ERROR else "warn"
            return Alert(
                source_id=snap.source_id,
                level=level,
                headline=scrub(snap.headline),
                detail=scrub(snap.error or ""),
                ts=snap.ts,
            )
        return None


def _counts(servers: Sequence[McpServer]) -> dict[str, int]:
    """Per-state tallies (always carries every key, so a renderer never KeyErrors)."""
    out = dict.fromkeys(STATES, 0)
    for server in servers:
        out[server.state] = out.get(server.state, 0) + 1
    return out


def _headline(payload: McpPayload, state: SourceState) -> str:
    """The one-liner — it says ``health not measured`` out loud so nobody infers a probe.

    ``configs R/A`` is READ over ATTEMPTED, so a document that failed to parse shrinks the
    numerator instead of vanishing; ``UNREADABLE`` then names how many, because "20 enabled"
    over a partial read is a narrower claim than it looks.
    """
    counts = _counts(payload.servers)
    bad = len(payload.problems)
    warn = f" ({bad} UNREADABLE)" if bad else ""
    return strip_controls(
        f"mcp [{state}] {len(payload.servers)} declared: {counts['enabled']} enabled/"
        f"{counts['disabled']} disabled/{counts['denied']} denied/"
        f"{counts['pending-approval']} pending/{counts['undefined']} undefined; "
        f"configs {len(payload.docs_read)}/{payload.docs_attempted}{warn}; "
        "health not measured"
    )
