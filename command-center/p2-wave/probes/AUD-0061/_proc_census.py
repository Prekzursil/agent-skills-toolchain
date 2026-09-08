r"""Shared /proc introspection for AUD-0061 (MCP live process census).

Pure /proc parsing -- deliberately does NOT shell out to `ps` for the census
itself (a forked `ps` child is a transient process that can pollute its own
scan, which is exactly the self-referential bug class the catalog's
tests_required control targets). `ps` is only used, if at all, by a caller
for a human-readable cross-check, never by the counting logic.

Creation-time comparisons use the raw starttime field (field 22 of
/proc/<pid>/stat, clock ticks since boot) rather than a wall-clock string,
because ticks-since-boot is the value the kernel actually hands back and is
exact-integer comparable with no rounding ambiguity.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

HZ = os.sysconf("SC_CLK_TCK")


def boot_time_epoch() -> int:
    with open("/proc/stat", encoding="ascii", errors="replace") as f:
        for line in f:
            if line.startswith("btime "):
                return int(line.split()[1])
    raise RuntimeError("btime not found in /proc/stat")


def read_stat_fields(pid: int) -> dict[str, Any] | None:
    """Parse /proc/<pid>/stat. The comm field is parenthesised and may itself
    contain spaces/parens, so split on the LAST ')' before tokenising the
    fixed-width remainder -- the standard safe parse."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii", errors="replace")
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    try:
        pid_part, rest = raw.split("(", 1)
        comm, rest2 = rest.rsplit(")", 1)
        fields = rest2.split()
        # fields[0] is state; ppid is fields[1]; starttime is fields[19] (0-indexed)
        # because field list here starts AFTER "pid (comm)", so original field
        # numbering 3=state,4=ppid,...,22=starttime maps to fields[0],[1],...,[19]
        ppid = int(fields[1])
        starttime_ticks = int(fields[19])
        return {"pid": int(pid_part.strip()), "comm": comm, "ppid": ppid, "starttime_ticks": starttime_ticks}
    except (ValueError, IndexError):
        return None


def read_status_mem(pid: int) -> dict[str, int]:
    vmrss_kb = 0
    vmsize_kb = 0
    try:
        text = Path(f"/proc/{pid}/status").read_text(encoding="ascii", errors="replace")
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return {"vmrss_kb": 0, "vmsize_kb": 0}
    for line in text.splitlines():
        if line.startswith("VmRSS:"):
            vmrss_kb = int(line.split()[1])
        elif line.startswith("VmSize:"):
            vmsize_kb = int(line.split()[1])
    return {"vmrss_kb": vmrss_kb, "vmsize_kb": vmsize_kb}


def read_cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return []
    parts = raw.split(b"\x00")
    return [p.decode("utf-8", errors="replace") for p in parts if p != b""]


def own_creation_ticks() -> int:
    stat = read_stat_fields(os.getpid())
    if stat is None:
        raise RuntimeError("cannot read own /proc/self/stat")
    return int(stat["starttime_ticks"])


def list_all_pids() -> list[int]:
    out = []
    for name in os.listdir("/proc"):
        if name.isdigit():
            out.append(int(name))
    return out


def scan_raw(extra_self_marker_pids: frozenset[int] = frozenset()) -> list[dict[str, Any]]:
    """Enumerate every PID visible in /proc right now with cmdline + mem +
    creation ticks. `extra_self_marker_pids` is accepted only so a caller can
    ask this function to ALSO tag pids it already knows are "self" for
    bookkeeping; it does not affect what gets returned (no filtering here --
    the raw scan is deliberately unfiltered so the self-exclusion step is a
    separate, auditable pass)."""
    rows = []
    for pid in list_all_pids():
        stat = read_stat_fields(pid)
        if stat is None:
            continue
        mem = read_status_mem(pid)
        cmdline = read_cmdline(pid)
        rows.append(
            {
                "pid": stat["pid"],
                "ppid": stat["ppid"],
                "comm": stat["comm"],
                "starttime_ticks": stat["starttime_ticks"],
                "cmdline": cmdline,
                "vmrss_kb": mem["vmrss_kb"],
                "vmsize_kb": mem["vmsize_kb"],
                "is_declared_self": pid in extra_self_marker_pids,
            }
        )
    return rows


def apply_self_exclusion(rows: list[dict[str, Any]], own_ticks: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split rows into (kept, excluded) where excluded = every row whose
    starttime_ticks EXACTLY equals own_ticks (the calling probe's own
    creation time). This is the tests_required control mechanism: it removes
    the probe's own process (and any other process that happens to share the
    exact same creation tick, which in practice is only ever the probe
    itself at this granularity on a lightly loaded host) regardless of
    whether a naive substring matcher would otherwise have flagged it."""
    kept, excluded = [], []
    for r in rows:
        if r["starttime_ticks"] == own_ticks:
            excluded.append(r)
        else:
            kept.append(r)
    return kept, excluded


def find_exec_daemon_mcp_config(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Locate the exec-daemon process (the Cursor Cloud pod's session host)
    and parse its --mcp-config JSON argument, which declares this session's
    configured MCP servers. Returns None if no such process/arg is found --
    a residual_unknown, not a crash."""
    for r in rows:
        cmdline = r["cmdline"]
        if not cmdline:
            continue
        joined = " ".join(cmdline)
        if "exec-daemon" not in joined and "/exec-daemon/" not in (cmdline[0] if cmdline else ""):
            continue
        if "--mcp-config" not in cmdline:
            continue
        idx = cmdline.index("--mcp-config")
        if idx + 1 >= len(cmdline):
            continue
        raw_json = cmdline[idx + 1]
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        bc_id_match = re.search(r"bc_id=([\w-]+)", joined)
        return {
            "exec_daemon_pid": r["pid"],
            "exec_daemon_ppid": r["ppid"],
            "exec_daemon_vmrss_kb": r["vmrss_kb"],
            "exec_daemon_vmsize_kb": r["vmsize_kb"],
            "exec_daemon_starttime_ticks": r["starttime_ticks"],
            "bc_id": bc_id_match.group(1) if bc_id_match else None,
            "mcp_servers_config": parsed.get("mcpServers", {}),
            "raw_arg_bytes": len(raw_json),
        }
    return None


def server_match(row: dict[str, Any], server_name: str, server_def: dict[str, Any]) -> bool:
    """A process matches a configured MCP server definition if its argv[0]
    basename EXACTLY equals the server's declared command AND at least one
    argv token contains a distinguishing fragment of the server's declared
    args (so `node` alone, e.g. this very interpreter's parent shell, never
    counts as a match for a `node ... start.mjs` server).

    Explicitly excludes any process whose cmdline contains "--mcp-config":
    that flag's value is a JSON blob which NAMES every configured server's
    command/args as text (e.g. the literal substring "start.mjs" appears
    inside the exec-daemon's own --mcp-config argument even though the
    exec-daemon itself never executes start.mjs). Counting that process as a
    live "Context-mode" match would be a use-vs-mention detector failure --
    matching a process that MENTIONS the server in its config, not one that
    actually USES/runs it. Measured on this host: without this guard,
    probe1 misclassified pid 753 (the exec-daemon) as a live Context-mode
    match; this exclusion was added after observing that false positive."""
    cmdline = row["cmdline"]
    if not cmdline:
        return False
    if "--mcp-config" in cmdline:
        return False
    argv0_base = os.path.basename(cmdline[0])
    declared_command = server_def.get("command", "")
    if argv0_base != declared_command:
        return False
    declared_args = server_def.get("args", [])
    joined = " ".join(cmdline)
    for a in declared_args:
        frag = a.replace("${CLAUDE_PLUGIN_ROOT}", "").strip("/")
        if not frag:
            continue
        # Strip template-variable wrapper; look for the literal remainder
        # (e.g. "start.mjs", "browser-use@latest", "chrome-devtools-mcp@1.2.0").
        candidate = frag.split("/")[-1]
        if candidate and candidate in joined:
            return True
    return False
