"""Decision logic for the shared-MCP-host supervisor.

Pure functions, no I/O, no process control - so every rule below is unit-testable
and the PowerShell supervisor stays a thin actuator around tested decisions.

Three decisions live here, each encoding a failure this estate already paid for:

``parse_fleet`` / ``validate_fleet``
    Refuse a manifest before it can bind a LIVE port. 8765 (basic-memory) and
    8812 (mcp_agent_mail) are running services; binding either takes them down.

``wedge_verdict``
    Decide whether a host is genuinely wedged. Recycling on a failed health
    poll ALONE is what made the agent-mail supervisor kill children that were
    2-60s from ready (its fix was a 240s grace; the deeper fix is an AND-gate).
    A kill needs THREE agreeing signals: unhealthy, CPU flat, and no new
    requests served.

``find_orphans``
    Decide what may be killed. A machine-wide pattern reap once killed sibling
    sessions' MCP children; reaping is therefore ownership-scoped - a process
    survives unless it is OUR leftover or its parent is gone.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any

#: Ports already owned by long-lived local services. Binding one is a hard error.
RESERVED_PORTS: dict[int, str] = {
    8765: "basic-memory",
    8812: "mcp_agent_mail",
}

#: A CPU delta at or below this (seconds) counts as "no progress".
CPU_EPSILON = 0.05

DEFAULT_HEALTH_PATH = "/healthz"
DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_STARTUP_GRACE_SEC = 240
DEFAULT_MAX_FAIL_STREAK = 3

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@dataclass(frozen=True)
class ServerSpec:
    """One shared host: a stdio MCP command published on a loopback port."""

    name: str
    port: int
    command: tuple[str, ...]
    health_path: str = DEFAULT_HEALTH_PATH
    bind_host: str = DEFAULT_BIND_HOST
    enabled: bool = True
    startup_grace_sec: int = DEFAULT_STARTUP_GRACE_SEC


@dataclass(frozen=True)
class HostSample:
    """One observation of a running host, from /healthz + the OS process table."""

    cpu_seconds: float
    requests_served: int
    healthy: bool
    uptime_sec: float
    fail_streak: int


def parse_fleet(data: Any) -> tuple[list[ServerSpec], list[str]]:
    """Parse a fleet manifest into specs plus a list of human-readable errors.

    Returns ``([], errors)`` when anything is malformed - the caller must treat a
    non-empty error list as fatal rather than starting a partial fleet.
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return [], ["fleet manifest must be a mapping with a 'servers' key"]

    raw_servers = data.get("servers")
    if not isinstance(raw_servers, list):
        return [], ["fleet manifest 'servers' must be a list"]

    specs: list[ServerSpec] = []
    for index, entry in enumerate(raw_servers):
        label = f"servers[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: must be a mapping")
            continue

        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{label}: missing or empty 'name'")
            continue

        port = entry.get("port")
        if not isinstance(port, int) or isinstance(port, bool):
            errors.append(f"{label} ({name}): 'port' must be an integer")
            continue
        if not 1024 <= port <= 65535:
            errors.append(f"{label} ({name}): 'port' {port} outside 1024-65535")
            continue

        command = entry.get("command")
        if not isinstance(command, list) or not command:
            errors.append(f"{label} ({name}): 'command' must be a non-empty list")
            continue
        if not all(isinstance(part, str) for part in command):
            errors.append(f"{label} ({name}): 'command' entries must be strings")
            continue

        specs.append(
            ServerSpec(
                name=name,
                port=port,
                command=tuple(command),
                health_path=str(entry.get("health_path", DEFAULT_HEALTH_PATH)),
                bind_host=str(entry.get("bind_host", DEFAULT_BIND_HOST)),
                enabled=bool(entry.get("enabled", True)),
                startup_grace_sec=int(
                    entry.get("startup_grace_sec", DEFAULT_STARTUP_GRACE_SEC)
                ),
            )
        )

    if errors:
        return [], errors
    return specs, []


def validate_fleet(specs: list[ServerSpec]) -> list[str]:
    """Cross-spec checks: port clashes, name clashes, reserved ports, bind host.

    Disabled specs are skipped: a parked entry must not block the fleet.
    """
    errors: list[str] = []
    seen_ports: dict[int, str] = {}
    seen_names: set[str] = set()

    for spec in specs:
        if not spec.enabled:
            continue

        if spec.name in seen_names:
            errors.append(f"duplicate server name '{spec.name}'")
        seen_names.add(spec.name)

        owner = RESERVED_PORTS.get(spec.port)
        if owner is not None:
            errors.append(
                f"'{spec.name}' wants port {spec.port}, which belongs to the live "
                f"{owner} service - pick another port"
            )

        if spec.port in seen_ports:
            errors.append(
                f"port {spec.port} claimed by both '{seen_ports[spec.port]}' "
                f"and '{spec.name}'"
            )
        seen_ports[spec.port] = spec.name

        if spec.bind_host not in _LOOPBACK:
            errors.append(
                f"'{spec.name}' binds {spec.bind_host}: only loopback addresses "
                f"({', '.join(sorted(_LOOPBACK))}) are allowed"
            )

    return errors


def wedge_verdict(
    previous: HostSample | None,
    current: HostSample,
    *,
    startup_grace_sec: int = DEFAULT_STARTUP_GRACE_SEC,
    max_fail_streak: int = DEFAULT_MAX_FAIL_STREAK,
    cpu_epsilon: float = CPU_EPSILON,
) -> str:
    """Classify a host as HEALTHY / STARTING / DEGRADED / BUSY / WEDGED.

    Only ``WEDGED`` authorises a recycle, and it requires an AND-gate of three
    mechanically independent signals - a failed health poll, a flat CPU counter,
    and a flat request counter. Any single one of those alone is a measurement
    artifact often enough that acting on it costs more than waiting:

    * ``STARTING`` - inside the startup grace. A cold start on this box has been
      measured at 90-150s under memory pressure; never kill inside the grace.
    * ``DEGRADED`` - unhealthy but under the fail-streak threshold, or the first
      ever observation (one reading is not a trend).
    * ``BUSY``     - unhealthy, streak exceeded, but CPU or requests still
      advancing: the process is working, the probe is just not being answered.
    """
    if current.healthy:
        return "HEALTHY"

    if current.uptime_sec < startup_grace_sec:
        return "STARTING"

    if current.fail_streak < max_fail_streak:
        return "DEGRADED"

    if previous is None:
        return "DEGRADED"

    cpu_advanced = (current.cpu_seconds - previous.cpu_seconds) > cpu_epsilon
    requests_advanced = current.requests_served > previous.requests_served
    if cpu_advanced or requests_advanced:
        return "BUSY"

    return "WEDGED"


def find_orphans(
    procs: list[dict[str, Any]],
    supervisor_pid: int,
    tracked_pids: set[int],
    signature: str,
) -> list[int]:
    """Return pids safe to reap: OUR leftovers and true orphans, nothing else.

    ``procs`` rows carry ``pid``, ``ppid`` and ``cmdline``. A process is reapable
    only when its command line matches ``signature`` AND it is either

    * parented by this supervisor but no longer tracked (a stale leftover), or
    * parented by a pid that is not alive in ``procs`` (a true orphan).

    A process whose parent is a DIFFERENT live process belongs to somebody else -
    typically a sibling agent session - and is never returned. That distinction
    is the whole rule: a machine-wide pattern reap once killed sibling sessions'
    MCP children, and the fix was to scope reaping to ownership.

    Raises ``ValueError`` on an empty signature, which would otherwise match
    every process on the box.
    """
    if not signature or not signature.strip():
        raise ValueError("find_orphans requires a non-empty command-line signature")

    needle = signature.lower()
    live_pids = {row.get("pid") for row in procs}
    reapable: set[int] = set()

    for row in procs:
        pid = row.get("pid")
        if not isinstance(pid, int) or pid == supervisor_pid or pid in tracked_pids:
            continue
        if needle not in str(row.get("cmdline", "")).lower():
            continue

        ppid = row.get("ppid")
        if ppid == supervisor_pid or ppid not in live_pids:
            reapable.add(pid)

    return sorted(reapable)


# --------------------------------------------------------------------- CLI
#
# The PowerShell supervisor shells to these subcommands so that every DECISION
# (what is valid, what is wedged, what may be killed) stays in tested Python and
# PowerShell only actuates. Each subcommand reads/writes JSON on stdout.


def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def _cmd_validate(args: argparse.Namespace) -> int:
    specs, errors = parse_fleet(_load_json(args.manifest))
    errors = errors or validate_fleet(specs)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(json.dumps({"ok": False, "errors": errors}))
        return 1
    print(json.dumps({"ok": True, "servers": len([s for s in specs if s.enabled])}))
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    specs, errors = parse_fleet(_load_json(args.manifest))
    errors = errors or validate_fleet(specs)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}))
        return 1
    plan = [
        {
            "name": spec.name,
            "port": spec.port,
            "command": list(spec.command),
            "health_url": f"http://{spec.bind_host}:{spec.port}{spec.health_path}",
            "bind_host": spec.bind_host,
            "startup_grace_sec": spec.startup_grace_sec,
        }
        for spec in specs
        if spec.enabled
    ]
    print(json.dumps({"ok": True, "plan": plan}))
    return 0


def _cmd_verdict(args: argparse.Namespace) -> int:
    payload = _load_json(args.state)
    previous = payload.get("previous")
    verdict = wedge_verdict(
        HostSample(**previous) if previous else None,
        HostSample(**payload["current"]),
        startup_grace_sec=int(
            payload.get("startup_grace_sec", DEFAULT_STARTUP_GRACE_SEC)
        ),
        max_fail_streak=int(payload.get("max_fail_streak", DEFAULT_MAX_FAIL_STREAK)),
    )
    print(json.dumps({"ok": True, "verdict": verdict, "recycle": verdict == "WEDGED"}))
    return 0


def _cmd_orphans(args: argparse.Namespace) -> int:
    payload = _load_json(args.input)
    try:
        pids = find_orphans(
            payload.get("procs", []),
            supervisor_pid=int(payload["supervisor_pid"]),
            tracked_pids={int(p) for p in payload.get("tracked_pids", [])},
            signature=str(payload.get("signature", "")),
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}))
        return 1
    print(json.dumps({"ok": True, "orphans": pids}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="check a fleet manifest")
    validate.add_argument("--manifest", required=True)
    validate.set_defaults(func=_cmd_validate)

    plan = subparsers.add_parser("plan", help="emit the enabled-server launch plan")
    plan.add_argument("--manifest", required=True)
    plan.set_defaults(func=_cmd_plan)

    verdict = subparsers.add_parser("verdict", help="classify a host from two samples")
    verdict.add_argument("--state", required=True)
    verdict.set_defaults(func=_cmd_verdict)

    orphans = subparsers.add_parser("orphans", help="list pids that are safe to reap")
    orphans.add_argument("--input", required=True)
    orphans.set_defaults(func=_cmd_orphans)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
