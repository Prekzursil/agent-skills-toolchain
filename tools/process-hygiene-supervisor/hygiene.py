#!/usr/bin/env python3
"""Estate-wide process-hygiene decision engine (pure Python, no process control).

Every decision this module makes is a pure function of a JSON *snapshot* of the
Windows process table plus a JSON *policy*; the only side effect is the JSONL
*ledger*. Process termination, ``wsl --shutdown`` and the cursor-agent reaper are
delegated to an injected actuator (``hygiene_actuate.WindowsActuator`` in
production, a fake in the tests), so every rule below is unit-testable and the
PowerShell launcher stays a thin snapshot-gatherer/actuator - the same split the
estate already uses for ``tools/mcp/mcp-host-supervisor`` (Python decides,
PowerShell actuates).

The rules encode the leaks measured on the owner's 31.6 GB box at 04:50 EEST on
02.09.2026 (3.5 GB free; 67.7 GB committed):

* ``retired``                 - the retired AgentBridge bridge-server crash-looping
  under three Grok sessions. Stopped on sight; the ledger names the launcher to
  edit so it stops respawning.
* ``orphan`` / ``daemon``     - node/python whose parent is gone. Reaped only after
  age + repeated whole-tree-idle confirmation; a parentless process that owns a
  listening port is a daemon (auth2api), reported not killed.
* ``session-age`` / ``rss-*`` - per-runtime session-age and private-bytes ceilings
  with graceful-stop-then-kill; an IDE-owned or peer-runtime-owned agent is never
  a stale session.
* ``mcp-*``                   - MCP duplication, singleton breach and per-instance
  budget, decided through the shipped ``mcp_fleet_supervisor`` / control plane.
* ``wsl-*``                   - a report + idle ``wsl --shutdown`` for an idle
  vmmem, paired with the ``.wslconfig`` memory cap in the install steps.
* protected                   - auth2api, the Basic Memory daemon + watchdog, the
  MCP hosts, this supervisor and Windows binaries survive every rule.

cursor-agent orphans are DELEGATED to the tested ``cursor-orphan-reaper.ps1``
rather than reaped here, so its multi-observation identity-revalidation contract
stays the single owner of cursor-agent lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Any

SCHEMA_POLICY = "process-hygiene-policy-v1"
SCHEMA_SNAPSHOT = "process-hygiene-snapshot-v1"
SCHEMA_STATE = "process-hygiene-state-v1"
SCHEMA_LEDGER = "process-hygiene-ledger-v1"

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_POLICY_PATH = HERE / "policy.example.json"
DEFAULT_FLEET_PATH = REPO_ROOT / ".agents" / "scripts" / "mcp_fleet_supervisor.py"
DEFAULT_REGISTRY_PATH = REPO_ROOT / ".agents" / "agents.json"

TIER_ORDER = {"normal": 0, "elevated": 1, "critical": 2}
IDE_NAMES = frozenset({"cursor.exe", "code.exe"})
COMMAND_LINE_MAX = 500

_SECRET_FLAG_RE = re.compile(
    r"(?i)(--?(?:api[-_]?key|access[-_]?key|password|secret|token)[\s=:]+)(\S+)"
)
_SECRET_LITERAL_RE = re.compile(
    r"(?i)\b(?:github_pat_|gh[pousr]_|hf_|apify_api_|sk-|ctx7sk-|fc-|do[op]_v1_)"
    r"[A-Za-z0-9_-]{12,}"
)


class PolicyError(ValueError):
    """Raised when a policy, state or wiring input violates the contract."""


class SnapshotError(ValueError):
    """Raised when a process snapshot is malformed or out of order."""


# --------------------------------------------------------------------- normalise


def _norm(value: str) -> str:
    return str(value).replace("\\", "/").lower()


def redact(text: str) -> str:
    """Strip credential flags and literal-key tokens before they hit the ledger."""
    text = _SECRET_FLAG_RE.sub(r"\1[REDACTED]", text)
    return _SECRET_LITERAL_RE.sub("[REDACTED]", text)


# ------------------------------------------------------------------ policy load


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PolicyError(f"{label} must be a mapping")
    return value


def _pos_int(section: dict[str, Any], key: str, label: str) -> int:
    value = section.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise PolicyError(f"{label}.{key} must be a non-negative integer")
    return value


def _pos_num(section: dict[str, Any], key: str, label: str) -> float:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise PolicyError(f"{label}.{key} must be a non-negative number")
    return float(value)


def _string_list(section: dict[str, Any], key: str, label: str) -> list[str]:
    value = section.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PolicyError(f"{label}.{key} must be a list of strings")
    return list(value)


def _bool(section: dict[str, Any], key: str, label: str, default: bool) -> bool:
    value = section.get(key, default)
    if not isinstance(value, bool):
        raise PolicyError(f"{label}.{key} must be a boolean")
    return value


def _compile(pattern: str, label: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise PolicyError(f"{label} is not a valid regex: {exc}") from exc


def _tier(section: dict[str, Any], key: str, label: str, default: str) -> str:
    value = section.get(key, default)
    if value not in TIER_ORDER:
        raise PolicyError(f"{label}.{key} must name a tier ({sorted(TIER_ORDER)})")
    return value


_POLICY_KEYS = {
    "schema",
    "intervalSeconds",
    "pressure",
    "idle",
    "protected",
    "browsers",
    "runtimes",
    "orphans",
    "retired",
    "mcp",
    "wsl",
    "escalation",
    "integration",
    "ledger",
}


def validate_policy(raw: Any) -> dict[str, Any]:
    """Return a normalised, fully-defaulted policy or raise ``PolicyError``."""
    policy = _require_mapping(raw, "policy")
    if policy.get("schema") != SCHEMA_POLICY:
        raise PolicyError(f"policy schema must be {SCHEMA_POLICY}")
    unknown = {key for key in policy if not key.startswith("_")} - _POLICY_KEYS
    if unknown:
        raise PolicyError(f"policy: unknown key {sorted(unknown)[0]!r}")

    pressure = _require_mapping(policy["pressure"], "pressure")
    elevated = _require_mapping(pressure.get("elevated"), "pressure.elevated")
    critical = _require_mapping(pressure.get("critical"), "pressure.critical")
    tiers = {
        "elevated": {
            "free": _pos_int(elevated, "freeBytesBelow", "pressure.elevated"),
            "ratio": _pos_num(elevated, "commitRatioAbove", "pressure.elevated"),
        },
        "critical": {
            "free": _pos_int(critical, "freeBytesBelow", "pressure.critical"),
            "ratio": _pos_num(critical, "commitRatioAbove", "pressure.critical"),
        },
        "deescalate": _pos_int(pressure, "deescalateObservations", "pressure"),
    }
    if tiers["deescalate"] < 1:
        raise PolicyError("pressure.deescalateObservations must be >= 1")
    if tiers["critical"]["free"] > tiers["elevated"]["free"]:
        raise PolicyError("pressure.critical.freeBytesBelow must be <= elevated")
    if tiers["critical"]["ratio"] < tiers["elevated"]["ratio"]:
        raise PolicyError("pressure.critical.commitRatioAbove must be >= elevated")

    idle = _require_mapping(policy["idle"], "idle")
    idle_norm = {
        "cpu": _pos_num(idle, "cpuSeconds", "idle"),
        "io": _pos_int(idle, "ioBytes", "idle"),
        "observations": _pos_int(idle, "observations", "idle"),
    }
    if idle_norm["observations"] < 1:
        raise PolicyError("idle.observations must be >= 1")

    protected = _require_mapping(policy["protected"], "protected")
    protected_norm = {
        "exe": [
            _compile(pattern, "protected.executablePatterns")
            for pattern in _string_list(protected, "executablePatterns", "protected")
        ],
        "names": [
            name.lower() for name in _string_list(protected, "names", "protected")
        ],
        "tokens": [
            _norm(token)
            for token in _string_list(protected, "commandLineTokens", "protected")
        ],
    }

    browsers = _require_mapping(policy["browsers"], "browsers")
    browsers_norm = {
        "names": [name.lower() for name in _string_list(browsers, "names", "browsers")],
        "report": _pos_int(browsers, "reportPrivateBytesAbove", "browsers"),
    }

    runtimes_raw = _require_mapping(policy["runtimes"], "runtimes")
    runtimes: dict[str, dict[str, Any]] = {}
    for name, spec in runtimes_raw.items():
        label = f"runtimes.{name}"
        spec = _require_mapping(spec, label)
        pattern = spec.get("executablePattern")
        tokens = _string_list(spec, "commandLineTokens", label)
        if pattern is None and not tokens:
            raise PolicyError(f"{label} needs executablePattern or commandLineTokens")
        soft = _pos_int(spec, "softPrivateBytes", label)
        hard = _pos_int(spec, "hardPrivateBytes", label)
        if hard < soft:
            raise PolicyError(f"{label}.softPrivateBytes must be <= hardPrivateBytes")
        runtimes[name] = {
            "exe": _compile(pattern, f"{label}.executablePattern") if pattern else None,
            "tokens": [_norm(token) for token in tokens],
            "maxAge": _pos_int(spec, "maxSessionAgeSeconds", label),
            "soft": soft,
            "hard": hard,
            "graceful": _pos_int(spec, "gracefulSeconds", label),
            "orphanHandler": spec.get("orphanHandler"),
        }
        if runtimes[name]["orphanHandler"] not in (None, "cursor-orphan-reaper"):
            raise PolicyError(f"{label}.orphanHandler is unsupported")

    orphans = _require_mapping(policy["orphans"], "orphans")
    orphans_norm = {
        "minAge": _pos_int(orphans, "minAgeSeconds", "orphans"),
        "names": [name.lower() for name in _string_list(orphans, "names", "orphans")],
        "graceful": _pos_int(orphans, "gracefulSeconds", "orphans"),
    }

    retired_raw = policy.get("retired", [])
    if not isinstance(retired_raw, list):
        raise PolicyError("retired must be a list")
    retired_norm: list[dict[str, Any]] = []
    for index, entry in enumerate(retired_raw):
        label = f"retired[{index}]"
        entry = _require_mapping(entry, label)
        identifier = entry.get("id")
        match_all = entry.get("matchAll")
        if not isinstance(identifier, str) or not identifier:
            raise PolicyError(f"{label}.id must be a non-empty string")
        if (
            not isinstance(match_all, list)
            or not match_all
            or any(not isinstance(token, str) or not token for token in match_all)
        ):
            raise PolicyError(f"{label}.matchAll must be a non-empty string list")
        retired_norm.append(
            {
                "id": identifier,
                "tokens": [_norm(token) for token in match_all],
                "graceful": _pos_int(entry, "gracefulSeconds", label),
                "remediation": str(entry.get("remediation", "")),
            }
        )

    mcp = _require_mapping(policy["mcp"], "mcp")
    mcp_norm = {
        "enabled": _bool(mcp, "enabled", "mcp", True),
        "graceful": _pos_int(mcp, "gracefulSeconds", "mcp"),
        "sameOwner": _tier(
            _require_mapping(mcp["sameOwnerDuplicate"], "mcp.sameOwnerDuplicate"),
            "minTier",
            "mcp.sameOwnerDuplicate",
            "elevated",
        ),
        "singletonTier": _tier(
            _require_mapping(mcp["singletonDuplicate"], "mcp.singletonDuplicate"),
            "minTier",
            "mcp.singletonDuplicate",
            "elevated",
        ),
        "singletonGrace": _pos_int(
            _require_mapping(mcp["singletonDuplicate"], "mcp.singletonDuplicate"),
            "graceSeconds",
            "mcp.singletonDuplicate",
        ),
        "overBudget": _tier(
            _require_mapping(mcp["overBudget"], "mcp.overBudget"),
            "minTier",
            "mcp.overBudget",
            "critical",
        ),
    }

    wsl = _require_mapping(policy["wsl"], "wsl")
    unknown_wsl = set(wsl) - {"vmmemNames", "reportPrivateBytesAbove", "idleShutdown"}
    if unknown_wsl:
        raise PolicyError(f"wsl: unknown key {sorted(unknown_wsl)[0]!r}")
    idle_shutdown = _require_mapping(wsl["idleShutdown"], "wsl.idleShutdown")
    wsl_norm = {
        "names": [name.lower() for name in _string_list(wsl, "vmmemNames", "wsl")],
        "report": _pos_int(wsl, "reportPrivateBytesAbove", "wsl"),
        "tier": _tier(idle_shutdown, "minTier", "wsl.idleShutdown", "elevated"),
        "observations": _pos_int(idle_shutdown, "observations", "wsl.idleShutdown"),
    }
    if wsl_norm["observations"] < 1:
        raise PolicyError("wsl.idleShutdown.observations must be >= 1")

    escalation = _require_mapping(policy.get("escalation", {}), "escalation")
    escalation_norm = {
        "stopActiveAtCritical": _bool(
            escalation, "stopActiveAtCritical", "escalation", False
        )
    }

    integration = _require_mapping(policy.get("integration", {}), "integration")
    powershell = integration.get("powershell", "powershell.exe")
    if not isinstance(powershell, str) or not powershell:
        raise PolicyError("integration.powershell must be a string")
    integration_norm = {
        "powershell": powershell,
        "reaperPath": str(integration.get("reaperPath", "")),
        "reaperStateFile": str(integration.get("reaperStateFile", "")),
        "reaperEvidenceRoot": str(integration.get("reaperEvidenceRoot", "")),
        "wslExe": str(integration.get("wslExe", "wsl.exe")),
    }

    ledger = _require_mapping(policy.get("ledger", {}), "ledger")
    ledger_norm = {
        "maxBytes": _pos_int(
            {"maxBytes": ledger.get("maxBytes", 20 * 1024 * 1024)}, "maxBytes", "ledger"
        )
    }

    return {
        "schema": SCHEMA_POLICY,
        "intervalSeconds": _pos_int(policy, "intervalSeconds", "policy"),
        "pressure": tiers,
        "idle": idle_norm,
        "protected": protected_norm,
        "browsers": browsers_norm,
        "runtimes": runtimes,
        "orphans": orphans_norm,
        "retired": retired_norm,
        "mcp": mcp_norm,
        "wsl": wsl_norm,
        "escalation": escalation_norm,
        "integration": integration_norm,
        "ledger": ledger_norm,
    }


def load_policy(path: pathlib.Path | str) -> dict[str, Any]:
    return validate_policy(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))


# --------------------------------------------------------------------- snapshot


@dataclass(frozen=True)
class ProcRow:
    pid: int
    ppid: int
    name: str
    executable: str
    command_line: str
    created_unix: int
    cpu_seconds: float | None
    io_bytes: int | None
    working_set_bytes: int
    private_bytes: int

    @property
    def exe_norm(self) -> str:
        return _norm(self.executable)

    @property
    def cmd_norm(self) -> str:
        return _norm(self.command_line)

    @property
    def metrics_known(self) -> bool:
        return self.cpu_seconds is not None and self.io_bytes is not None


@dataclass
class Snapshot:
    taken_unix: int
    physical_bytes: int
    free_bytes: int
    commit_total_bytes: int
    commit_limit_bytes: int
    compressed_bytes: int | None
    wsl_available: bool
    wsl_running: list[str]
    listeners: dict[int, int]
    supervisor_pids: set[int]
    processes: list[ProcRow]
    by_pid: dict[int, ProcRow] = field(default_factory=dict)
    children: dict[int, list[int]] = field(default_factory=dict)


def _int(
    section: dict[str, Any], key: str, label: str, *, minimum: int | None = None
) -> int:
    value = section.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise SnapshotError(f"{label}.{key} must be an integer")
    if minimum is not None and value < minimum:
        raise SnapshotError(f"{label}.{key} must be >= {minimum}")
    return value


def _opt_number(section: dict[str, Any], key: str, label: str) -> float | None:
    value = section.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SnapshotError(f"{label}.{key} must be a number or null")
    return value


def parse_snapshot(raw: Any) -> Snapshot:
    """Validate a process-table snapshot and index it by pid / parent."""
    if not isinstance(raw, dict):
        raise SnapshotError("snapshot must be a mapping")
    if raw.get("schema") != SCHEMA_SNAPSHOT:
        raise SnapshotError(f"snapshot schema must be {SCHEMA_SNAPSHOT}")
    taken = _int(raw, "taken_unix", "snapshot", minimum=0)
    host = _require_mapping_snapshot(raw.get("host"), "host")
    physical = _int(host, "physical_bytes", "host", minimum=1)
    free = _int(host, "free_bytes", "host", minimum=0)
    commit_total = _int(host, "commit_total_bytes", "host", minimum=0)
    commit_limit = _int(host, "commit_limit_bytes", "host", minimum=0)
    compressed_raw = host.get("compressed_bytes")
    if compressed_raw is not None:
        compressed_raw = _int(host, "compressed_bytes", "host", minimum=0)

    wsl_raw = raw.get("wsl", {"available": False, "running_distros": []})
    wsl = _require_mapping_snapshot(wsl_raw, "wsl")
    wsl_available = wsl.get("available", False)
    if not isinstance(wsl_available, bool):
        raise SnapshotError("wsl.available must be a boolean")
    running = wsl.get("running_distros", [])
    if not isinstance(running, list) or any(
        not isinstance(item, str) for item in running
    ):
        raise SnapshotError("wsl.running_distros must be a list of strings")

    listeners: dict[int, int] = {}
    for index, entry in enumerate(raw.get("listeners", [])):
        entry = _require_mapping_snapshot(entry, f"listeners[{index}]")
        listeners[_int(entry, "port", f"listeners[{index}]", minimum=0)] = _int(
            entry, "pid", f"listeners[{index}]", minimum=0
        )

    supervisor_pids = set()
    for index, value in enumerate(raw.get("supervisor_pids", [])):
        if not isinstance(value, int) or isinstance(value, bool):
            raise SnapshotError(f"supervisor_pids[{index}] must be an integer")
        supervisor_pids.add(value)

    processes_raw = raw.get("processes")
    if not isinstance(processes_raw, list):
        raise SnapshotError("processes must be a list")
    processes: list[ProcRow] = []
    for index, entry in enumerate(processes_raw):
        label = f"processes[{index}]"
        entry = _require_mapping_snapshot(entry, label)
        for key in ("name", "executable", "command_line"):
            if not isinstance(entry.get(key), str):
                raise SnapshotError(f"{label}.{key} must be a string")
        processes.append(
            ProcRow(
                pid=_int(entry, "pid", label, minimum=0),
                ppid=_int(entry, "ppid", label, minimum=0),
                name=entry["name"],
                executable=entry["executable"],
                command_line=entry["command_line"],
                created_unix=_int(entry, "created_unix", label, minimum=0),
                cpu_seconds=_opt_number(entry, "cpu_seconds", label),
                io_bytes=None
                if entry.get("io_bytes") is None
                else _int(entry, "io_bytes", label, minimum=0),
                working_set_bytes=_int(entry, "working_set_bytes", label, minimum=0),
                private_bytes=_int(entry, "private_bytes", label, minimum=0),
            )
        )

    snapshot = Snapshot(
        taken_unix=taken,
        physical_bytes=physical,
        free_bytes=free,
        commit_total_bytes=commit_total,
        commit_limit_bytes=commit_limit,
        compressed_bytes=compressed_raw,
        wsl_available=wsl_available,
        wsl_running=list(running),
        listeners=listeners,
        supervisor_pids=supervisor_pids,
        processes=processes,
    )
    for proc in processes:
        if proc.pid in snapshot.by_pid:
            raise SnapshotError(f"duplicate pid {proc.pid}")
        snapshot.by_pid[proc.pid] = proc
    for proc in processes:
        snapshot.children.setdefault(proc.ppid, []).append(proc.pid)
    return snapshot


def _require_mapping_snapshot(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SnapshotError(f"snapshot {label} must be a mapping")
    return value


def load_snapshot(path: pathlib.Path | str) -> Snapshot:
    return parse_snapshot(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))


# ------------------------------------------------------------------- fleet wire


@dataclass(frozen=True)
class Fleet:
    supervisor: Any
    control: Any


def load_fleet(path: pathlib.Path | str) -> Fleet:
    """Import the shipped MCP fleet supervisor + control plane, or fail closed."""
    path = pathlib.Path(path)
    if not path.is_file():
        raise PolicyError(f"fleet supervisor not found: {path}")
    scripts_dir = str(path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    control = importlib.import_module("mcp_control_plane")
    spec = importlib.util.spec_from_file_location("mcp_fleet_supervisor", path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so the module's @dataclass annotations resolve.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return Fleet(supervisor=module, control=control)


# --------------------------------------------------------------------- decision


@dataclass
class Decision:
    rule: str
    action: str  # stop | report | wsl-shutdown
    min_tier: str
    root: ProcRow
    tree: list[ProcRow]
    graceful_seconds: int
    detail: dict[str, Any]

    @property
    def tree_private_bytes(self) -> int:
        return sum(member.private_bytes for member in self.tree)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "action": self.action,
            "min_tier": self.min_tier,
            "root_pid": self.root.pid,
            "tree_pids": [member.pid for member in self.tree],
            "tree_private_bytes": self.tree_private_bytes,
            "graceful_seconds": self.graceful_seconds,
            "detail": self.detail,
        }


@dataclass
class Plan:
    taken_unix: int
    tier: str
    raw_tier: str
    metrics: dict[str, Any]
    decisions: list[Decision]
    delegate_reaper: bool
    reaper_root_pid: int | None
    wsl_shutdown: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "raw_tier": self.raw_tier,
            "metrics": self.metrics,
            "delegate_reaper": self.delegate_reaper,
            "wsl_shutdown": self.wsl_shutdown,
            "decisions": [decision.to_dict() for decision in self.decisions],
        }


TERMINAL_ACTIONS = frozenset({"stop", "wsl-shutdown"})


def tier_at_least(current: str, minimum: str) -> bool:
    return TIER_ORDER[current] >= TIER_ORDER[minimum]


# ----------------------------------------------------------------------- engine


class Engine:
    def __init__(
        self,
        policy: dict[str, Any],
        state: dict[str, Any] | None,
        *,
        fleet: Fleet,
        registry: dict[str, Any] | None,
    ) -> None:
        self.policy = policy
        self.fleet = fleet
        self.registry = registry
        state = state or {}
        if state and state.get("schema") != SCHEMA_STATE:
            raise PolicyError("state schema is not recognised")
        self.state = state or {
            "schema": SCHEMA_STATE,
            "last_run_unix": 0,
            "tier": {"current": "normal", "calm_streak": 0},
            "observations": {},
            "wsl": {},
        }
        self.state.setdefault("observations", {})
        self.state.setdefault("tier", {"current": "normal", "calm_streak": 0})
        if policy["mcp"]["enabled"] and registry is None:
            raise PolicyError("registry is required when mcp is enabled")

    # -- helpers ---------------------------------------------------------

    def _is_protected(self, proc: ProcRow, snapshot: Snapshot) -> bool:
        if proc.pid in snapshot.supervisor_pids:
            return True
        if proc.name.lower() in self.policy["protected"]["names"]:
            return True
        if not proc.executable:
            return True
        exe = proc.exe_norm
        if any(pattern.search(exe) for pattern in self.policy["protected"]["exe"]):
            return True
        haystack = f"{exe} {proc.cmd_norm}"
        return any(token in haystack for token in self.policy["protected"]["tokens"])

    def _descendants(self, root: int, snapshot: Snapshot) -> list[int]:
        order: list[int] = []
        seen = {root}

        def walk(pid: int) -> None:
            parent_created = snapshot.by_pid[pid].created_unix
            for child in snapshot.children.get(pid, []):
                if child in seen:
                    continue
                if snapshot.by_pid[child].created_unix < parent_created:
                    continue  # PID reuse: a child cannot predate its parent.
                seen.add(child)
                walk(child)
                order.append(child)
            if pid != root:
                order.append(pid)

        walk(root)
        order.append(root)
        # children-first: deepest first, root last.
        return list(dict.fromkeys(order))

    def _build_tree(
        self, root: int, snapshot: Snapshot
    ) -> tuple[list[ProcRow], list[int]]:
        tree: list[ProcRow] = []
        protected: list[int] = []
        for pid in self._descendants(root, snapshot):
            proc = snapshot.by_pid[pid]
            if self._is_protected(proc, snapshot):
                protected.append(pid)
                continue
            tree.append(proc)
        return tree, protected

    def _is_parentless(self, proc: ProcRow, snapshot: Snapshot) -> bool:
        parent = snapshot.by_pid.get(proc.ppid)
        if parent is None:
            return True
        return parent.created_unix > proc.created_unix

    def _runtime_of(self, proc: ProcRow) -> str | None:
        exe = proc.exe_norm
        cmd = proc.cmd_norm
        for name, spec in self.policy["runtimes"].items():
            if spec["exe"] is not None and spec["exe"].search(exe):
                return name
            if any(token in cmd for token in spec["tokens"]):
                return name
        return None

    def _ownership(
        self, proc: ProcRow, own_runtime: str, snapshot: Snapshot
    ) -> tuple[str, str | None]:
        current = snapshot.by_pid.get(proc.ppid)
        seen: set[int] = {proc.pid}
        while current is not None and current.pid not in seen:
            seen.add(current.pid)
            if current.name.lower() in IDE_NAMES:
                return "ide", current.name.lower()
            other = self._runtime_of(current)
            if other is not None and other != own_runtime:
                return "runtime", other
            current = snapshot.by_pid.get(current.ppid)
        if self._is_parentless(proc, snapshot):
            return "orphan", None
        return "stale", None

    def _owner_root(self, root: int, snapshot: Snapshot) -> str:
        current: ProcRow | None = snapshot.by_pid.get(root)
        seen: set[int] = set()
        while current is not None and current.pid not in seen:
            seen.add(current.pid)
            runtime = self._runtime_of(current)
            if runtime is not None:
                return f"{runtime}:{current.pid}"
            current = snapshot.by_pid.get(current.ppid)
        return f"service:{root}"

    def _idle_streak(self, proc: ProcRow) -> int:
        entry = self.state["observations"].get(_key(proc))
        return int(entry["idle_streak"]) if entry else 0

    def _update_observations(self, snapshot: Snapshot) -> None:
        thresholds = self.policy["idle"]
        previous = self.state["observations"]
        current: dict[str, Any] = {}
        for proc in snapshot.processes:
            key = _key(proc)
            prior = previous.get(key)
            streak = 0
            if proc.metrics_known and prior is not None and prior.get("metrics_known"):
                cpu_delta = proc.cpu_seconds - prior["cpu"]
                io_delta = proc.io_bytes - prior["io"]
                idle = (
                    0 <= cpu_delta <= thresholds["cpu"]
                    and 0 <= io_delta <= thresholds["io"]
                )
                streak = int(prior["idle_streak"]) + 1 if idle else 0
            first_seen = prior["first_seen"] if prior else snapshot.taken_unix
            current[key] = {
                "idle_streak": streak,
                "cpu": proc.cpu_seconds,
                "io": proc.io_bytes,
                "metrics_known": proc.metrics_known,
                "first_seen": first_seen,
                "last_seen": snapshot.taken_unix,
            }
        self.state["observations"] = current

    def _confirmed_idle(self, proc: ProcRow, observations: int) -> bool:
        return proc.metrics_known and self._idle_streak(proc) >= observations

    # -- tier ------------------------------------------------------------

    def _raw_tier(self, snapshot: Snapshot) -> tuple[str, float]:
        ratio = snapshot.commit_total_bytes / snapshot.physical_bytes
        pressure = self.policy["pressure"]
        tier = "normal"
        if (
            snapshot.free_bytes < pressure["elevated"]["free"]
            or ratio > pressure["elevated"]["ratio"]
        ):
            tier = "elevated"
        if (
            snapshot.free_bytes < pressure["critical"]["free"]
            or ratio > pressure["critical"]["ratio"]
        ):
            tier = "critical"
        return tier, ratio

    def _effective_tier(self, raw_tier: str) -> str:
        state = self.state["tier"]
        current = state.get("current", "normal")
        if TIER_ORDER[raw_tier] >= TIER_ORDER[current]:
            state["current"] = raw_tier
            state["calm_streak"] = 0
            return raw_tier
        streak = int(state.get("calm_streak", 0)) + 1
        if streak >= self.policy["pressure"]["deescalate"]:
            state["current"] = raw_tier
            state["calm_streak"] = 0
            return raw_tier
        state["calm_streak"] = streak
        return current

    # -- evaluate --------------------------------------------------------

    def evaluate(self, snapshot: Snapshot, *, reaper_available: bool = True) -> Plan:
        if snapshot.taken_unix <= self.state.get("last_run_unix", 0):
            raise SnapshotError("snapshot taken_unix must be after the last run")
        self._update_observations(snapshot)
        raw_tier, ratio = self._raw_tier(snapshot)
        tier = self._effective_tier(raw_tier)

        metrics: dict[str, Any] = {
            "free_bytes": snapshot.free_bytes,
            "physical_bytes": snapshot.physical_bytes,
            "commit_total_bytes": snapshot.commit_total_bytes,
            "commit_limit_bytes": snapshot.commit_limit_bytes,
            "commit_ratio": ratio,
            "compressed_bytes": snapshot.compressed_bytes,
            "process_count": len(snapshot.processes),
        }
        decisions: list[Decision] = []
        claimed: set[int] = set()

        singleton_members = self._collect_singleton_members(snapshot)
        delegate_pids = self._collect_delegated_cursor_roots(snapshot, reaper_available)
        reaper_root = min(delegate_pids) if delegate_pids else None

        self._rule_retired(snapshot, tier, decisions, claimed)
        if self.policy["mcp"]["enabled"]:
            self._rule_mcp(
                snapshot, tier, decisions, claimed, singleton_members, metrics
            )
        self._rule_orphans(
            snapshot, tier, decisions, claimed, singleton_members, delegate_pids
        )
        self._rule_sessions(
            snapshot, tier, decisions, claimed, singleton_members, delegate_pids
        )
        wsl_shutdown = self._rule_wsl(snapshot, tier, decisions)
        self._rule_browsers(snapshot, decisions)
        if reaper_root is not None:
            decisions.append(
                Decision(
                    rule="cursor-orphan-reaper",
                    action="report",
                    min_tier="normal",
                    root=snapshot.by_pid[reaper_root],
                    tree=[],
                    graceful_seconds=0,
                    detail={
                        "delegated": True,
                        "root_pid": reaper_root,
                        "reason": "parentless cursor-agent root; delegated to the reaper",
                    },
                )
            )

        self.state["last_run_unix"] = snapshot.taken_unix
        return Plan(
            taken_unix=snapshot.taken_unix,
            tier=tier,
            raw_tier=raw_tier,
            metrics=metrics,
            decisions=decisions,
            delegate_reaper=reaper_root is not None,
            reaper_root_pid=reaper_root,
            wsl_shutdown=wsl_shutdown,
        )

    # -- collectors ------------------------------------------------------

    def _collect_delegated_cursor_roots(
        self, snapshot: Snapshot, reaper_available: bool
    ) -> set[int]:
        if not reaper_available:
            return set()
        delegated: set[int] = set()
        for proc in snapshot.processes:
            if self._runtime_of(proc) != "cursor-agent":
                continue
            handler = self.policy["runtimes"]["cursor-agent"]["orphanHandler"]
            if handler != "cursor-orphan-reaper":
                continue
            if self._is_parentless(proc, snapshot):
                for pid in self._descendants(proc.pid, snapshot):
                    delegated.add(pid)
        return delegated

    def _collect_singleton_members(self, snapshot: Snapshot) -> dict[int, str]:
        members: dict[int, str] = {}
        if self.registry is None:
            return members
        for name, server in self.registry["mcp"]["servers"].items():
            tokens = server.get("processMatch")
            if not tokens:
                continue
            needles = [_norm(token) for token in tokens]
            for proc in snapshot.processes:
                haystack = f"{proc.exe_norm} {proc.cmd_norm}"
                if all(needle in haystack for needle in needles):
                    members[proc.pid] = name
        return members

    # -- rules -----------------------------------------------------------

    def _rule_retired(self, snapshot, tier, decisions, claimed) -> None:
        for entry in self.policy["retired"]:
            for proc in snapshot.processes:
                if proc.pid in claimed:
                    continue
                haystack = f"{proc.exe_norm} {proc.cmd_norm}"
                if not all(token in haystack for token in entry["tokens"]):
                    continue
                if self._is_protected(proc, snapshot):
                    continue
                # The root cleared the protected check, so it is always in its own
                # tree; no empty-tree guard is needed here.
                tree, protected = self._build_tree(proc.pid, snapshot)
                for member in tree:
                    claimed.add(member.pid)
                decisions.append(
                    Decision(
                        rule="retired",
                        action="stop",
                        min_tier="normal",
                        root=proc,
                        tree=tree,
                        graceful_seconds=entry["graceful"],
                        detail={
                            "id": entry["id"],
                            "remediation": entry["remediation"],
                            "protected_members": protected,
                            "parent_chain": self._parent_chain(proc, snapshot),
                        },
                    )
                )

    def _parent_chain(self, proc: ProcRow, snapshot: Snapshot) -> list[dict[str, Any]]:
        chain: list[dict[str, Any]] = []
        current = snapshot.by_pid.get(proc.ppid)
        seen: set[int] = {proc.pid}
        while current is not None and current.pid not in seen:
            seen.add(current.pid)
            chain.append({"pid": current.pid, "name": current.name})
            current = snapshot.by_pid.get(current.ppid)
        return chain

    def _rule_orphans(
        self, snapshot, tier, decisions, claimed, singleton_members, delegate_pids
    ) -> None:
        names = set(self.policy["orphans"]["names"])
        min_age = self.policy["orphans"]["minAge"]
        observations = self.policy["idle"]["observations"]
        graceful = self.policy["orphans"]["graceful"]
        for proc in snapshot.processes:
            if proc.pid in claimed or proc.pid in delegate_pids:
                continue
            if proc.pid in singleton_members:
                continue
            if proc.name.lower() not in names:
                continue
            if self._is_protected(proc, snapshot):
                continue
            if not self._is_parentless(proc, snapshot):
                continue
            own_runtime = self._runtime_of(proc)
            if own_runtime is not None and own_runtime != "cursor-agent":
                # Non-cursor runtimes are session-age's job, not the generic reaper's.
                continue
            if own_runtime is None and self._subtree_has_runtime(proc.pid, snapshot):
                # A detached shell hosting a runtime session is not a leaf leak;
                # leave the tree so the session-age / reaper rules own the runtime
                # child and the husk is reaped once it is a leaf.
                continue
            if snapshot.taken_unix - proc.created_unix < min_age:
                continue
            owned_port = _port_owned_by(proc.pid, snapshot)
            if owned_port is not None:
                decisions.append(
                    Decision(
                        rule="daemon",
                        action="report",
                        min_tier="normal",
                        root=proc,
                        tree=[],
                        graceful_seconds=0,
                        detail={
                            "port": owned_port,
                            "reason": "parentless but owns a listening port; treated "
                            "as an intentional daemon, not a leak",
                        },
                    )
                )
                continue
            tree, protected = self._claimable_tree(proc, snapshot, claimed)
            if not self._all_idle(tree, observations):
                continue
            detail = {
                "idle_observations": self._idle_streak(proc),
                "age_seconds": snapshot.taken_unix - proc.created_unix,
            }
            server = self._server_for(proc, singleton_members)
            if server is not None:
                detail["mcp_server"] = server
            self._commit_stop(
                "orphan",
                proc,
                "normal",
                graceful,
                detail,
                tree,
                protected,
                decisions,
                claimed,
            )

    def _server_for(self, proc: ProcRow, singleton_members) -> str | None:
        if self.registry is None:
            return None
        haystack = f"{proc.exe_norm} {proc.cmd_norm}"
        for name, server in self.registry["mcp"]["servers"].items():
            tokens = self.fleet.supervisor.identity_tokens(name, server)
            if tokens and any(token in haystack for token in tokens):
                return name
        return None

    def _rule_sessions(
        self, snapshot, tier, decisions, claimed, singleton_members, delegate_pids
    ) -> None:
        observations = self.policy["idle"]["observations"]
        stop_active = self.policy["escalation"]["stopActiveAtCritical"]
        for proc in snapshot.processes:
            if proc.pid in claimed or proc.pid in delegate_pids:
                continue
            if proc.pid in singleton_members:
                continue
            runtime = self._runtime_of(proc)
            if runtime is None:
                continue
            spec = self.policy["runtimes"][runtime]
            age = snapshot.taken_unix - proc.created_unix
            private = self._subtree_private(proc.pid, snapshot)
            kind, owner = self._ownership(proc, runtime, snapshot)
            self._maybe_session_age(
                proc,
                runtime,
                spec,
                age,
                kind,
                owner,
                tier,
                observations,
                stop_active,
                snapshot,
                decisions,
                claimed,
            )
            self._maybe_rss(
                proc,
                runtime,
                spec,
                private,
                kind,
                tier,
                observations,
                stop_active,
                snapshot,
                decisions,
                claimed,
            )

    def _maybe_session_age(
        self,
        proc,
        runtime,
        spec,
        age,
        kind,
        owner,
        tier,
        observations,
        stop_active,
        snapshot,
        decisions,
        claimed,
    ) -> None:
        if age <= spec["maxAge"] or proc.pid in claimed:
            return
        detail = {"runtime": runtime, "age_seconds": age}
        if kind in ("ide", "runtime"):
            detail["owned_by"] = owner
            self._add_report(
                "session-age", proc, tier, spec["graceful"], detail, decisions
            )
            return
        self._stop_or_report(
            "session-age",
            proc,
            "normal",
            spec["graceful"],
            detail,
            snapshot,
            decisions,
            claimed,
            tier,
            allow_active_critical=True,
        )

    def _maybe_rss(
        self,
        proc,
        runtime,
        spec,
        private,
        kind,
        tier,
        observations,
        stop_active,
        snapshot,
        decisions,
        claimed,
    ) -> None:
        if proc.pid in claimed:
            return
        if private >= spec["hard"]:
            rule, min_tier = "rss-hard", "normal"
        elif private >= spec["soft"]:
            rule, min_tier = "rss-soft", "elevated"
        else:
            return
        detail = {"runtime": runtime, "private_bytes": private}
        self._stop_or_report(
            rule,
            proc,
            min_tier,
            spec["graceful"],
            detail,
            snapshot,
            decisions,
            claimed,
            tier,
            allow_active_critical=True,
        )

    def _subtree_private(self, root: int, snapshot: Snapshot) -> int:
        return sum(
            snapshot.by_pid[pid].private_bytes
            for pid in self._descendants(root, snapshot)
        )

    def _subtree_has_runtime(self, root: int, snapshot: Snapshot) -> bool:
        return any(
            pid != root and self._runtime_of(snapshot.by_pid[pid]) is not None
            for pid in self._descendants(root, snapshot)
        )

    def _claimable_tree(self, proc, snapshot, claimed):
        tree, protected = self._build_tree(proc.pid, snapshot)
        return [member for member in tree if member.pid not in claimed], protected

    def _all_idle(self, tree, observations) -> bool:
        return bool(tree) and all(
            self._confirmed_idle(member, observations) for member in tree
        )

    def _commit_stop(
        self,
        rule,
        proc,
        min_tier,
        graceful,
        detail,
        tree,
        protected,
        decisions,
        claimed,
    ) -> None:
        for member in tree:
            claimed.add(member.pid)
        decisions.append(
            Decision(
                rule,
                "stop",
                min_tier,
                proc,
                tree,
                graceful,
                dict(detail, protected_members=protected),
            )
        )

    def _stop_or_report(
        self,
        rule,
        proc,
        min_tier,
        graceful,
        detail,
        snapshot,
        decisions,
        claimed,
        tier,
        *,
        allow_active_critical,
    ) -> None:
        tree, protected = self._claimable_tree(proc, snapshot, claimed)
        if not tree:
            return
        observations = self.policy["idle"]["observations"]
        if self._all_idle(tree, observations):
            self._commit_stop(
                rule,
                proc,
                min_tier,
                graceful,
                detail,
                tree,
                protected,
                decisions,
                claimed,
            )
        elif (
            allow_active_critical and self.policy["escalation"]["stopActiveAtCritical"]
        ):
            self._commit_stop(
                rule,
                proc,
                "critical",
                graceful,
                detail,
                tree,
                protected,
                decisions,
                claimed,
            )
        else:
            self._add_report(rule, proc, tier, graceful, detail, decisions)

    def _add_report(self, rule, proc, tier, graceful, detail, decisions) -> None:
        decisions.append(
            Decision(rule, "report", tier, proc, [], graceful, dict(detail))
        )

    # -- mcp -------------------------------------------------------------

    def _rule_mcp(
        self, snapshot, tier, decisions, claimed, singleton_members, metrics
    ) -> None:
        records = [
            self.fleet.supervisor.ProcessRecord(
                pid=proc.pid,
                parent_pid=proc.ppid,
                executable_path=proc.executable,
                command_line=proc.command_line,
                private_bytes=proc.private_bytes,
            )
            for proc in snapshot.processes
        ]
        # evaluate_fleet gives the path-independent aggregates (private-byte sums,
        # per-instance budget). Its duplicate flag keys on the client owner via
        # PurePath, which only splits Windows paths on Windows, so the
        # duplicate/cross-owner verdicts here come from this engine's own
        # regex-based owner resolution instead (see _owner_root).
        report = self.fleet.supervisor.evaluate_fleet(self.registry, records, set())
        servers = self.registry["mcp"]["servers"]
        assigned, _ambiguous, _secret = self.fleet.supervisor.assign_processes(
            servers, records
        )
        self._mcp_singletons(snapshot, tier, decisions, claimed, singleton_members)
        graceful = self.policy["mcp"]["graceful"]
        for name, server in servers.items():
            if server.get("processMatch"):
                continue
            pids = assigned.get(name, set())
            if not pids:
                continue
            roots = self.fleet.supervisor.process_roots(pids, records)
            self._mcp_duplicates(
                name, roots, pids, snapshot, tier, decisions, claimed, graceful
            )
            self._mcp_over_budget(
                name, roots, pids, snapshot, tier, decisions, claimed, graceful
            )
        metrics["fleet"] = {
            "status": report["status"],
            "duplicateServers": sorted(
                {
                    decision.detail["server"]
                    for decision in decisions
                    if decision.rule == "mcp-duplicate-same-owner"
                }
            ),
            "overBudgetServers": report["overBudgetServers"],
            "totalPrivateBytes": report["totalPrivateBytes"],
        }

    def _mcp_singletons(
        self, snapshot, tier, decisions, claimed, singleton_members
    ) -> None:
        grace = self.policy["mcp"]["singletonGrace"]
        min_tier = self.policy["mcp"]["singletonTier"]
        by_server: dict[str, list[int]] = {}
        for pid, name in singleton_members.items():
            by_server.setdefault(name, []).append(pid)
        for name, pids in by_server.items():
            if len(pids) < 2:
                continue
            port = _port_of(self.registry["mcp"]["servers"][name])
            keeper = snapshot.listeners.get(port) if port is not None else None
            if keeper is None or keeper not in pids:
                decisions.append(
                    Decision(
                        rule="mcp-singleton-duplicate",
                        action="report",
                        min_tier=min_tier,
                        root=snapshot.by_pid[min(pids)],
                        tree=[],
                        graceful_seconds=grace,
                        detail={
                            "server": name,
                            "port": port,
                            "member_pids": sorted(pids),
                            "reason": "duplicate singleton but no live port owner yet; "
                            "left for the watchdog to converge",
                        },
                    )
                )
                continue
            for pid in sorted(pids):
                if pid == keeper or pid in claimed:
                    continue
                proc = snapshot.by_pid[pid]
                if snapshot.taken_unix - proc.created_unix <= grace:
                    continue
                tree, protected = self._claimable_tree(proc, snapshot, claimed)
                if not tree:
                    continue
                self._commit_stop(
                    "mcp-singleton-duplicate",
                    proc,
                    min_tier,
                    grace,
                    {"server": name, "port_owner": keeper},
                    tree,
                    protected,
                    decisions,
                    claimed,
                )

    def _mcp_duplicates(
        self, name, roots, pids, snapshot, tier, decisions, claimed, graceful
    ) -> None:
        owners: dict[str, list[int]] = {}
        for root in roots:
            owners.setdefault(self._owner_root(root, snapshot), []).append(root)
        for owner, owner_roots in owners.items():
            if len(owner_roots) < 2:
                continue
            ordered = sorted(
                owner_roots, key=lambda pid: snapshot.by_pid[pid].created_unix
            )
            kept = ordered[0]
            for younger in ordered[1:]:
                proc = snapshot.by_pid[younger]
                detail = {"server": name, "kept_root": kept, "owner": owner}
                self._stop_or_report(
                    "mcp-duplicate-same-owner",
                    proc,
                    self.policy["mcp"]["sameOwner"],
                    graceful,
                    detail,
                    snapshot,
                    decisions,
                    claimed,
                    tier,
                    allow_active_critical=False,
                )
        distinct = sorted(owners)
        if len(distinct) > 1:
            decisions.append(
                Decision(
                    rule="mcp-duplicate-cross-owner",
                    action="report",
                    min_tier="normal",
                    root=snapshot.by_pid[min(roots)],
                    tree=[],
                    graceful_seconds=graceful,
                    detail={
                        "server": name,
                        "owners": distinct,
                        "proposal": "collapse to one shared instance behind "
                        "tools/mcp/mcp-http-host so sessions dial one bridge",
                    },
                )
            )

    def _mcp_over_budget(
        self, name, roots, pids, snapshot, tier, decisions, claimed, graceful
    ) -> None:
        contract = self.fleet.control.effective_server_contract(self.registry, name)
        limit = contract["maxPrivateBytes"]
        for root in roots:
            if root in claimed:
                continue
            instance = self._assigned_private(root, pids, snapshot)
            if instance <= limit:
                continue
            proc = snapshot.by_pid[root]
            detail = {"server": name, "limit_bytes": limit, "instance_bytes": instance}
            self._stop_or_report(
                "mcp-over-budget",
                proc,
                self.policy["mcp"]["overBudget"],
                graceful,
                detail,
                snapshot,
                decisions,
                claimed,
                tier,
                allow_active_critical=False,
            )

    def _assigned_private(self, root: int, pids: set[int], snapshot: Snapshot) -> int:
        return sum(
            snapshot.by_pid[pid].private_bytes
            for pid in self._descendants(root, snapshot)
            if pid in pids
        )

    # -- wsl / browsers --------------------------------------------------

    def _rule_wsl(self, snapshot, tier, decisions) -> bool:
        if not snapshot.wsl_available:
            return False
        names = set(self.policy["wsl"]["names"])
        vmmem = next(
            (proc for proc in snapshot.processes if proc.name.lower() in names), None
        )
        if vmmem is None:
            return False
        if vmmem.private_bytes > self.policy["wsl"]["report"]:
            self._add_report(
                "wsl-report",
                vmmem,
                tier,
                0,
                {"private_bytes": vmmem.private_bytes, "running": snapshot.wsl_running},
                decisions,
            )
        if not snapshot.wsl_running:
            return False
        if not self._confirmed_idle(vmmem, self.policy["wsl"]["observations"]):
            return False
        decisions.append(
            Decision(
                rule="wsl-idle",
                action="wsl-shutdown",
                min_tier=self.policy["wsl"]["tier"],
                root=vmmem,
                tree=[],
                graceful_seconds=0,
                detail={
                    "running": snapshot.wsl_running,
                    "private_bytes": vmmem.private_bytes,
                    "reason": "idle WSL VM; wsl --shutdown reclaims it and "
                    "autoMemoryReclaim keeps the footprint bounded on next start",
                },
            )
        )
        return True

    def _rule_browsers(self, snapshot, decisions) -> None:
        names = set(self.policy["browsers"]["names"])
        buckets: dict[str, list[ProcRow]] = {}
        for proc in snapshot.processes:
            lower = proc.name.lower()
            if lower in names:
                buckets.setdefault(lower, []).append(proc)
        for name, procs in buckets.items():
            total = sum(proc.private_bytes for proc in procs)
            if total <= self.policy["browsers"]["report"]:
                continue
            representative = max(procs, key=lambda proc: proc.private_bytes)
            self._add_report(
                "browser",
                representative,
                "normal",
                0,
                {
                    "browser": name,
                    "process_count": len(procs),
                    "private_bytes": total,
                    "proposal": "enable Memory Saver / sleeping tabs so idle tabs "
                    "release working set instead of holding commit",
                },
                decisions,
            )


def _key(proc: ProcRow) -> str:
    return f"{proc.pid}|{proc.created_unix}"


def _port_owned_by(pid: int, snapshot: Snapshot) -> int | None:
    for port, owner in snapshot.listeners.items():
        if owner == pid:
            return port
    return None


def _port_of(server: dict[str, Any]) -> int | None:
    url = server.get("url")
    if not isinstance(url, str):
        return None
    match = re.search(r":(\d+)(?:/|$)", url)
    return int(match.group(1)) if match else None


# ------------------------------------------------------------------ ledger


@dataclass(frozen=True)
class StopResult:
    pid: int
    created_unix: int
    outcome: str
    detail: str


class Ledger:
    def __init__(self, path: pathlib.Path | str, *, max_bytes: int = 20 * 1024 * 1024):
        self.path = pathlib.Path(path)
        self.max_bytes = max_bytes

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n"
        # Rotate BEFORE writing so the live file always holds the latest line.
        if self.path.exists() and (
            self.path.stat().st_size + len(line.encode("utf-8")) > self.max_bytes
        ):
            self.path.replace(self.path.with_name(self.path.name + ".1"))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _truncate(text: str) -> str:
    if len(text) > COMMAND_LINE_MAX:
        return text[:COMMAND_LINE_MAX] + "..."
    return text


def record_for(
    proc: ProcRow,
    *,
    rule: str,
    action: str,
    tier: str,
    result: str,
    reason: str,
    run_id: str,
    ts: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_LEDGER,
        "ts": ts,
        "run_id": run_id,
        "rule": rule,
        "action": action,
        "tier": tier,
        "result": result,
        "reason": reason,
        "pid": proc.pid,
        "ppid": proc.ppid,
        "created_unix": proc.created_unix,
        "name": proc.name,
        "executable": redact(proc.executable),
        "command_line": redact(_truncate(proc.command_line)),
        "command_sha256": hashlib.sha256(proc.command_line.encode("utf-8")).hexdigest()[
            :16
        ],
        "private_bytes": proc.private_bytes,
        "working_set_bytes": proc.working_set_bytes,
        "detail": extra or {},
    }


# ------------------------------------------------------------------ apply


def apply_plan(
    plan: Plan,
    actuator: Any,
    ledger: Ledger,
    *,
    apply: bool,
    run_id: str,
) -> dict[str, Any]:
    ts = plan.taken_unix
    stopped = failed = deferred = dry_run = 0
    exit_bad = False
    for decision in plan.decisions:
        if decision.action not in TERMINAL_ACTIONS:
            ledger.append(
                record_for(
                    decision.root,
                    rule=decision.rule,
                    action=decision.action,
                    tier=plan.tier,
                    result="report",
                    reason=decision.rule,
                    run_id=run_id,
                    ts=ts,
                    extra=decision.detail,
                )
            )
            continue
        gate_ok = tier_at_least(plan.tier, decision.min_tier)
        if not apply:
            planned, dry_run = "dry-run", dry_run + 1
        elif not gate_ok:
            planned, deferred = "deferred", deferred + 1
        else:
            planned = None
        if decision.action == "wsl-shutdown":
            result = planned
            if planned is None:
                result = actuator.wsl_shutdown().outcome
                if result == "failed":
                    exit_bad = True
            ledger.append(
                {
                    "schema": SCHEMA_LEDGER,
                    "ts": ts,
                    "run_id": run_id,
                    "rule": decision.rule,
                    "action": "wsl-shutdown",
                    "tier": plan.tier,
                    "result": result,
                    "reason": decision.rule,
                    "pid": 0,
                    "detail": decision.detail,
                }
            )
            continue
        if planned is None:
            results = actuator.stop_tree(
                decision.tree, graceful_seconds=decision.graceful_seconds
            )
            any_failed = False
            for member, outcome in zip(decision.tree, results):
                any_failed = any_failed or outcome.outcome == "failed"
                ledger.append(
                    record_for(
                        member,
                        rule=decision.rule,
                        action="stop",
                        tier=plan.tier,
                        result=outcome.outcome,
                        reason=outcome.detail or decision.rule,
                        run_id=run_id,
                        ts=ts,
                        extra=decision.detail,
                    )
                )
            if any_failed:
                failed += 1
                exit_bad = True
            else:
                stopped += 1
        else:
            for member in decision.tree:
                ledger.append(
                    record_for(
                        member,
                        rule=decision.rule,
                        action="stop",
                        tier=plan.tier,
                        result=planned,
                        reason=decision.rule,
                        run_id=run_id,
                        ts=ts,
                        extra=decision.detail,
                    )
                )
    if plan.delegate_reaper:
        exit_bad = (
            _delegate_reaper(plan, actuator, ledger, apply, run_id, ts) or exit_bad
        )
    ledger.append(
        {
            "schema": SCHEMA_LEDGER,
            "ts": ts,
            "run_id": run_id,
            "rule": "run",
            "action": "summary",
            "tier": plan.tier,
            "result": "ok",
            "detail": {
                "tier": plan.tier,
                "raw_tier": plan.raw_tier,
                "apply": apply,
                "stopped": stopped,
                "failed": failed,
                "deferred": deferred,
                "dry_run": dry_run,
                "metrics": plan.metrics,
            },
        }
    )
    return {
        "stopped": stopped,
        "failed": failed,
        "deferred": deferred,
        "dry_run": dry_run,
        "exit_code": 2 if exit_bad else 0,
    }


def _delegate_reaper(plan, actuator, ledger, apply, run_id, ts) -> bool:
    exit_bad = False
    detail: dict[str, Any] = {"root_pid": plan.reaper_root_pid}
    if apply:
        outcome = actuator.run_reaper(apply=True)
        detail["reaper"] = outcome
        ok = outcome.get("exit_code", 1) == 0 and outcome.get("status") == "success"
        result = "delegated" if ok else "failed"
        exit_bad = not ok
    else:
        result = "dry-run"
    ledger.append(
        {
            "schema": SCHEMA_LEDGER,
            "ts": ts,
            "run_id": run_id,
            "rule": "cursor-orphan-reaper",
            "action": "delegate",
            "tier": plan.tier,
            "result": result,
            "reason": "cursor-agent lifecycle owned by the reaper",
            "pid": plan.reaper_root_pid,
            "detail": detail,
        }
    )
    return exit_bad


def build_actuator(policy: dict[str, Any], *, run_id: str):  # pragma: no cover
    """Construct the real Windows actuator (see hygiene_actuate.WindowsActuator)."""
    from hygiene_actuate import WindowsActuator

    return WindowsActuator(policy, run_id=run_id)


# --------------------------------------------------------------------- cli


def _load_state(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyError(f"state file is not valid JSON: {exc}") from exc


def _load_registry(policy: dict[str, Any], path: pathlib.Path) -> dict[str, Any] | None:
    if not policy["mcp"]["enabled"]:
        return None
    if not path.is_file():
        raise PolicyError(f"registry not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _build_engine(args, *, need_registry: bool) -> tuple[Engine, Snapshot, dict]:
    policy = load_policy(args.policy)
    registry = (
        _load_registry(policy, pathlib.Path(args.registry)) if need_registry else None
    )
    fleet = load_fleet(args.fleet)
    state = (
        _load_state(pathlib.Path(args.state)) if getattr(args, "state", None) else {}
    )
    snapshot = load_snapshot(args.snapshot)
    engine = Engine(policy, state, fleet=fleet, registry=registry)
    return engine, snapshot, policy


def _reaper_available(args, policy: dict[str, Any]) -> bool:
    if args.reaper_available == "yes":
        return True
    if args.reaper_available == "no":
        return False
    path = policy["integration"]["reaperPath"]
    return bool(path) and pathlib.Path(path).is_file()


def _cmd_run(args) -> int:
    engine, snapshot, policy = _build_engine(args, need_registry=True)
    plan = engine.evaluate(snapshot, reaper_available=_reaper_available(args, policy))
    run_id = f"{snapshot.taken_unix}-{plan.tier}"
    ledger = Ledger(pathlib.Path(args.ledger), max_bytes=policy["ledger"]["maxBytes"])
    actuator = build_actuator(policy, run_id=run_id) if args.apply else None
    summary = apply_plan(plan, actuator, ledger, apply=args.apply, run_id=run_id)
    pathlib.Path(args.state).write_text(
        json.dumps(engine.state, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "SUCCESS:process-hygiene "
        f"tier={plan.tier} apply={str(args.apply).lower()} "
        f"stopped={summary['stopped']} failed={summary['failed']} "
        f"deferred={summary['deferred']} dry_run={summary['dry_run']} "
        f"delegate_reaper={str(plan.delegate_reaper).lower()}"
    )
    return summary["exit_code"]


def _cmd_explain(args) -> int:
    engine, snapshot, policy = _build_engine(args, need_registry=True)
    plan = engine.evaluate(snapshot, reaper_available=_reaper_available(args, policy))
    print(json.dumps(plan.to_dict(), ensure_ascii=True, indent=2))
    return 0


def _cmd_validate_policy(args) -> int:
    try:
        load_policy(args.policy)
    except PolicyError as exc:
        print(f"FAILED:process-hygiene-policy {exc}")
        return 1
    print("SUCCESS:process-hygiene-policy ok")
    return 0


def _cmd_validate_snapshot(args) -> int:
    try:
        snapshot = load_snapshot(args.snapshot)
    except SnapshotError as exc:
        print(f"FAILED:process-hygiene-snapshot {exc}")
        return 1
    print(f"SUCCESS:process-hygiene-snapshot processes={len(snapshot.processes)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="evaluate and (with --apply) actuate")
    run.add_argument("--snapshot", required=True)
    run.add_argument("--policy", default=str(DEFAULT_POLICY_PATH))
    run.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    run.add_argument("--fleet", default=str(DEFAULT_FLEET_PATH))
    run.add_argument("--state", required=True)
    run.add_argument("--ledger", required=True)
    run.add_argument("--apply", action="store_true")
    run.add_argument("--reaper-available", choices=["yes", "no"], default=None)
    run.set_defaults(func=_cmd_run)

    explain = sub.add_parser("explain", help="print the plan as JSON; write nothing")
    explain.add_argument("--snapshot", required=True)
    explain.add_argument("--policy", default=str(DEFAULT_POLICY_PATH))
    explain.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    explain.add_argument("--fleet", default=str(DEFAULT_FLEET_PATH))
    explain.add_argument("--state", default=None)
    explain.add_argument("--reaper-available", choices=["yes", "no"], default=None)
    explain.set_defaults(func=_cmd_explain)

    vp = sub.add_parser("validate-policy", help="validate a policy file")
    vp.add_argument("--policy", default=str(DEFAULT_POLICY_PATH))
    vp.set_defaults(func=_cmd_validate_policy)

    vs = sub.add_parser("validate-snapshot", help="validate a snapshot file")
    vs.add_argument("--snapshot", required=True)
    vs.set_defaults(func=_cmd_validate_snapshot)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (PolicyError, SnapshotError) as exc:
        print(f"FAILED:process-hygiene {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
