"""PURE mutation planning: current state -> desired state -> an explicit diff.

Nothing here touches the filesystem, spawns a process, or opens a socket. A
:class:`Plan` is a value: it can be built, rendered, diffed and asserted on with no
side effect whatsoever, and :mod:`mcpapply.apply` is the only module that turns one
into bytes on disk.

The INVERSE SCOPE MAP
---------------------
:mod:`mcpctl.scopes` models READ precedence -- "given these scopes, what state wins".
Mutation needs the inverse: "to reach state X for server S, which scope do I write?".
The two must never disagree, so the inverse is DERIVED from
:data:`mcpctl.scopes.PRECEDENCE` rather than restated:

* :data:`SUPPRESSORS` is ``PRECEDENCE`` filtered to the scopes that actually suppress
  a server, in the same authority order.
* **Disabling needs ONE suppressor.** Any single one wins, so the planner writes the
  most effective one it can (see :data:`SPAWN_PREVENTING`).
* **Enabling needs ALL of them cleared.** A remove from one suppressor while another
  still lists the server is a no-op the operator will read as a failure, so
  :func:`plan_enable` emits one edit per suppressing scope and says so.

MEASURED, and the reason ``disable`` prefers the project row (scout A/B, 2026-07-27,
sandboxed ``CLAUDE_CONFIG_DIR``, single variable):

* ``projects[<exact cwd>].disabledMcpServers`` -> the server process is NOT spawned.
* root ``disabledMcpServers``                  -> the process IS still spawned.

So a disable written to the root list is a real disable of the TOOL SURFACE but buys
no RAM. :mod:`mcpapply.impact` reads :data:`SPAWN_PREVENTING` to keep that honest
instead of crediting every disable with a saving.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

from mcpctl.resolve import Resolution, State, resolve_topology
from mcpctl.safety import safe
from mcpctl.scopes import PRECEDENCE, ScopeId
from mcpctl.topology import Topology

__all__ = [
    "DISABLE_PREFERENCE",
    "Change",
    "Edit",
    "Intent",
    "Op",
    "Plan",
    "SPAWN_PREVENTING",
    "SUPPRESSORS",
    "SCOPE_FILE_LABEL",
    "plan_add",
    "plan_disable",
    "plan_edit",
    "plan_enable",
    "plan_reconnect",
    "plan_remove",
    "render_plan",
]


class Intent(str, Enum):
    """What the operator asked for, independent of which scopes get written."""

    ENABLE = "enable"
    DISABLE = "disable"
    ADD = "add"
    REMOVE = "remove"
    EDIT = "edit"
    RECONNECT = "reconnect"


class Op(str, Enum):
    """The shape of ONE key-level mutation inside a configuration document."""

    #: Append a name to a ``list[str]`` if absent.
    LIST_ADD = "list-add"
    #: Drop a name from a ``list[str]`` if present.
    LIST_REMOVE = "list-remove"
    #: Set ``mapping[name]`` to a spec object.
    MAP_SET = "map-set"
    #: Delete ``mapping[name]`` if present.
    MAP_DELETE = "map-delete"
    #: Nothing is written; the change is carried out over the live control channel.
    LIVE_ONLY = "live-only"


#: Verdict scopes that SUPPRESS, in authority order. Derived from the measured read
#: precedence so a write can never target a scope the reader would ignore.
SUPPRESSORS: tuple[ScopeId, ...] = tuple(
    s
    for s in PRECEDENCE
    if s
    in {
        ScopeId.SETTINGS_DENIED,
        ScopeId.CLAUDE_PROJECT_DISABLED,
        ScopeId.CLAUDE_USER_DISABLED,
    }
)

#: The suppressors MEASURED to stop the server process from being spawned at the next
#: session start. Root ``disabledMcpServers`` is deliberately ABSENT: the controlled
#: A/B showed the process still spawns, so a disable written there saves no memory.
SPAWN_PREVENTING: frozenset[ScopeId] = frozenset(
    {ScopeId.SETTINGS_DENIED, ScopeId.CLAUDE_PROJECT_DISABLED}
)

#: Which suppressor the planner writes for a plain ``disable``, best first. The
#: settings-denied scope is NOT offered: it is the host's own denial list and stealing
#: it for routine curation would make an operator's disable indistinguishable from a
#: policy denial.
DISABLE_PREFERENCE: tuple[ScopeId, ...] = (
    ScopeId.CLAUDE_PROJECT_DISABLED,
    ScopeId.CLAUDE_USER_DISABLED,
)

#: Which source document owns each scope. Labels match
#: :meth:`mcpctl.sources.SourcePaths.as_tuple`.
SCOPE_FILE_LABEL: Mapping[ScopeId, str] = {
    ScopeId.CLAUDE_USER: "claude_json",
    ScopeId.CLAUDE_USER_DISABLED: "claude_json",
    ScopeId.CLAUDE_PROJECT_DISABLED: "claude_json",
    ScopeId.MCP_JSON: "mcp_json",
    ScopeId.MCPJSON_APPROVED: "settings_local",
    ScopeId.SETTINGS_DENIED: "settings",
    ScopeId.LOADOUT_TEMPLATE: "disabled_defaults",
}


@dataclass(frozen=True)
class Edit:
    """ONE key-level mutation of ONE configuration document."""

    scope: ScopeId
    label: str
    #: Keys from the document root down to the container being mutated.
    key_path: tuple[str, ...]
    op: Op
    server: str
    #: A spec mapping for :attr:`Op.MAP_SET`; ``None`` for every other op.
    spec: Mapping[str, object] | None = None

    def describe(self) -> str:
        """One human-readable diff line, e.g. ``+ claude_json projects[..] ...``."""
        sign = {
            Op.LIST_ADD: "+",
            Op.MAP_SET: "+",
            Op.LIST_REMOVE: "-",
            Op.MAP_DELETE: "-",
            Op.LIVE_ONLY: "~",
        }[self.op]
        where = ".".join(self.key_path) if self.key_path else "(root)"
        return f"{sign} {self.label}:{where} [{self.scope.value}] {self.server}"


@dataclass(frozen=True)
class Change:
    """One operator-level intent, plus the edits and caveats it expands into."""

    intent: Intent
    server: str
    edits: tuple[Edit, ...] = ()
    warnings: tuple[str, ...] = ()
    #: State before the change, as resolved from the current topology.
    before: str = State.UNDEFINED.value

    @property
    def touches_disk(self) -> bool:
        """True when at least one edit writes a configuration file."""
        return any(e.op is not Op.LIVE_ONLY for e in self.edits)


@dataclass(frozen=True)
class Plan:
    """An ordered set of changes. Immutable, printable, and safe to hand around."""

    changes: tuple[Change, ...] = ()
    #: The ``projects[]`` key the plan was built for; ``None`` = no project scope.
    project_key: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def empty(self) -> bool:
        """True when the plan would change nothing -- already-in-desired-state."""
        return not any(c.edits for c in self.changes)

    def labels(self) -> tuple[str, ...]:
        """Every source label this plan writes, sorted and deduplicated."""
        return tuple(
            sorted(
                {
                    e.label
                    for c in self.changes
                    for e in c.edits
                    if e.op is not Op.LIVE_ONLY
                }
            )
        )

    def warnings(self) -> tuple[str, ...]:
        """Every caveat across every change, in order, deduplicated."""
        out: list[str] = []
        for change in self.changes:
            for warning in change.warnings:
                if warning not in out:
                    out.append(warning)
        return tuple(out)

    def to_dict(self) -> dict[str, object]:
        return {
            "project_key": self.project_key,
            "empty": self.empty,
            "labels": list(self.labels()),
            "notes": list(self.notes),
            "warnings": list(self.warnings()),
            "changes": [
                {
                    "intent": c.intent.value,
                    "server": c.server,
                    "before": c.before,
                    "warnings": list(c.warnings),
                    "edits": [
                        {
                            "scope": e.scope.value,
                            "label": e.label,
                            "key_path": list(e.key_path),
                            "op": e.op.value,
                            "server": e.server,
                            "describe": e.describe(),
                        }
                        for e in c.edits
                    ],
                }
                for c in self.changes
            ],
        }


_NO_PROJECT_ROW = (
    "no projects[] row for this cwd, so the project-scope disable (the one MEASURED to "
    "stop the process spawning) is unavailable; falling back to the root list, which "
    "hides the tools but does NOT prevent the spawn"
)

_DENIED_NOTE = (
    "this server is in settings.json -> deniedMcpServers, whose elements are OBJECTS "
    '({"serverName": ...}); the edit removes the matching object, not a bare string'
)

_ENABLE_MULTI = (
    "more than one scope suppresses this server: EVERY one must be cleared or the "
    "server stays off, which reads as a failed enable"
)


def _resolution_of(top: Topology, name: str) -> Resolution:
    return resolve_topology(top).get(name, Resolution(state=State.UNDEFINED))


def _project_path(project_key: str) -> tuple[str, ...]:
    return ("projects", project_key, "disabledMcpServers")


def _suppressor_edit(
    scope: ScopeId, name: str, project_key: str | None, op: Op
) -> Edit | None:
    """Build the edit that adds/removes ``name`` in ``scope``, or ``None``."""
    if scope is ScopeId.CLAUDE_PROJECT_DISABLED:
        if project_key is None:
            return None
        key_path = _project_path(project_key)
    elif scope is ScopeId.CLAUDE_USER_DISABLED:
        key_path = ("disabledMcpServers",)
    else:
        key_path = ("deniedMcpServers",)
    return Edit(
        scope=scope,
        label=SCOPE_FILE_LABEL[scope],
        key_path=key_path,
        op=op,
        server=name,
    )


_NO_RAM_SAVING = (
    "this disable lands in a scope MEASURED not to prevent the process spawn: the "
    "tools go away, the memory does not"
)

_ORPHAN_PROJECT_MENTION = (
    "a project-scope suppression is recorded but the topology carries no projects[] "
    "key, so that scope cannot be cleared; re-run with the exact cwd"
)

_EMPTY_SPEC = (
    "refusing to {verb} {name!r} with an EMPTY spec: an empty object is not a server "
    "definition (it names no command, url or type), and writing one REPLACES the "
    "existing definition -- command, args and the whole env block -- with nothing. "
    "Pass the definition with --spec '{{...}}'. To delete a server, use `remove`."
)


def _require_spec(spec: Mapping[str, object], *, verb: str, name: str) -> None:
    """Reject an empty definition spec.

    The wipe this prevents is one word wide: ``mcpapply edit cloud-hub --apply`` with
    no ``--spec`` defaulted to ``{}`` and replaced a live definition with an empty
    object while reporting success. The curation is LOAD-BEARING, so a destructive
    no-argument default must REFUSE, not warn.
    """
    if not spec:
        raise ValueError(_EMPTY_SPEC.format(verb=verb, name=name))


def plan_disable(top: Topology, name: str) -> Change:
    """Plan a disable: ONE suppressor, preferring the spawn-preventing project row."""
    safe_name = safe(name)
    resolution = _resolution_of(top, safe_name)
    if resolution.state in (State.DISABLED, State.DENIED):
        return Change(
            intent=Intent.DISABLE,
            server=safe_name,
            warnings=("already suppressed; nothing to write",),
            before=resolution.state.value,
        )
    warnings: list[str] = []
    writable = {
        ScopeId.CLAUDE_PROJECT_DISABLED: top.project_key is not None,
        ScopeId.CLAUDE_USER_DISABLED: True,
    }
    scope = next(s for s in DISABLE_PREFERENCE if writable[s])
    if scope is not ScopeId.CLAUDE_PROJECT_DISABLED:
        warnings.append(_NO_PROJECT_ROW)
    if scope not in SPAWN_PREVENTING:
        warnings.append(_NO_RAM_SAVING)
    edit = _suppressor_edit(scope, safe_name, top.project_key, Op.LIST_ADD)
    return Change(
        intent=Intent.DISABLE,
        server=safe_name,
        edits=() if edit is None else (edit,),
        warnings=tuple(warnings),
        before=resolution.state.value,
    )


def plan_enable(top: Topology, name: str) -> Change:
    """Plan an enable: clear the name from EVERY suppressing scope, not just one."""
    safe_name = safe(name)
    resolution = _resolution_of(top, safe_name)
    mentioned = set(top.mentions_of(safe_name))
    hits = tuple(s for s in SUPPRESSORS if s in mentioned)
    if not hits:
        return Change(
            intent=Intent.ENABLE,
            server=safe_name,
            warnings=("no scope suppresses this server; nothing to write",),
            before=resolution.state.value,
        )
    edits: list[Edit] = []
    warnings: list[str] = []
    if len(hits) > 1:
        warnings.append(_ENABLE_MULTI)
    for scope in hits:
        if scope is ScopeId.SETTINGS_DENIED:
            warnings.append(_DENIED_NOTE)
        edit = _suppressor_edit(scope, safe_name, top.project_key, Op.LIST_REMOVE)
        if edit is None:
            warnings.append(_ORPHAN_PROJECT_MENTION)
            continue
        edits.append(edit)
    return Change(
        intent=Intent.ENABLE,
        server=safe_name,
        edits=tuple(edits),
        warnings=tuple(warnings),
        before=resolution.state.value,
    )


def plan_add(
    top: Topology, name: str, spec: Mapping[str, object], *, scope: ScopeId
) -> Change:
    """Plan adding a server DEFINITION to ``claude-user`` or ``mcp-json``."""
    safe_name = safe(name)
    resolution = _resolution_of(top, safe_name)
    if scope not in (ScopeId.CLAUDE_USER, ScopeId.MCP_JSON):
        raise ValueError(
            f"a definition can only be added to {ScopeId.CLAUDE_USER.value} or "
            f"{ScopeId.MCP_JSON.value}, not {scope.value}"
        )
    _require_spec(spec, verb="add", name=safe_name)
    warnings: list[str] = []
    if top.spec_of(safe_name) is not None:
        warnings.append("a definition already exists; this REPLACES it")
    if scope is ScopeId.MCP_JSON and safe_name not in top.approved_mcpjson:
        warnings.append(
            "a .mcp.json definition starts pending-approval until it is listed in "
            "settings.local.json -> enabledMcpjsonServers"
        )
    return Change(
        intent=Intent.ADD,
        server=safe_name,
        edits=(
            Edit(
                scope=scope,
                label=SCOPE_FILE_LABEL[scope],
                key_path=("mcpServers",),
                op=Op.MAP_SET,
                server=safe_name,
                spec=spec,
            ),
        ),
        warnings=tuple(warnings),
        before=resolution.state.value,
    )


def plan_remove(top: Topology, name: str) -> Change:
    """Plan removing a server definition from EVERY definition scope that carries it."""
    safe_name = safe(name)
    resolution = _resolution_of(top, safe_name)
    scopes = top.scopes_of(safe_name)
    if not scopes:
        return Change(
            intent=Intent.REMOVE,
            server=safe_name,
            warnings=("no definition scope defines this server; nothing to write",),
            before=resolution.state.value,
        )
    return Change(
        intent=Intent.REMOVE,
        server=safe_name,
        edits=tuple(
            Edit(
                scope=scope,
                label=SCOPE_FILE_LABEL[scope],
                key_path=("mcpServers",),
                op=Op.MAP_DELETE,
                server=safe_name,
            )
            for scope in scopes
        ),
        warnings=(
            "removing the definition does NOT clear the curation lists that mention it; "
            "run `enable` first if you want a clean removal",
        )
        if top.mentions_of(safe_name)
        else (),
        before=resolution.state.value,
    )


def plan_edit(top: Topology, name: str, spec: Mapping[str, object]) -> Change:
    """Plan replacing an existing definition in place, in its own definition scope."""
    safe_name = safe(name)
    resolution = _resolution_of(top, safe_name)
    _require_spec(spec, verb="edit", name=safe_name)
    scopes = top.scopes_of(safe_name)
    if not scopes:
        return Change(
            intent=Intent.EDIT,
            server=safe_name,
            warnings=("no definition to edit; use `add` instead",),
            before=resolution.state.value,
        )
    scope = scopes[0]
    return Change(
        intent=Intent.EDIT,
        server=safe_name,
        edits=(
            Edit(
                scope=scope,
                label=SCOPE_FILE_LABEL[scope],
                key_path=("mcpServers",),
                op=Op.MAP_SET,
                server=safe_name,
                spec=spec,
            ),
        ),
        warnings=(
            "this REPLACES the whole definition -- command, args and env are taken "
            "from --spec, not merged into what is there now",
            "editing a definition takes effect at the NEXT session start unless "
            "it is followed by a live mcp_reconnect",
        )
        if len(scopes) == 1
        else (
            f"defined in {len(scopes)} scopes; only the first ({scope.value}) is edited",
        ),
        before=resolution.state.value,
    )


def plan_reconnect(top: Topology, name: str) -> Change:
    """Plan a live-only reconnect. Writes nothing; needs a live control session."""
    safe_name = safe(name)
    resolution = _resolution_of(top, safe_name)
    return Change(
        intent=Intent.RECONNECT,
        server=safe_name,
        edits=(
            Edit(
                scope=ScopeId.CLAUDE_USER,
                label="(live)",
                key_path=(),
                op=Op.LIVE_ONLY,
                server=safe_name,
            ),
        ),
        warnings=(
            "reconnect needs a control session this tool OWNS; a session whose stdin is "
            "an interactive TTY cannot be reached by any local channel",
        ),
        before=resolution.state.value,
    )


def build_plan(changes: Sequence[Change], *, project_key: str | None) -> Plan:
    """Collect changes into a plan, attaching the standing operator notes."""
    notes = [
        "DRY RUN by default: nothing is written and no control frame is sent without "
        "an explicit --apply.",
    ]
    if any(c.touches_disk for c in changes):
        notes.append(
            "three SessionStart hooks in this repo also write MCP config "
            "(mcp-defaults, mcp-canonical-sync, mcp-userscope-sync); an edit they own "
            "can be re-applied over this one at the next session start"
        )
    return Plan(changes=tuple(changes), project_key=project_key, notes=tuple(notes))


def render_plan(plan: Plan) -> str:
    """Render the plan as a plain-text diff. No ANSI, no control bytes."""
    lines: list[str] = []
    if plan.empty:
        lines.append("plan is EMPTY -- every requested change is already in effect")
    for change in plan.changes:
        lines.append(
            f"{change.intent.value.upper()} {change.server} (was: {change.before})"
        )
        for edit in change.edits:
            lines.append(f"    {edit.describe()}")
        for warning in change.warnings:
            lines.append(f"    ! {warning}")
    for note in plan.notes:
        lines.append(f"note: {note}")
    return "\n".join(lines)
