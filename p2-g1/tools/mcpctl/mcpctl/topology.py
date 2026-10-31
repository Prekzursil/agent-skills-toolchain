"""PURE parsing of the MCP configuration topology.

Every function here takes an already-loaded ``dict``/``list``/``str`` and returns
immutable records. There is no filesystem access, no ``os.environ`` read, and no
subprocess: :mod:`mcpctl.sources` owns the one thin read shim. That split is what lets
this module be exercised to 100% line+branch from fixtures alone.

Two hard rules the parsers enforce:

* **A credential value is never captured.** ``env`` blocks go through
  :func:`mcpctl.safety.env_fields`, which yields ``(name, kind)`` pairs only. A token
  cannot leak from a record that never held it.
* **A malformed config degrades, never raises.** A hand-edited config with a string
  where a mapping belongs still produces a row -- flagged ``malformed`` -- because a
  read-only inventory that crashes on the one broken server is useless exactly when
  the operator needs it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from mcpctl.safety import EnvField, env_fields, safe, strip_controls
from mcpctl.scopes import ScopeId

__all__ = [
    "ServerSpec",
    "SourceDocs",
    "Topology",
    "build_topology",
    "parse_denied_list",
    "parse_name_list",
    "parse_server_specs",
    "project_row",
]


@dataclass(frozen=True)
class ServerSpec:
    """A server definition, with every free-text field already made safe."""

    name: str
    transport: str
    command: str = ""
    args: tuple[str, ...] = ()
    url_present: bool = False
    env_fields: tuple[EnvField, ...] = ()
    #: True when the raw spec was not a mapping (e.g. a stray string in the config).
    malformed: bool = False


@dataclass(frozen=True)
class SourceDocs:
    """The five loaded configuration documents. ``None`` = file absent or unparseable."""

    claude_json: object = None
    mcp_json: object = None
    settings: object = None
    settings_local: object = None
    disabled_defaults: object = None


@dataclass(frozen=True)
class Topology:
    """Per-server definition scopes + verdict-scope mentions, plus the approval switches."""

    specs: Mapping[str, ServerSpec] = field(default_factory=dict)
    definitions: Mapping[str, tuple[ScopeId, ...]] = field(default_factory=dict)
    mentions: Mapping[str, tuple[ScopeId, ...]] = field(default_factory=dict)
    project_key: str | None = None
    project_row_found: bool = False
    approved_mcpjson: tuple[str, ...] = ()
    enable_all_project_servers: bool = False

    def names(self) -> tuple[str, ...]:
        """Every server name known to ANY scope, sorted and deduplicated."""
        return tuple(sorted(set(self.definitions) | set(self.mentions)))

    def scopes_of(self, name: str) -> tuple[ScopeId, ...]:
        """Definition scopes for ``name`` (empty when it is only ever mentioned)."""
        return self.definitions.get(name, ())

    def mentions_of(self, name: str) -> tuple[ScopeId, ...]:
        """Verdict scopes that name ``name``."""
        return self.mentions.get(name, ())

    def spec_of(self, name: str) -> ServerSpec | None:
        """The definition for ``name``, or ``None`` for a mention-only name."""
        return self.specs.get(name)


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return cast("Mapping[str, object]", value)
    return {}


def _transport_of(spec: Mapping[str, object]) -> str:
    declared = spec.get("type")
    if isinstance(declared, str) and declared:
        return strip_controls(declared)
    if "command" in spec:
        return "stdio"
    if "url" in spec:
        return "http"
    return "unknown"


def parse_server_specs(container: object) -> dict[str, ServerSpec]:
    """Parse an ``mcpServers`` mapping into safe :class:`ServerSpec` records."""
    out: dict[str, ServerSpec] = {}
    for raw_name, raw_spec in _as_mapping(container).items():
        name = strip_controls(str(raw_name))
        if not isinstance(raw_spec, Mapping):
            out[name] = ServerSpec(name=name, transport="unknown", malformed=True)
            continue
        spec = cast("Mapping[str, object]", raw_spec)
        raw_args = spec.get("args")
        args: tuple[str, ...] = ()
        if isinstance(raw_args, list):
            args = tuple(safe(str(a)) for a in cast("list[object]", raw_args))
        out[name] = ServerSpec(
            name=name,
            transport=_transport_of(spec),
            command=safe(str(spec.get("command", ""))),
            args=args,
            url_present="url" in spec,
            env_fields=env_fields(spec.get("env")),
        )
    return out


def parse_name_list(value: object) -> tuple[str, ...]:
    """Parse a ``list[str]`` of server names, dropping any non-string element."""
    if not isinstance(value, list):
        return ()
    return tuple(
        strip_controls(item)
        for item in cast("list[object]", value)
        if isinstance(item, str)
    )


def parse_denied_list(value: object) -> tuple[str, ...]:
    """Parse ``deniedMcpServers``, whose elements are OBJECTS on this box.

    Measured element shape: ``{"serverName": "markitdown"}``. A bare string element is
    also accepted so a hand-edited file still reads, and an object without
    ``serverName`` is dropped rather than turning into ``"None"``.
    """
    if not isinstance(value, list):
        return ()
    names: list[str] = []
    for item in cast("list[object]", value):
        if isinstance(item, str):
            names.append(strip_controls(item))
        elif isinstance(item, Mapping):
            server = cast("Mapping[str, object]", item).get("serverName")
            if isinstance(server, str):
                names.append(strip_controls(server))
    return tuple(names)


def project_row(
    claude_doc: object, project_key: str | None
) -> tuple[Mapping[str, object], bool]:
    """Return ``(row, found)`` for the EXACT ``project_key`` -- never an ancestor.

    Claude Code keys ``projects`` by the session's exact cwd, so an ancestor row must
    not be attributed to a deeper directory. Measured on this box: cwd
    ``.../agent-worktrees/agent-364079870`` has no row while its ancestor
    ``C:/Users/Prekzursil`` carries 117 disabled names -- a different project entirely.
    Backslashes are normalised because the stored keys use forward slashes.
    """
    if project_key is None:
        return {}, False
    projects = _as_mapping(_as_mapping(claude_doc).get("projects"))
    key = project_key.replace("\\", "/")
    if key not in projects:
        return {}, False
    return _as_mapping(projects[key]), True


def build_topology(docs: SourceDocs, *, project_key: str | None) -> Topology:
    """Fold the five documents into one scope-qualified topology."""
    claude = _as_mapping(docs.claude_json)
    mcp_json = _as_mapping(docs.mcp_json)
    settings = _as_mapping(docs.settings)
    settings_local = _as_mapping(docs.settings_local)
    defaults = _as_mapping(docs.disabled_defaults)

    user_specs = parse_server_specs(claude.get("mcpServers"))
    project_specs = parse_server_specs(mcp_json.get("mcpServers"))

    definitions: dict[str, list[ScopeId]] = {}
    specs: dict[str, ServerSpec] = {}
    for scope, parsed in (
        (ScopeId.CLAUDE_USER, user_specs),
        (ScopeId.MCP_JSON, project_specs),
    ):
        for name, spec in parsed.items():
            definitions.setdefault(name, []).append(scope)
            specs.setdefault(name, spec)

    row, found = project_row(claude, project_key)
    enable_all = settings_local.get("enableAllProjectMcpServers")
    approved = parse_name_list(settings_local.get("enabledMcpjsonServers"))

    verdicts: tuple[tuple[ScopeId, tuple[str, ...]], ...] = (
        (ScopeId.SETTINGS_DENIED, parse_denied_list(settings.get("deniedMcpServers"))),
        (
            ScopeId.CLAUDE_PROJECT_DISABLED,
            parse_name_list(row.get("disabledMcpServers")) if found else (),
        ),
        (
            ScopeId.CLAUDE_USER_DISABLED,
            parse_name_list(claude.get("disabledMcpServers")),
        ),
        (ScopeId.MCPJSON_APPROVED, approved),
        (
            ScopeId.LOADOUT_TEMPLATE,
            parse_name_list(defaults.get("disabledMcpServers")),
        ),
    )
    mentions: dict[str, list[ScopeId]] = {}
    for scope, names in verdicts:
        for name in names:
            bucket = mentions.setdefault(name, [])
            if scope not in bucket:
                bucket.append(scope)

    return Topology(
        specs=specs,
        definitions={k: tuple(v) for k, v in definitions.items()},
        mentions={k: tuple(v) for k, v in mentions.items()},
        project_key=project_key,
        project_row_found=found,
        approved_mcpjson=approved,
        enable_all_project_servers=enable_all is True,
    )
