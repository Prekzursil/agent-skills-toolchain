#!/usr/bin/env python3
"""Merge agents-managed MCP servers into Cursor's ~/.cursor/mcp.json.

Reads .agents/agents.json (source of truth) and merges the registry servers
into the live .cursor/mcp.json — using clean names (no agents__ prefix) and
skipping servers already provided by installed Cursor plugins.

Cursor is not a first-class target in mcp_control_plane (VALID_TARGETS is
{claude, codex}), so this merge mirrors the *claude* target selection: Cursor
can expose the same custom/local MCP surface as Claude Code.

Reunited 2026-09-02 from two lineages (``reconcile-flags/
mcp-cursor-merge-lineage-2026-09-02.md``): the repo's registry-authoritative
renderer with ``--check`` and the ``x_cursor.stdio_bridge`` rendering, and the
live box's two-phase, approval-gated attachment. Both test suites pin it.

Cursor-specific rendering differences vs the Claude merge:
- Credential references use Cursor's interpolation syntax ``${env:NAME}``
  (plain ``${NAME}`` is passed through literally by Cursor and would clobber
  inherited environment values).
- A timestamped backup of mcp.json is taken by default before writing
  (disable with --no-backup).
- Cursor's mcp.json has no documented ``disabled`` field, so definition
  attachment and runtime state are separate concerns. Nothing written here ever
  carries ``disabled``; runtime state is owned by the manager through
  ``cursor-agent mcp enable/disable``. Adding or removing a definition in this
  file requires a Cursor restart before it takes effect.
- An http server may declare ``x_cursor.stdio_bridge`` (``command`` + ``args``):
  Cursor then runs that per-session stdio shim with ``--url <registry url>``
  appended instead of dialing the URL itself. Used for ``basic-memory``, whose
  shared daemon restarts near-daily and whose stale session Cursor's own client
  never heals (``.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md``). Claude and
  Codex renderers ignore the key. Rendering is OS-independent, so ``--check``
  agrees on this entry from Linux as well. The script hardcodes no shim: an
  http entry without the declaration renders the direct URL.

Registry authority
------------------
The registry is the ONLY source of an entry's body. The live file supplies key
order and nothing else for every name the registry governs: a governed name the
registry does not generate is dropped, never adopted. Adopting it was how an
off-registry hand edit — measured 2026-09-01 as a stdio wrapper in front of the
shared ``basic-memory`` HTTP daemon — could outlive a sync and be force-enabled.
Governed = every registry name, the safe-default set, and the never-mount set.

Two-phase attachment
--------------------
SAFE DEFAULT (no flag): ``CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS`` — the core six
(``CURSOR_ENABLED_SERVERS``, the G-6=6B keep-list) plus explicitly owner-requested
local adapters — are attached. This is what ``sync_shared_state.ps1`` gets. The
remaining safe registry definitions are **deferred, not deleted and not
unsupported**: they stay in agents.json, they are still rendered by
``build_managed_servers_from_agents``, and ``.agents/mcp-cursor-parked-31.json``
keeps a rollback snapshot of them. A later sync cannot re-insert them, not even
as ``disabled: true``. Mixpanel stays absent (``CURSOR_RETIRED_SERVERS``).

EXPLICIT (--attach-all-safe): projects every safe registry definition and keeps
manual live entries whose names the registry has never governed. In dry-run and
``--check`` this is a projection only. With --write it additionally REQUIRES
--approvals-file pointing at the target workspace's Cursor approval store, and
refuses unless the approved set is a subset of the safe-default set. That gate
exists because Cursor's approval store keys on a server ID, so a stale approval
for a non-core name would silently auto-approve that server the moment its
definition is attached. Missing, unreadable, or malformed approval evidence
fails closed.

``--check`` reports drift between the live file and what this merge would render
under the active policy, and writes nothing — the read-only probe for
off-registry hand edits.

Full-attachment write sequencing (operator procedure)
-----------------------------------------------------
1. Freeze Cursor sessions for the workspace; no agent may be mid-run.
2. Have the manager disable every non-core server in the exact workdir
   (``cursor-agent mcp disable <id>`` run from that workspace).
3. Verify the workspace approval file is safe-default-only — this script
   re-verifies it, but check first so step 4 is not a surprise
   (``--attach-all-safe --check --approvals-file <workspace>/mcp-approvals.json``).
4. Run the guarded write:
   ``--attach-all-safe --write --approvals-file <workspace>/mcp-approvals.json``
5. Re-read the written mcp.json and confirm the attached set (``--check``).
6. Restart Cursor so the new definitions load.
7. Check process/status output before letting agents resume.

There is NO atomicity outside this guarded sequence: the JSON write itself is
atomic, but definition attachment plus approval state plus a running Cursor is
not a transaction. Never describe it as one.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import re
import shutil
import sys
from collections.abc import Collection, Iterable, Mapping
from datetime import datetime
from typing import Any

import mcp_control_plane as control


DEFAULT_PROJECT_ROOT = pathlib.Path(r"C:\Users\Prekzursil")
DEFAULT_LIVE_CONFIG = DEFAULT_PROJECT_ROOT / ".cursor" / "mcp.json"
DEFAULT_AGENTS_CONFIG = DEFAULT_PROJECT_ROOT / ".agents" / "agents.json"

# Servers intentionally left plugin-managed in Cursor. The tavily marketplace
# plugin is explicitly enabled in ~/.cursor/settings.json and mounts the same
# server; rendering it here would double-mount it.
CURSOR_PLUGIN_PROVIDED_SERVERS = frozenset({"tavily"})

# Registry servers deliberately NOT exposed to Cursor. These are present in
# .claude.json but explicitly denied in Claude's settings.json permissions;
# Cursor has no deny mechanism, so parity means not mounting them at all.
CURSOR_DENIED_SERVERS = frozenset({"markitdown", "meta-tool"})

# Servers retired from Cursor by owner decision and never re-mounted from a
# stale live file. They are absent from the registry, so this only guards
# against resurrecting a hand-edited leftover.
CURSOR_RETIRED_SERVERS = frozenset({"mixpanel", "mixpanel-mcp"})

# The core servers the owner keeps runtime-approved in Cursor — the G-6=6B
# (2026-08-27) keep-list. Both lineage names point at the same set.
CURSOR_DEFAULT_APPROVED_SERVERS = frozenset(
    {
        "agent-mail",
        "basic-memory",
        "chrome-devtools",
        "context7",
        "firecrawl",
        "playwright",
    }
)
CURSOR_ENABLED_SERVERS = CURSOR_DEFAULT_APPROVED_SERVERS

# Safe-default attachment policy. Without --attach-all-safe the merge writes
# the core set plus explicitly owner-requested local adapters (live,
# 2026-08-28: glm53-space). Everything else the registry selects is deferred to
# the explicit, approval-gated mode.
CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS = CURSOR_DEFAULT_APPROVED_SERVERS | {"glm53-space"}

# Cursor approval-store entries are "<server-name>-<16 lowercase hex>".
CURSOR_APPROVAL_ID_RE = re.compile(r"^(?P<name>.+)-(?P<digest>[0-9a-f]{16})$")

ENV_REF_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")

IS_WINDOWS = platform.system() == "Windows"


class ApprovalEvidenceError(RuntimeError):
    """Raised when Cursor approval evidence is absent, unusable, or too broad."""


def load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_cursor_approvals(path: pathlib.Path | str) -> frozenset[str]:
    """Read a workspace ``mcp-approvals.json`` and return approved server names.

    Fails closed: an absent or unreadable file, invalid JSON, a non-list
    payload, or any entry that is not a well-formed ``<name>-<16 hex>`` ID
    raises instead of degrading to "nothing is approved".
    """
    target = pathlib.Path(path)
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError as error:
        raise ApprovalEvidenceError(
            f"approval evidence is unreadable at {target}: {error}"
        ) from error

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ApprovalEvidenceError(
            f"approval evidence is malformed JSON at {target}: {error}"
        ) from error

    if not isinstance(payload, list):
        raise ApprovalEvidenceError(
            f"approval evidence is malformed at {target}: expected a JSON array of IDs"
        )

    names: set[str] = set()
    for item in payload:
        if not isinstance(item, str):
            raise ApprovalEvidenceError(
                f"approval evidence is malformed at {target}: non-string entry {item!r}"
            )
        match = CURSOR_APPROVAL_ID_RE.fullmatch(item)
        if match is None:
            raise ApprovalEvidenceError(
                f"approval evidence is malformed at {target}: "
                f"{item!r} is not a <name>-<16 hex> approval ID"
            )
        names.add(match.group("name"))
    return frozenset(names)


def load_safe_default_approvals(path: pathlib.Path | str) -> frozenset[str]:
    """Refuse approval evidence wider than the default-attached surface."""
    approved = parse_cursor_approvals(path)
    non_default = sorted(approved - CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS)
    if non_default:
        raise ApprovalEvidenceError(
            "approval evidence is wider than the safe-default surface; disable "
            f"these in the target workdir first: {', '.join(non_default)}"
        )
    return approved


def to_cursor_reference(value: Any) -> Any:
    """Rewrite ``${NAME}`` env references to Cursor's ``${env:NAME}`` syntax."""
    if not isinstance(value, str):
        return value
    return ENV_REF_RE.sub(lambda m: f"${{env:{m.group(1)}}}", value)


def needs_cmd_wrapper(command: str) -> bool:
    """Check if a command needs cmd /c wrapper on Windows."""
    if not IS_WINDOWS:
        return False
    bare = command.strip().lower()
    return bare in ("npx", "npm", "node") or bare.startswith("npx ")


def wrap_for_windows(command: str, args: list[str]) -> tuple[str, list[str]]:
    """Wrap npx/npm commands with cmd /c on Windows."""
    if needs_cmd_wrapper(command):
        return "cmd", ["/c", command] + args
    return command, args


def cursor_stdio_bridge(server: Mapping[str, Any]) -> dict[str, Any] | None:
    """The ``x_cursor.stdio_bridge`` override, or None when Cursor dials the URL."""
    x_cursor = server.get("x_cursor")
    if not isinstance(x_cursor, Mapping):
        return None
    bridge = x_cursor.get("stdio_bridge")
    return dict(bridge) if isinstance(bridge, Mapping) else None


def build_cursor_server(name: str, server: dict[str, Any]) -> dict[str, Any] | None:
    """Convert an agents.json server definition to a .cursor/mcp.json entry."""
    transport = server.get("transport", "stdio")

    if transport == "http":
        bridge = cursor_stdio_bridge(server)
        if bridge is not None:
            # Cursor runs a per-session stdio shim that dials the registry URL.
            # The URL is appended here, never repeated in the registry, so the
            # shim can only ever point at the daemon the registry declares.
            command, args = wrap_for_windows(
                str(bridge["command"]),
                [str(a) for a in bridge.get("args", [])] + ["--url", server["url"]],
            )
            return {"command": command, "args": args}
        entry: dict[str, Any] = {
            "url": server["url"],
        }
        headers = dict(server.get("headers", {}))
        x_codex = server.get("x_codex", {})
        bearer_env = (
            x_codex.get("bearer_token_env_var") if isinstance(x_codex, dict) else None
        )
        if bearer_env and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer ${{{bearer_env}}}"
        if headers:
            entry["headers"] = {
                key: to_cursor_reference(value) for key, value in headers.items()
            }
        return entry

    # stdio transport
    command = server.get("command", "")
    args = [str(a) for a in server.get("args", [])]

    command, args = wrap_for_windows(command, args)

    entry = {
        "command": command,
        "args": args,
    }

    env = server.get("env", {})
    if env:
        entry["env"] = {key: to_cursor_reference(value) for key, value in env.items()}

    if server.get("cwd"):
        entry["cwd"] = server["cwd"]

    return entry


def cursor_excluded_servers() -> frozenset[str]:
    return CURSOR_PLUGIN_PROVIDED_SERVERS | CURSOR_DENIED_SERVERS


def cursor_unmountable_servers() -> frozenset[str]:
    """Names that must never reach mcp.json, from any source or code path."""
    return cursor_excluded_servers() | CURSOR_RETIRED_SERVERS


def strip_disabled(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Drop ``disabled``: Cursor has no documented support for the field."""
    stamped = dict(entry)
    stamped.pop("disabled", None)
    return stamped


def attachable(name: str, *, attach_all_safe: bool) -> bool:
    """Decide whether a name may be attached under the active policy."""
    if name in cursor_unmountable_servers():
        return False
    if attach_all_safe:
        return True
    return name in CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS


def merge_cursor_mcp_servers(
    live_servers: Mapping[str, Any],
    generated: Mapping[str, dict[str, Any]],
    *,
    attach_all_safe: bool = False,
    registry_names: Collection[str] | None = None,
) -> dict[str, Any]:
    """Attach registry definitions to Cursor's mcpServers under the active policy.

    Default (``attach_all_safe=False``) attaches only the safe-default set, so a
    routine sync cannot widen Cursor's surface. ``attach_all_safe=True`` attaches
    every safe registry definition and additionally preserves manual live entries
    whose names the registry has never governed. Both the live loop and the
    generated loop drop plugin-provided, denied, and retired names, so a
    regression upstream cannot mount them. Runtime state is never expressed here
    — no entry carries ``disabled``.

    The registry is the ONLY source of a governed entry's body. The live file
    supplies key order and nothing else for those names: a governed name the
    registry does not generate is dropped, never adopted, in either mode. Pass
    ``registry_names`` (every name in ``mcp.servers``) so that a registry entry
    that is disabled, untargeted, or excluded counts as governed too.
    """
    governed = (
        set(generated)
        | set(registry_names or ())
        | CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS
        | cursor_unmountable_servers()
    )
    merged: dict[str, Any] = {}
    for name, entry in live_servers.items():
        if not attachable(name, attach_all_safe=attach_all_safe):
            continue
        if name in generated:
            merged[name] = strip_disabled(generated[name])
        elif attach_all_safe and name not in governed and isinstance(entry, Mapping):
            merged[name] = strip_disabled(entry)
    for name, entry in generated.items():
        if name in merged or not attachable(name, attach_all_safe=attach_all_safe):
            continue
        merged[name] = strip_disabled(entry)
    return merged


def build_managed_servers_from_agents(agents_config: dict) -> dict[str, dict[str, Any]]:
    """Render every safe Claude-target definition; attachment policy is separate."""
    selected = control.select_target_servers(
        agents_config,
        "claude",
        plugin_provided=cursor_excluded_servers(),
    )
    rendered = {
        name: build_cursor_server(name, server) for name, server in selected.items()
    }
    result = {name: entry for name, entry in rendered.items() if entry is not None}
    control.assert_exact_target_parity(
        agents_config,
        "claude",
        result,
        plugin_provided=cursor_excluded_servers(),
    )
    return result


def fail(reason: str) -> int:
    print(f"FAILED:mcp-cursor-merge {reason}", file=sys.stderr)
    return 2


def classify_registry_skips(
    servers: Mapping[str, Any], generated: Iterable[str]
) -> dict[str, list[str]]:
    """Explain why each registry server was not rendered for Cursor."""
    rendered = set(generated)
    skips: dict[str, list[str]] = {
        "plugin": [],
        "denied": [],
        "registry_disabled": [],
        "no_target": [],
    }
    for name, server in sorted(servers.items()):
        if name in rendered:
            continue
        if name in CURSOR_PLUGIN_PROVIDED_SERVERS:
            skips["plugin"].append(name)
        elif name in CURSOR_DENIED_SERVERS:
            skips["denied"].append(name)
        elif not server.get("enabled", True):
            skips["registry_disabled"].append(name)
        else:
            skips["no_target"].append(name)
    return skips


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge agents-managed MCP servers into Cursor's .cursor/mcp.json",
        epilog=(
            "Safe default: only the core six plus owner-requested adapters are "
            "attached, so sync_shared_state.ps1 cannot widen Cursor's surface. "
            "--attach-all-safe projects every safe registry definition; combined with "
            "--write it requires --approvals-file and refuses unless that workspace "
            "approval store is safe-default-only. --check compares the live file with "
            "the projection under the active policy and writes nothing. "
            "Full-attachment sequence: freeze sessions; manager disables every "
            "non-core server in the exact workdir; verify the approval file is "
            "safe-default-only; run the guarded write; re-read mcp.json; restart "
            "Cursor; check process/status. This sequence is not atomic."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--live", default=str(DEFAULT_LIVE_CONFIG), help="Path to live .cursor/mcp.json"
    )
    parser.add_argument(
        "--agents-config",
        default=str(DEFAULT_AGENTS_CONFIG),
        help="Path to .agents/agents.json",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write merged config back to .cursor/mcp.json",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip the timestamped backup before writing",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Report drift between the live file and the registry projection; write "
            "nothing. Run this on the same OS that renders the file: the npx 'cmd /c' "
            "wrapper is Windows-only, so a Linux run reports the npx servers as false "
            "drift"
        ),
    )
    parser.add_argument(
        "--attach-all-safe",
        action="store_true",
        help=(
            "Attach every safe registry definition instead of the safe-default set; "
            "with --write this requires --approvals-file"
        ),
    )
    parser.add_argument(
        "--approvals-file",
        default=None,
        help=(
            "Path to the target workspace's Cursor mcp-approvals.json; an "
            "--attach-all-safe write is refused unless it is safe-default-only. "
            "Verified whenever given with --attach-all-safe; ignored otherwise"
        ),
    )
    args = parser.parse_args()

    if args.check and args.write:
        parser.error("--check is read-only and cannot be combined with --write")

    live_path = pathlib.Path(args.live)
    agents_config_path = pathlib.Path(args.agents_config)

    agents_config = load_json(agents_config_path)
    live_config = load_json(live_path) if live_path.exists() else {}
    control.validate_registry(agents_config)

    servers = agents_config.get("mcp", {}).get("servers", {})
    mcp_servers = live_config.get("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        mcp_servers = {}
    generated = build_managed_servers_from_agents(agents_config)

    approval_proof = "not-required"
    if args.attach_all_safe:
        approval_proof = "dry-run-unverified"
        if args.write and not args.approvals_file:
            return fail(
                "--attach-all-safe --write requires --approvals-file "
                "<workspace>/mcp-approvals.json"
            )
        if args.approvals_file:
            try:
                load_safe_default_approvals(args.approvals_file)
            except ApprovalEvidenceError as error:
                return fail(str(error))
            approval_proof = "safe-default-only-verified"

    merged = merge_cursor_mcp_servers(
        mcp_servers,
        generated,
        attach_all_safe=args.attach_all_safe,
        registry_names=set(servers),
    )
    bridged = sorted(
        name
        for name in merged
        if cursor_stdio_bridge(servers.get(name, {})) is not None
    )
    attach_flag = str(args.attach_all_safe).lower()

    if args.check:
        drifted = sorted(
            name
            for name in set(merged) | set(mcp_servers)
            if merged.get(name) != mcp_servers.get(name)
        )
        if drifted:
            # Names only: entries carry ${env:...} references, never values.
            print(
                "FAILED:mcp-cursor-check "
                f"live={live_path} drift={len(drifted)} servers={','.join(drifted)} "
                f"attach_all_safe={attach_flag}"
            )
            return 1
        print(
            f"SUCCESS:mcp-cursor-check live={live_path} drift=0 managed={len(merged)} "
            f"attach_all_safe={attach_flag}"
        )
        return 0

    live_config["mcpServers"] = merged

    skips = classify_registry_skips(servers, generated)
    added = [name for name in merged if name not in mcp_servers]
    updated = [name for name in merged if name in mcp_servers]
    core_attached = [name for name in merged if name in CURSOR_DEFAULT_APPROVED_SERVERS]
    noncore_projected = [
        name for name in merged if name not in CURSOR_DEFAULT_APPROVED_SERVERS
    ]
    manual_preserved = [name for name in merged if name not in generated]
    parked = [name for name in generated if name not in merged]
    disabled_keys = [
        name
        for name, entry in merged.items()
        if isinstance(entry, dict) and "disabled" in entry
    ]

    if args.write:
        if live_path.exists() and not args.no_backup:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = live_path.with_suffix(f".json.bak-{ts}")
            shutil.copy2(live_path, backup_path)

        control.atomic_write_json(live_path, live_config)

    print(
        "SUCCESS:mcp-cursor-merge "
        f"managed={len(generated)} attached={len(merged)} "
        f"core_attached={len(core_attached)} "
        f"noncore_projected={len(noncore_projected)} "
        f"manual_preserved={len(manual_preserved)} "
        f"added={len(added)} updated={len(updated)} "
        f"disabled_keys={len(disabled_keys)} "
        f"plugin_skips={len(skips['plugin'])} denied_skips={len(skips['denied'])} "
        f"registry_disabled_skips={len(skips['registry_disabled'])} "
        f"no_target_skips={len(skips['no_target'])} "
        f"parked_skips={len(parked)} bridged={len(bridged)} "
        f"attach_all_safe={attach_flag} "
        f"approval_proof={approval_proof} "
        f"write={str(args.write).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
